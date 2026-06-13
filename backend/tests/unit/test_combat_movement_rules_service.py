import pytest

from services.combat_movement_rules_service import (
    MovementRuleError,
    apply_stand_up_from_prone,
    has_condition_alias,
    movement_is_speed_zero,
    remove_condition_alias,
    validate_displacement_allowed,
    validate_frightened_movement,
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


def test_apply_stand_up_from_prone_rejects_speed_zero_conditions():
    with pytest.raises(MovementRuleError) as exc:
        apply_stand_up_from_prone(
            {"movement_used": 0, "movement_max": 6, "base_movement_max": 6},
            ["prone", "grappled"],
        )

    assert str(exc.value) == "speed_zero_condition_blocks_standing"


@pytest.mark.parametrize("condition", ["grappled", "restrained", "被擒抱", "束缚"])
def test_speed_zero_conditions_block_displacement(condition):
    assert movement_is_speed_zero([condition]) is True
    with pytest.raises(MovementRuleError) as exc:
        validate_displacement_allowed([condition], 1)

    assert str(exc.value) == "speed_zero_condition_blocks_movement"


def test_exhaustion_level_5_blocks_displacement():
    durations = {"exhaustion_level": 5}

    assert movement_is_speed_zero(["exhaustion"], durations) is True
    with pytest.raises(MovementRuleError) as exc:
        validate_displacement_allowed(["exhaustion"], 1, durations)

    assert str(exc.value) == "speed_zero_condition_blocks_movement"


def test_exhaustion_level_5_blocks_standing_from_prone():
    with pytest.raises(MovementRuleError) as exc:
        apply_stand_up_from_prone(
            {"movement_used": 0, "movement_max": 6, "base_movement_max": 6},
            ["prone", "exhaustion"],
            {"exhaustion_level": 5},
        )

    assert str(exc.value) == "speed_zero_condition_blocks_standing"


def test_validate_displacement_allows_no_op_for_speed_zero_condition():
    validate_displacement_allowed(["grappled"], 0)


def test_condition_alias_helpers_preserve_unrelated_raw_conditions():
    assert has_condition_alias(["倒地"], "prone") is True
    assert remove_condition_alias(["倒地", "custom_mark"], "prone") == ["custom_mark"]


def test_frightened_movement_blocks_approaching_source_by_id():
    with pytest.raises(MovementRuleError) as exc:
        validate_frightened_movement(
            ["frightened"],
            {"frightened": {"duration": 2, "source_id": "enemy-1"}},
            {"x": 5, "y": 5},
            {"x": 6, "y": 5},
            {"enemy-1": {"x": 8, "y": 5}},
        )

    assert str(exc.value) == "frightened_source_blocks_approach"


def test_frightened_movement_allows_lateral_or_retreat_from_source():
    validate_frightened_movement(
        ["frightened"],
        {"frightened": {"duration": 2, "source_position": {"x": 8, "y": 5}}},
        {"x": 5, "y": 5},
        {"x": 5, "y": 6},
        {},
    )
    validate_frightened_movement(
        ["frightened"],
        {"frightened_source_id": "enemy-1"},
        {"x": 5, "y": 5},
        {"x": 4, "y": 5},
        {"enemy-1": {"x": 8, "y": 5}},
    )
