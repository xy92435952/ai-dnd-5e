from __future__ import annotations

import math
from typing import Any

from services.combat_tactical_service import DIFFICULT_TERRAIN, terrain_kind


def build_movement_path_cells(
    from_pos: dict[str, Any] | None,
    to_pos: dict[str, Any] | None,
) -> list[dict[str, int | str]]:
    if not from_pos or not to_pos:
        return []
    try:
        ax = int(from_pos["x"])
        ay = int(from_pos["y"])
        tx = int(to_pos["x"])
        ty = int(to_pos["y"])
    except (KeyError, TypeError, ValueError):
        return []

    dx = tx - ax
    dy = ty - ay
    steps = max(abs(dx), abs(dy))
    if steps <= 0:
        return []

    cells: list[dict[str, int | str]] = []
    seen: set[str] = set()
    for index in range(1, steps + 1):
        cx = ax + _round_like_js(dx * index / steps)
        cy = ay + _round_like_js(dy * index / steps)
        key = f"{cx}_{cy}"
        if key in seen:
            continue
        seen.add(key)
        cells.append({"cell": key, "x": cx, "y": cy})
    return cells


def build_movement_cost_breakdown(
    grid_data: dict[str, Any] | None,
    from_pos: dict[str, Any] | None,
    to_pos: dict[str, Any] | None,
    *,
    base_cost: int | None = None,
) -> dict[str, Any]:
    path = build_movement_path_cells(from_pos, to_pos)
    base = max(0, int(base_cost if base_cost is not None else len(path) or 0))
    terrain = dict(grid_data or {})
    difficult_cells: list[dict[str, Any]] = []

    for cell in path:
        key = str(cell["cell"])
        value = terrain.get(key, "")
        kind = terrain_kind(value)
        if kind not in DIFFICULT_TERRAIN:
            continue
        difficult_cells.append({
            "cell": key,
            "terrain": kind,
            "label": _terrain_label(value, kind),
            "extra_cost": 1,
        })

    difficult_extra = sum(int(cell.get("extra_cost", 1) or 1) for cell in difficult_cells)
    return {
        "steps": len(path),
        "base_cost": base,
        "movement_cost": base + difficult_extra,
        "difficult_terrain_extra": difficult_extra,
        "difficult_terrain_cells": difficult_cells,
        "path": path,
    }


def _terrain_label(value: Any, terrain: str) -> str:
    if isinstance(value, dict):
        return str(
            value.get("name")
            or value.get("label")
            or value.get("title")
            or _default_label(terrain)
        )
    return _default_label(terrain)


def _default_label(terrain: str) -> str:
    return "Difficult terrain" if terrain in DIFFICULT_TERRAIN else str(terrain or "Terrain")


def _round_like_js(value: float) -> int:
    return math.floor(value + 0.5)
