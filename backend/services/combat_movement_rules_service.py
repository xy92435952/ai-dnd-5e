from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.dnd_rules import (
    has_speed_zero_condition,
    normalize_condition,
    normalize_conditions,
)


class MovementRuleError(Exception):
    """Raised when a movement rule cannot be satisfied."""


@dataclass
class StandUpResult:
    turn_state: dict[str, Any]
    conditions: list[str]
    stood_up: bool = False
    movement_cost: int = 0


def remove_condition_alias(conditions: list[str] | None, condition: str) -> list[str]:
    """Remove a condition by canonical meaning, preserving unrelated raw condition names."""
    canonical = normalize_condition(condition)
    return [
        item
        for item in (conditions or [])
        if normalize_condition(item) != canonical
    ]


def has_condition_alias(conditions: list[str] | None, condition: str) -> bool:
    return normalize_condition(condition) in normalize_conditions(conditions or [])


def movement_is_speed_zero(
    conditions: list[str] | None,
    condition_durations: dict[str, Any] | None = None,
) -> bool:
    return has_speed_zero_condition(
        {
            "conditions": list(conditions or []),
            "condition_durations": dict(condition_durations or {}),
        }
    )


def validate_displacement_allowed(
    conditions: list[str] | None,
    distance: int,
    condition_durations: dict[str, Any] | None = None,
) -> None:
    if distance <= 0:
        return
    if movement_is_speed_zero(conditions, condition_durations):
        raise MovementRuleError("speed_zero_condition_blocks_movement")


def validate_frightened_movement(
    conditions: list[str] | None,
    condition_durations: dict[str, Any] | None,
    old_pos: dict[str, Any] | None,
    new_pos: dict[str, Any] | None,
    positions: dict[str, Any] | None,
) -> None:
    """Reject voluntary movement that moves a frightened creature closer to its source."""
    if not has_condition_alias(conditions or [], "frightened"):
        return
    if not old_pos or not new_pos:
        return
    for source_pos in _frightened_source_positions(condition_durations or {}, positions or {}):
        old_dist = _grid_distance(old_pos, source_pos)
        new_dist = _grid_distance(new_pos, source_pos)
        if old_dist is not None and new_dist is not None and new_dist < old_dist:
            raise MovementRuleError("frightened_source_blocks_approach")


def apply_stand_up_from_prone(
    turn_state: dict[str, Any],
    conditions: list[str] | None,
    condition_durations: dict[str, Any] | None = None,
) -> StandUpResult:
    """Apply 5e standing-up cost if the creature is prone."""
    updated_turn_state = dict(turn_state or {})
    current_conditions = list(conditions or [])
    if not has_condition_alias(current_conditions, "prone"):
        return StandUpResult(
            turn_state=updated_turn_state,
            conditions=current_conditions,
        )
    if movement_is_speed_zero(current_conditions, condition_durations):
        raise MovementRuleError("speed_zero_condition_blocks_standing")

    movement_max = max(0, int(updated_turn_state.get("movement_max", 0) or 0))
    base_movement_max = max(0, int(updated_turn_state.get("base_movement_max", movement_max) or 0))
    movement_used = max(0, int(updated_turn_state.get("movement_used", 0) or 0))
    stand_cost = max(1, base_movement_max // 2) if base_movement_max > 0 else 0
    remaining = movement_max - movement_used
    if stand_cost <= 0 or remaining < stand_cost:
        raise MovementRuleError("not_enough_movement_to_stand")

    updated_turn_state["movement_used"] = movement_used + stand_cost
    return StandUpResult(
        turn_state=updated_turn_state,
        conditions=remove_condition_alias(current_conditions, "prone"),
        stood_up=True,
        movement_cost=stand_cost,
    )


def _frightened_source_positions(
    condition_durations: dict[str, Any],
    positions: dict[str, Any],
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    entries = [_duration_entry(condition_durations, "frightened")]
    for key in ("frightened_source", "frightened_source_position", "frightened_source_id"):
        if key in condition_durations:
            entries.append(condition_durations.get(key))

    for entry in entries:
        if isinstance(entry, dict):
            source_position = entry.get("source_position") or entry.get("sourcePosition")
            if isinstance(source_position, dict):
                sources.append(source_position)
            source_ids = entry.get("source_ids") or entry.get("sourceIds")
            if not isinstance(source_ids, list):
                source_ids = [entry.get("source_id") or entry.get("sourceId")]
            for source_id in source_ids:
                if source_id is not None and str(source_id) in positions:
                    sources.append(positions[str(source_id)])
        elif entry is not None and str(entry) in positions:
            sources.append(positions[str(entry)])

    unique = []
    seen = set()
    for source in sources:
        key = (source.get("x"), source.get("y"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique


def _duration_entry(condition_durations: dict[str, Any], condition: str) -> Any:
    canonical = normalize_condition(condition)
    for key, value in condition_durations.items():
        if normalize_condition(str(key)) == canonical:
            return value
    return None


def _grid_distance(a: dict[str, Any], b: dict[str, Any]) -> int | None:
    try:
        return max(abs(int(a["x"]) - int(b["x"])), abs(int(a["y"]) - int(b["y"])))
    except (KeyError, TypeError, ValueError):
        return None
