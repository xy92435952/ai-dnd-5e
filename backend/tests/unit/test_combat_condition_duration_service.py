from types import SimpleNamespace

from services.combat_condition_duration_service import (
    tick_character_conditions,
    tick_enemy_conditions,
)


def test_tick_character_conditions_removes_expired_condition():
    char = SimpleNamespace(
        conditions=["poisoned", "blinded"],
        condition_durations={"poisoned": 1, "blinded": 2},
        class_resources={
            "condition_sources": {
                "poisoned": [{"caster_id": "caster-1"}],
                "blinded": [{"caster_id": "caster-2"}],
            },
        },
    )

    removed = tick_character_conditions(char)

    assert removed == ["poisoned"]
    assert char.conditions == ["blinded"]
    assert char.condition_durations == {"blinded": 1}
    assert char.class_resources["condition_sources"] == {
        "blinded": [{"caster_id": "caster-2"}],
    }


def test_tick_enemy_conditions_updates_enemy_dict():
    enemy = {
        "conditions": ["restrained", "frightened"],
        "condition_durations": {"restrained": 1, "frightened": 3},
        "condition_sources": {
            "restrained": [{"caster_id": "caster-1"}],
            "frightened": [{"caster_id": "caster-2"}],
        },
    }

    removed = tick_enemy_conditions(enemy)

    assert removed == ["restrained"]
    assert enemy["conditions"] == ["frightened"]
    assert enemy["condition_durations"] == {"frightened": 2}
    assert enemy["condition_sources"] == {
        "frightened": [{"caster_id": "caster-2"}],
    }
