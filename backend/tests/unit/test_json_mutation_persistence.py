import ast
from pathlib import Path

from sqlalchemy import JSON

from models import Character, CombatState, GameLog, Module, Session


BACKEND_DIR = Path(__file__).resolve().parents[2]
SOURCE_DIRS = (BACKEND_DIR / "api", BACKEND_DIR / "services")

ORM_VARIABLE_NAMES = {
    "session",
    "sess",
    "combat",
    "combat_state",
    "char",
    "character",
    "player",
    "attacker",
    "target",
    "target_char",
    "target_character",
    "source",
    "source_char",
    "source_character",
    "caster",
    "actor",
    "actor_char",
    "actor_character",
    "module",
    "log",
    "game_log",
    "host_char",
    "guest_char",
    "ally",
    "enemy_char",
}
COPY_CALLS = {"dict", "list", "set"}
MUTATING_METHODS = {
    "append",
    "extend",
    "insert",
    "pop",
    "clear",
    "update",
    "setdefault",
    "remove",
    "discard",
    "sort",
    "reverse",
}


def _json_field_names() -> set[str]:
    fields: set[str] = set()
    for model in (Session, CombatState, GameLog, Module, Character):
        for column in model.__table__.columns:
            if isinstance(column.type, JSON):
                fields.add(column.name)
    return fields


JSON_FIELDS = _json_field_names()


class JsonMutationScanner(ast.NodeVisitor):
    def __init__(self, path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef):
        self.path = path
        self.function_name = node.name
        self.aliases: dict[str, tuple[tuple[str, str], str]] = {}
        self.mutations: list[tuple[int, str, tuple[str, str], str, str, str]] = []
        self.persist_operations: list[tuple[int, tuple[str, str], str]] = []
        for child in node.body:
            self.visit(child)

    def _json_attr(self, node: ast.AST) -> tuple[str, str] | None:
        if (
            isinstance(node, ast.Attribute)
            and node.attr in JSON_FIELDS
            and isinstance(node.value, ast.Name)
            and node.value.id in ORM_VARIABLE_NAMES
        ):
            return node.value.id, node.attr
        return None

    def _source_from_expr(self, node: ast.AST) -> tuple[tuple[str, str], str] | None:
        attr = self._json_attr(node)
        if attr:
            return attr, "direct"

        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and node.values:
            attr = self._json_attr(node.values[0])
            if attr:
                return attr, "direct"

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in COPY_CALLS
            and node.args
        ):
            copied = self._source_from_expr(node.args[0])
            if copied:
                return copied[0], "copy"

        return None

    def _base_name(self, node: ast.AST) -> str | None:
        while isinstance(node, (ast.Subscript, ast.Attribute)):
            node = node.value
        return node.id if isinstance(node, ast.Name) else None

    def _json_attr_base(self, node: ast.AST) -> tuple[str, tuple[str, str]] | None:
        if not isinstance(node, (ast.Subscript, ast.Attribute)):
            return None

        root = node.value
        while isinstance(root, (ast.Subscript, ast.Attribute)):
            attr = self._json_attr(root)
            if attr:
                return ast.unparse(root), attr
            root = root.value

        attr = self._json_attr(root)
        if attr:
            return ast.unparse(root), attr
        return None

    def _record_mutation(self, node: ast.AST, lineno: int, kind: str, source: str) -> None:
        direct = self._json_attr_base(node)
        if direct:
            alias, field = direct
            self.mutations.append((lineno, alias, field, "direct", kind, source))
            return

        base = self._base_name(node)
        if base in self.aliases:
            field, mode = self.aliases[base]
            self.mutations.append((lineno, base, field, mode, kind, source))

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            attr = self._json_attr(target)
            if attr:
                self.persist_operations.append((node.lineno, attr, "assign"))

        for target in node.targets:
            if not isinstance(target, ast.Name):
                self._record_mutation(
                    target,
                    node.lineno,
                    "nested assign",
                    ast.unparse(node)[:160],
                )

        source = self._source_from_expr(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                if source:
                    self.aliases[target.id] = source
                else:
                    self.aliases.pop(target.id, None)

        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        attr = self._json_attr(node.target)
        if attr:
            self.persist_operations.append((node.lineno, attr, "assign"))
        elif not isinstance(node.target, ast.Name):
            self._record_mutation(
                node.target,
                node.lineno,
                "nested assign",
                ast.unparse(node)[:160],
            )

        source = self._source_from_expr(node.value) if node.value else None
        if isinstance(node.target, ast.Name):
            if source:
                self.aliases[node.target.id] = source
            else:
                self.aliases.pop(node.target.id, None)

        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._record_mutation(node.target, node.lineno, "aug assign", ast.unparse(node)[:160])
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "flag_modified"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in JSON_FIELDS
        ):
            self.persist_operations.append(
                (node.lineno, (node.args[0].id, str(node.args[1].value)), "flag_modified")
            )

        if isinstance(node.func, ast.Attribute) and node.func.attr in MUTATING_METHODS:
            self._record_mutation(
                node.func.value,
                node.lineno,
                f"method {node.func.attr}",
                ast.unparse(node)[:160],
            )

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def missing_persistence_messages(self) -> list[str]:
        messages: list[str] = []
        for lineno, alias, field, mode, kind, source in self.mutations:
            has_assignment = any(
                persisted_field == field and operation == "assign"
                for _, persisted_field, operation in self.persist_operations
            )
            has_flag = any(
                persisted_field == field and operation == "flag_modified"
                for _, persisted_field, operation in self.persist_operations
            )
            if has_assignment or (mode == "direct" and has_flag):
                continue

            rel_path = self.path.relative_to(BACKEND_DIR)
            messages.append(
                f"{rel_path}:{lineno} {self.function_name} mutates {alias} "
                f"from {field[0]}.{field[1]} via {kind} without top-level assignment "
                f"or flag_modified: {source}"
            )
        return messages


class FunctionCollector(ast.NodeVisitor):
    def __init__(self, path: Path):
        self.path = path
        self.messages: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scan_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._scan_function(node)

    def _scan_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        scanner = JsonMutationScanner(self.path, node)
        self.messages.extend(scanner.missing_persistence_messages())


def test_sqlalchemy_json_mutations_are_persisted_explicitly():
    messages: list[str] = []
    for source_dir in SOURCE_DIRS:
        for path in source_dir.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            collector = FunctionCollector(path)
            collector.visit(tree)
            messages.extend(collector.messages)

    assert messages == []
