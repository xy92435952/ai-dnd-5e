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


def movement_is_speed_zero(conditions: list[str] | None) -> bool:
    return has_speed_zero_condition({"conditions": list(conditions or [])})


def validate_displacement_allowed(conditions: list[str] | None, distance: int) -> None:
    if distance <= 0:
        return
    if movement_is_speed_zero(conditions):
        raise MovementRuleError("speed_zero_condition_blocks_movement")


def apply_stand_up_from_prone(
    turn_state: dict[str, Any],
    conditions: list[str] | None,
) -> StandUpResult:
    """Apply 5e standing-up cost if the creature is prone."""
    updated_turn_state = dict(turn_state or {})
    current_conditions = list(conditions or [])
    if not has_condition_alias(current_conditions, "prone"):
        return StandUpResult(
            turn_state=updated_turn_state,
            conditions=current_conditions,
        )
    if movement_is_speed_zero(current_conditions):
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
