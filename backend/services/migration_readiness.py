"""Offline readiness checks for moving local SQLite data to PostgreSQL."""

from __future__ import annotations

import ast
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import JSON, MetaData
from sqlalchemy.engine import make_url


ERROR = "error"


@dataclass(frozen=True)
class MigrationReadinessIssue:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class MigrationReadinessReport:
    sqlite_path: Path
    target_url: str
    issues: tuple[MigrationReadinessIssue, ...]

    @property
    def ok(self) -> bool:
        return not any(issue.severity == ERROR for issue in self.issues)


def check_sqlite_to_postgres_readiness(
    *,
    sqlite_path: str | Path,
    target_database_url: str,
    metadata: MetaData,
    alembic_versions_dir: str | Path | None = None,
) -> MigrationReadinessReport:
    """Check the local migration path without mutating either database."""
    source_path = Path(sqlite_path)
    issues: list[MigrationReadinessIssue] = []

    if not _is_postgres_url(target_database_url):
        issues.append(
            MigrationReadinessIssue(
                ERROR,
                "target_not_postgres",
                "DATABASE_URL must point to PostgreSQL for SQLite -> PostgreSQL migration.",
            )
        )

    if not source_path.exists():
        issues.append(
            MigrationReadinessIssue(
                ERROR,
                "sqlite_missing",
                f"SQLite source database does not exist: {source_path}",
            )
        )
    elif not source_path.is_file():
        issues.append(
            MigrationReadinessIssue(
                ERROR,
                "sqlite_not_file",
                f"SQLite source path is not a file: {source_path}",
            )
        )
    else:
        issues.extend(_check_sqlite_schema(source_path, metadata))

    if alembic_versions_dir is not None:
        issues.extend(_check_alembic_revision_chain(Path(alembic_versions_dir)))

    return MigrationReadinessReport(
        sqlite_path=source_path,
        target_url=_mask_database_url(target_database_url),
        issues=tuple(issues),
    )


def format_readiness_report(report: MigrationReadinessReport) -> str:
    status = "READY" if report.ok else "NOT READY"
    lines = [
        f"SQLite -> PostgreSQL migration readiness: {status}",
        f"Source SQLite: {report.sqlite_path}",
        f"Target URL: {report.target_url}",
    ]
    if not report.issues:
        lines.append("No readiness issues found.")
        return "\n".join(lines)

    for issue in report.issues:
        lines.append(f"[{issue.severity.upper()}] {issue.code}: {issue.message}")
    return "\n".join(lines)


def _is_postgres_url(database_url: str) -> bool:
    try:
        driver = make_url(database_url).drivername
    except Exception:
        return False
    return driver.startswith("postgresql")


def _mask_database_url(database_url: str) -> str:
    try:
        return make_url(database_url).render_as_string(hide_password=True)
    except Exception:
        return database_url


def _check_sqlite_schema(sqlite_path: Path, metadata: MetaData) -> list[MigrationReadinessIssue]:
    issues: list[MigrationReadinessIssue] = []
    expected_tables = {
        table.name: {column.name for column in table.columns}
        for table in metadata.sorted_tables
    }
    json_columns = _metadata_json_columns(metadata)

    try:
        conn = sqlite3.connect(sqlite_path)
    except sqlite3.Error as exc:
        return [
            MigrationReadinessIssue(
                ERROR,
                "sqlite_open_failed",
                f"Could not open SQLite database {sqlite_path}: {exc}",
            )
        ]

    try:
        existing_tables = _sqlite_tables(conn)
        for table_name, expected_columns in expected_tables.items():
            if table_name not in existing_tables:
                issues.append(
                    MigrationReadinessIssue(
                        ERROR,
                        "missing_table",
                        f"SQLite database is missing table '{table_name}'.",
                    )
                )
                continue

            existing_columns = _sqlite_columns(conn, table_name)
            missing_columns = sorted(expected_columns - existing_columns)
            for column_name in missing_columns:
                issues.append(
                    MigrationReadinessIssue(
                        ERROR,
                        "missing_column",
                        f"SQLite database is missing model column '{table_name}.{column_name}'.",
                    )
                )

        issues.extend(_check_json_values(conn, existing_tables, json_columns))
    finally:
        conn.close()

    return issues


