from __future__ import annotations

import re
from pathlib import Path

from main import app
from tests.route_helpers import iter_effective_routes


ROOT_DIR = Path(__file__).resolve().parents[3]
FRONTEND_CLIENT = ROOT_DIR / "frontend" / "src" / "api" / "client.js"


def _normalize_route(path: str) -> str:
    path = path.split("?", 1)[0]
    path = re.sub(r"\$\{[^}]+\}", "{param}", path)
    path = re.sub(r"\{[^}/]+\}", "{param}", path)
    return path.rstrip("/") or "/"


def _frontend_routes() -> set[tuple[str, str]]:
    source = FRONTEND_CLIENT.read_text(encoding="utf-8")
    routes: set[tuple[str, str]] = set()
    for match in re.finditer(r"api\.(get|post|patch|put|delete)\(\s*([`'])(/[^`']+)\2", source):
        method = match.group(1).upper()
        path = _normalize_route(match.group(3))
        routes.add((method, path))
    return routes


def _backend_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for route in iter_effective_routes(app):
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        for method in methods:
            if method in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
                routes.add((method, _normalize_route(path)))
    return routes


def test_frontend_http_client_routes_exist_on_backend():
    missing = sorted(_frontend_routes() - _backend_routes())

    assert missing == []
