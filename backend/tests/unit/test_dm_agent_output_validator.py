from services.graphs.dm_agent_utils import validate_dm_output_adjudication


def test_validator_removes_mechanical_outcomes_while_check_is_pending():
    data = {
        "needs_check": {"required": True, "check_type": "隐匿", "dc": 14},
        "state_delta": {
            "characters": [{"id": "c1", "hp_change": -3}],
            "enemies": [{"id": "e1", "hp_change": -5}],
            "gold_changes": [{"id": "c1", "amount": 20}],
            "trap_triggers": [{"target_character_id": "c1", "trap": {"name": "Dart"}}],
            "combat_trigger": True,
            "combat_end": True,
        },
        "ai_turns": [{"actor_id": "e1"}],
    }

    repaired, warnings = validate_dm_output_adjudication(data, {"combat_active": False})

    assert warnings
    assert repaired["state_delta"]["characters"] == []
    assert repaired["state_delta"]["enemies"] == []
    assert repaired["state_delta"]["gold_changes"] == []
    assert repaired["state_delta"]["trap_triggers"] == []
    assert repaired["state_delta"]["combat_trigger"] is False
    assert repaired["state_delta"]["combat_end"] is False
    assert repaired["ai_turns"] == []
    assert repaired["adjudication_warnings"] == warnings


def test_validator_removes_combat_trigger_when_combat_is_already_active():
    data = {
        "needs_check": {"required": False},
        "state_delta": {
            "characters": [],
            "enemies": [],
            "combat_trigger": True,
            "combat_end": False,
        },
    }

    repaired, warnings = validate_dm_output_adjudication(data, {"combat_active": True})

    assert repaired["state_delta"]["combat_trigger"] is False
    assert "already active" in warnings[0]


def test_validator_preserves_exploration_combat_trigger_with_initial_enemies():
    data = {
        "needs_check": {"required": False},
        "state_delta": {
            "characters": [],
            "enemies": [],
            "combat_trigger": True,
            "initial_enemies": [{"name": "Goblin", "hp": 7}],
            "combat_end": False,
        },
    }

    repaired, warnings = validate_dm_output_adjudication(data, {"combat_active": False})

    assert warnings == []
    assert repaired["state_delta"]["combat_trigger"] is True
    assert "adjudication_warnings" not in repaired


def test_validator_removes_enemy_delta_outside_combat_without_trigger():
    data = {
        "needs_check": {"required": False},
        "state_delta": {
            "characters": [],
            "enemies": [{"id": "e1", "hp_change": -99}],
            "combat_trigger": False,
            "combat_end": False,
        },
    }

    repaired, warnings = validate_dm_output_adjudication(data, {"combat_active": False})

    assert repaired["state_delta"]["enemies"] == []
    assert any("outside combat" in warning for warning in warnings)
