from services.combat_grid_service import (
    ai_move_toward,
    check_attack_range,
    chebyshev_distance,
    has_adjacent_enemy,
    has_ally_adjacent_to,
)


def test_chebyshev_distance_counts_diagonal_as_one_step():
    assert chebyshev_distance({"x": 1, "y": 1}, {"x": 4, "y": 3}) == 3


def test_check_attack_range_rejects_far_melee_target():
    in_range, distance, error = check_attack_range(
        {"x": 1, "y": 1},
        {"x": 4, "y": 1},
        is_ranged=False,
    )

    assert in_range is False
    assert distance == 3
    assert "目标不在近战范围内" in error


def test_ai_move_toward_stops_when_adjacent():
    result = ai_move_toward(
        {"x": 0, "y": 0},
        {"x": 4, "y": 0},
        move_budget=3,
        positions={},
        actor_id="orc",
    )

    assert result == {"x": 3, "y": 0, "steps": 3}


def test_has_adjacent_enemy_ignores_dead_enemies():
    positions = {"hero": {"x": 1, "y": 1}, "dead": {"x": 2, "y": 1}, "alive": {"x": 4, "y": 1}}

    assert has_adjacent_enemy(
        "hero",
        [
            {"id": "dead", "hp_current": 0},
            {"id": "alive", "hp_current": 5},
        ],
        positions,
    ) is False


def test_has_ally_adjacent_to_excludes_attacker():
    positions = {
        "target": {"x": 4, "y": 4},
        "rogue": {"x": 5, "y": 4},
        "fighter": {"x": 8, "y": 8},
    }

    assert has_ally_adjacent_to(
        "target",
        "rogue",
        [
            {"id": "rogue", "hp_current": 8},
            {"id": "fighter", "hp_current": 10},
        ],
        positions,
    ) is False
