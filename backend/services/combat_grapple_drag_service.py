from __future__ import annotations

from typing import Any

from services.dnd_rules import normalize_condition


BLOCKING_TERRAIN = {
    "wall",
    "cover",
    "half_cover",
    "three_quarters_cover",
    "total_cover",
    "blocked",
    "blocking",
    "blocker",
    "impassable",
    "opaque",
}


def build_grapple_drag_result(
    *,
    actor_id: str,
    actor_from: dict[str, Any] | None,
    actor_to: dict[str, Any] | None,
    positions: dict[str, Any] | None,
    targets: list[dict[str, Any]] | None,
    grid_data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not actor_from or not actor_to:
        return None
    dx = _coord(actor_to, "x") - _coord(actor_from, "x")
    dy = _coord(actor_to, "y") - _coord(actor_from, "y")
    distance = max(abs(dx), abs(dy))
    if distance <= 0:
        return None

    all_positions = {str(key): value for key, value in dict(positions or {}).items()}
    dragged = [
        target for target in (targets or [])
        if _is_grappled_by(target, actor_id)
        and _is_adjacent(actor_from, all_positions.get(str(target.get("id"))))
    ]
    if not dragged:
        return None

    width, height = _grid_dimensions(grid_data or {})
    dragged_ids = {str(target.get("id")) for target in dragged}
    occupied = {
        (_coord(position, "x"), _coord(position, "y"))
        for entity_id, position in all_positions.items()
        if str(entity_id) not in dragged_ids and str(entity_id) != str(actor_id)
    }
    planned_destinations: set[tuple[int, int]] = set()
    target_results: list[dict[str, Any]] = []

    for target in dragged:
        target_id = str(target.get("id"))
        current = all_positions.get(target_id)
        if not current:
            continue
        destination = {
            "x": _coord(current, "x") + dx,
            "y": _coord(current, "y") + dy,
        }
        blocked_reason = _drag_blocked_reason(
            destination=destination,
            width=width,
            height=height,
            occupied=occupied | planned_destinations,
            grid_data=grid_data or {},
        )
        target_result = {
            "target_id": target_id,
            "target_name": target.get("name") or "Target",
            "from": {"x": _coord(current, "x"), "y": _coord(current, "y")},
            "to": destination,
            "distance_ft": distance * 5,
            "steps": distance,
            "applied": blocked_reason is None,
        }
        if blocked_reason:
            target_result["blocked_reason"] = blocked_reason
            return {
                "type": "grapple_drag",
                "actor_id": str(actor_id),
                "distance_ft": distance * 5,
                "steps": distance,
                "movement_cost": distance * 2,
                "targets": [target_result],
                "applied": False,
                "blocked_reason": blocked_reason,
            }
        planned_destinations.add((destination["x"], destination["y"]))
        target_results.append(target_result)

    if not target_results:
        return None
    return {
        "type": "grapple_drag",
        "actor_id": str(actor_id),
        "distance_ft": distance * 5,
        "steps": distance,
        "movement_cost": distance * 2,
        "targets": target_results,
        "applied": True,
    }


def apply_grapple_drag_positions(
    positions: dict[str, Any],
    drag_result: dict[str, Any] | None,
) -> dict[str, Any]:
    if not drag_result or not drag_result.get("applied"):
        return positions
    updated = dict(positions or {})
    for target in drag_result.get("targets") or []:
        if not target.get("applied"):
            continue
        updated[str(target["target_id"])] = dict(target["to"])
    return updated


def _is_grappled_by(target: dict[str, Any], actor_id: str) -> bool:
    conditions = [normalize_condition(item) for item in target.get("conditions") or []]
    if "grappled" not in conditions:
        return False
    metadata = _condition_metadata(target.get("condition_durations") or {}, "grappled")
    source_id = metadata.get("source_id") or metadata.get("sourceId") or metadata.get("source")
    return source_id is not None and str(source_id) == str(actor_id)


def _condition_metadata(durations: dict[str, Any], condition: str) -> dict[str, Any]:
    canonical = normalize_condition(condition)
    for key, value in (durations or {}).items():
        if normalize_condition(str(key)) != canonical:
            continue
        return dict(value) if isinstance(value, dict) else {"source_id": value}
    return {}


def _is_adjacent(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    if not a or not b:
        return False
    return max(abs(_coord(a, "x") - _coord(b, "x")), abs(_coord(a, "y") - _coord(b, "y"))) <= 1


def _drag_blocked_reason(
    *,
    destination: dict[str, int],
    width: int,
    height: int,
    occupied: set[tuple[int, int]],
    grid_data: dict[str, Any],
) -> str | None:
    x = destination["x"]
    y = destination["y"]
    if not (0 <= x < width and 0 <= y < height):
        return "out_of_bounds"
    if (x, y) in occupied:
        return "occupied"
    if _is_blocking_terrain(grid_data, destination):
        return "blocked_terrain"
    return None


def _is_blocking_terrain(grid_data: dict[str, Any], position: dict[str, int]) -> bool:
    cell = grid_data.get(f"{position['x']}_{position['y']}")
    if isinstance(cell, dict):
        terrain = cell.get("terrain") or cell.get("type") or cell.get("kind") or ""
    else:
        terrain = str(cell or "")
    return terrain.strip().lower() in BLOCKING_TERRAIN


def _grid_dimensions(grid_data: dict[str, Any]) -> tuple[int, int]:
    try:
        return int(grid_data.get("width") or 20), int(grid_data.get("height") or 12)
    except (TypeError, ValueError):
        return 20, 12


def _coord(position: dict[str, Any], key: str) -> int:
    return int(position.get(key, 0) or 0)