def _metadata_json_columns(metadata: MetaData) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for table in metadata.sorted_tables:
        columns = {
            column.name
            for column in table.columns
            if isinstance(column.type, JSON)
        }
        if columns:
            result[table.name] = columns
    return result


def _sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _sqlite_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()
    return {str(row[1]) for row in rows}


def _check_json_values(
    conn: sqlite3.Connection,
    existing_tables: set[str],
    json_columns: dict[str, set[str]],
) -> list[MigrationReadinessIssue]:
    issues: list[MigrationReadinessIssue] = []
    for table_name, columns in json_columns.items():
        if table_name not in existing_tables:
            continue
        existing_columns = _sqlite_columns(conn, table_name)
        for column_name in sorted(columns & existing_columns):
            sql = (
                f"SELECT rowid, {_quote_identifier(column_name)} "
                f"FROM {_quote_identifier(table_name)} "
                f"WHERE {_quote_identifier(column_name)} IS NOT NULL"
            )
            for rowid, value in conn.execute(sql):
                if isinstance(value, bytes):
                    value = value.decode("utf-8")
                if not isinstance(value, str):
                    continue
                try:
                    json.loads(value)
                except (TypeError, json.JSONDecodeError):
                    issues.append(
                        MigrationReadinessIssue(
                            ERROR,
                            "invalid_json",
                            (
                                f"SQLite JSON column '{table_name}.{column_name}' has "
                                f"invalid JSON at rowid {rowid}."
                            ),
                        )
                    )
    return issues


def _check_alembic_revision_chain(versions_dir: Path) -> list[MigrationReadinessIssue]:
    if not versions_dir.exists():
        return [
            MigrationReadinessIssue(
                ERROR,
                "alembic_versions_missing",
                f"Alembic versions directory does not exist: {versions_dir}",
            )
        ]

    revision_map: dict[str, tuple[str | None, Path]] = {}
    issues: list[MigrationReadinessIssue] = []
    for path in sorted(versions_dir.glob("*.py")):
        revision, down_revision = _read_alembic_revision(path)
        if not revision:
            issues.append(
                MigrationReadinessIssue(
                    ERROR,
                    "alembic_revision_missing",
                    f"Alembic file has no revision id: {path.name}",
                )
            )
            continue
        if revision in revision_map:
            issues.append(
                MigrationReadinessIssue(
                    ERROR,
                    "alembic_revision_duplicate",
                    f"Alembic revision '{revision}' is duplicated.",
                )
            )
        revision_map[revision] = (down_revision, path)

    if not revision_map:
        issues.append(
            MigrationReadinessIssue(
                ERROR,
                "alembic_no_revisions",
                f"No Alembic revisions found in {versions_dir}",
            )
        )
        return issues

    down_revisions = {
        down_revision
        for down_revision, _ in revision_map.values()
        if down_revision is not None
    }
    for down_revision in sorted(down_revisions):
        if down_revision not in revision_map:
            issues.append(
                MigrationReadinessIssue(
                    ERROR,
                    "alembic_broken_chain",
                    f"Alembic down_revision '{down_revision}' is not present in versions.",
                )
            )

    heads = sorted(set(revision_map) - down_revisions)
    if len(heads) != 1:
        issues.append(
            MigrationReadinessIssue(
                ERROR,
                "alembic_head_count",
                f"Alembic should have exactly one head revision, found {len(heads)}: {heads}",
            )
        )

    return issues


def _read_alembic_revision(path: Path) -> tuple[str | None, str | None]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assignments: dict[str, object] = {}
    for node in tree.body:
        target_name = _assignment_name(node)
        if target_name not in {"revision", "down_revision"}:
            continue
        value = _assignment_value(node)
        try:
            assignments[target_name] = ast.literal_eval(value) if value is not None else None
        except (TypeError, ValueError):
            assignments[target_name] = None

    revision = assignments.get("revision")
    down_revision = assignments.get("down_revision")
    return (
        revision if isinstance(revision, str) else None,
        down_revision if isinstance(down_revision, str) else None,
    )


def _assignment_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        return target.id if isinstance(target, ast.Name) else None
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _assignment_value(node: ast.AST) -> ast.AST | None:
    if isinstance(node, ast.Assign):
        return node.value
    if isinstance(node, ast.AnnAssign):
        return node.value
    return None


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
