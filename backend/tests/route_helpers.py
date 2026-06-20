from __future__ import annotations

from collections.abc import Iterable
from types import SimpleNamespace


def iter_effective_routes(router) -> Iterable[object]:
    """Yield concrete route-like objects across FastAPI router internals.

    FastAPI 0.138 can keep included routers as nested route containers in
    ``.routes``. Tests that assert public API contracts should inspect the
    concrete/effective routes instead of depending on that storage detail.
    """
    seen: set[tuple[str, tuple[str, ...]]] = set()
    yield from _iter_effective_routes(router, seen)


def _iter_effective_routes(router, seen: set[tuple[str, tuple[str, ...]]]) -> Iterable[object]:
    for route in getattr(router, "routes", []):
        yield from _iter_effective_route(route, seen)


def _iter_effective_route(route, seen: set[tuple[str, tuple[str, ...]]]) -> Iterable[object]:
    yielded = False
    for candidate in getattr(route, "_effective_candidates", None) or []:
        candidate_route = getattr(candidate, "original_route", candidate)
        candidate_path = getattr(candidate, "path", None)
        candidate_methods = getattr(candidate, "methods", None)
        if candidate_methods is None:
            candidate_methods = getattr(candidate_route, "methods", None)
        if candidate_path is None:
            candidate_path = getattr(candidate_route, "path", None)
        if candidate_path is not None and candidate_methods is not None:
            yielded = True
            yield from _yield_unique_route(
                SimpleNamespace(path=candidate_path, methods=candidate_methods),
                seen,
            )
        else:
            nested_router = getattr(candidate_route, "original_router", None)
            if nested_router is not None:
                yielded = True
                yield from _iter_effective_routes(nested_router, seen)

    if yielded:
        return

    path = getattr(route, "path", None)
    methods = getattr(route, "methods", None)
    if path is not None and methods is not None:
        yield from _yield_unique_route(route, seen)
        return

    included_router = getattr(route, "original_router", None)
    if included_router is not None:
        yield from _iter_effective_routes(included_router, seen)


def _yield_unique_route(route, seen: set[tuple[str, tuple[str, ...]]]) -> Iterable[object]:
    methods = getattr(route, "methods", set()) or set()
    key = (getattr(route, "path", ""), tuple(sorted(methods)))
    if key in seen:
        return
    seen.add(key)
    yield route
