from services.combat_legendary_action_service import (
    initialize_legendary_actions,
    normalize_legendary_action_uses,
    normalize_legendary_actions,
    refresh_legendary_actions_for_new_round,
    refresh_legendary_actions_for_turn_start,
    spend_legendary_action,
)


def test_normalize_legendary_actions_accepts_dicts_and_strings():
    actions = normalize_legendary_actions([
        {"name": "Tail Attack", "cost": 2, "description": "Tail sweep."},
        "Detect",
    ])

    assert actions[0]["id"] == "legendary_tail_attack"
    assert actions[0]["cost"] == 2
    assert actions[1]["id"] == "legendary_detect"
    assert actions[1]["cost"] == 1


def test_initialize_legendary_actions_defaults_to_three_uses_when_actions_exist():
    enemy = {"legendary_actions": [{"name": "Tail Attack"}]}

    state = initialize_legendary_actions(enemy)

    assert state == {"uses": 3, "remaining": 3}
    assert enemy["legendary_action_uses"] == 3
    assert enemy["legendary_action_uses_remaining"] == 3


def test_initialize_legendary_actions_reads_explicit_remaining_and_uses():
    enemy = {
        "legendary_actions": [{"name": "Wing Attack", "cost": "2 actions"}],
        "legendary_actions_per_round": "4/round",
        "legendary_action_uses_remaining": 2,
    }

    state = initialize_legendary_actions(enemy)

    assert normalize_legendary_action_uses("4/round") == 4
    assert state == {"uses": 4, "remaining": 2}
    assert enemy["legendary_actions"][0]["cost"] == 2


def test_refresh_legendary_actions_for_new_round_restores_surviving_enemy_pool():
    enemies = [
        {
            "id": "dragon-1",
            "name": "Dragon",
            "hp_current": 100,
            "legendary_actions": [{"name": "Detect"}],
            "legendary_action_uses": 3,
            "legendary_action_uses_remaining": 0,
        },
        {
            "id": "dead-1",
            "name": "Dead Boss",
            "hp_current": 0,
            "legendary_actions": [{"name": "Detect"}],
            "legendary_action_uses": 3,
            "legendary_action_uses_remaining": 0,
        },
    ]

    result = refresh_legendary_actions_for_new_round(enemies)

    assert result == {"changed": True, "refreshed": [{"enemy_id": "dragon-1", "name": "Dragon", "uses": 3}]}
    assert enemies[0]["legendary_action_uses_remaining"] == 3
    assert enemies[1]["legendary_action_uses_remaining"] == 0


def test_refresh_legendary_actions_for_turn_start_restores_only_actor_pool():
    enemy = {
        "id": "dragon-1",
        "name": "Dragon",
        "hp_current": 100,
        "legendary_actions": [{"name": "Detect"}],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 1,
    }

    result = refresh_legendary_actions_for_turn_start(enemy)

    assert result == {"changed": True, "refreshed": {"enemy_id": "dragon-1", "name": "Dragon", "uses": 3}}
    assert enemy["legendary_action_uses_remaining"] == 3


def test_spend_legendary_action_checks_cost_and_remaining_pool():
    enemy = {
        "legendary_actions": [
            {"id": "tail", "name": "Tail Attack", "cost": 2},
            {"id": "detect", "name": "Detect", "cost": 1},
        ],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 2,
    }

    spent = spend_legendary_action(enemy, "tail")
    failed = spend_legendary_action(enemy, "tail")

    assert spent["spent"] is True
    assert spent["remaining"] == 0
    assert failed["spent"] is False
    assert failed["reason"] == "insufficient_uses"
