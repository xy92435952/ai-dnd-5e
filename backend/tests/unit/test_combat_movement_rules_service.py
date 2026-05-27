import pytest

from services.combat_movement_rules_service import (
    MovementRuleError,
    apply_stand_up_from_prone,
    has_condition_alias,
    remove_condition_alias,
)


def test_apply_stand_up_from_prone_costs_half_base_movement_and_removes_condition():
    result = apply_stand_up_from_prone(
        {"movement_used": 1, "movement_max": 12, "base_movement_max": 6},
        ["prone", "poisoned"],
    )

    assert result.stood_up is True
    assert result.movement_cost == 3
    assert result.turn_state["movement_used"] == 4
    assert result.conditions == ["poisoned"]


def test_apply_stand_up_from_prone_accepts_chinese_prone_alias():
    result = apply_stand_up_from_prone(
        {"movement_used": 0, "movement_max": 6},
        ["倒地"],
    )

    assert result.stood_up is True
    assert result.movement_cost == 3
    assert result.turn_state["movement_used"] == 3
    assert result.conditions == []


def test_apply_stand_up_from_prone_rejects_insufficient_movement():
    with pytest.raises(MovementRuleError):
        apply_stand_up_from_prone(
            {"movement_used": 4, "movement_max": 6},
            ["prone"],
        )


def test_condition_alias_helpers_preserve_unrelated_raw_conditions():
    assert has_condition_alias(["倒地"], "prone") is True
    assert remove_condition_alias(["倒地", "custom_mark"], "prone") == ["custom_mark"]
