from types import SimpleNamespace

from services.combat_repeat_save_service import (
    build_repeat_save_condition_metadata,
    resolve_repeat_save_end_of_turn_saves,
)


def test_repeat_save_end_of_turn_success_removes_paralyzed():
    actor = {
        "id": "target-1",
        "name": "Held Guard",
        "conditions": ["paralyzed"],
        "condition_durations": {
            "paralyzed": {
                "duration": 10,
                "repeat_save": "end_of_turn",
                "save_ability": "wis",
                "save_dc": 12,
                "end_save_d20": 20,
                "spell_name": "Hold Person",
            },
        },
        "derived": {"saving_throws": {"wis": 0}},
    }

    results = resolve_repeat_save_end_of_turn_saves(actor, entity_id="target-1", actor_name="Held Guard")

    assert len(results) == 1
    result = results[0]
    assert result["type"] == "condition_end_save"
    assert result["condition"] == "paralyzed"
    assert result["ended"] is True
    assert result["removed_conditions"] == ["paralyzed"]
    assert actor["conditions"] == []
    assert actor["condition_durations"] == {}
    assert result["target_state"]["conditions"] == []


def test_repeat_save_end_of_turn_failure_keeps_blinded():
    actor = {
        "id": "target-1",
        "name": "Blinded Guard",
        "conditions": ["blinded"],
        "condition_durations": {
            "blinded": {
                "duration": 10,
                "repeat_save": "end_of_turn",
                "save_ability": "con",
                "save_dc": 15,
                "end_save_d20": 5,
                "spell_name": "Blindness/Deafness",
            },
        },
        "derived": {"saving_throws": {"con": 0}},
    }

    results = resolve_repeat_save_end_of_turn_saves(actor, entity_id="target-1", actor_name="Blinded Guard")

    assert len(results) == 1
    assert results[0]["ended"] is False
    assert results[0]["save"]["success"] is False
    assert actor["conditions"] == ["blinded"]
    assert actor["condition_durations"]["blinded"]["duration"] == 10


def test_repeat_save_can_spend_bardic_inspiration_to_end_condition():
    actor = SimpleNamespace(
        id="target-1",
        name="Inspired Guard",
        conditions=["blinded"],
        condition_durations={
            "blinded": {
                "duration": 10,
                "repeat_save": "end_of_turn",
                "save_ability": "con",
                "save_dc": 15,
                "end_save_d20": 11,
                "spell_name": "Blindness/Deafness",
            },
        },
        class_resources={
            "bardic_inspiration": {
                "die": "d8",
                "uses_remaining": 1,
                "source_character_id": "bard-1",
                "source_character_name": "Lyra",
            },
        },
        derived={"saving_throws": {"con": 0}},
        ability_scores={},
    )

    results = resolve_repeat_save_end_of_turn_saves(
        actor,
        entity_id="target-1",
        actor_name="Inspired Guard",
        use_bardic_inspiration=True,
        bardic_inspiration_roll=4,
    )

    assert len(results) == 1
    save = results[0]["save"]
    assert save["success"] is True
    assert save["total"] == 15
    assert save["bardic_inspiration"]["spent"] is True
    assert save["bardic_inspiration"]["context"] == "condition_end_save"
    assert save["bardic_inspiration"]["roll"] == 4
    assert actor.class_resources["bardic_inspiration"]["uses_remaining"] == 0
    assert actor.conditions == []
    assert actor.condition_durations == {}


def test_fear_repeat_save_requires_blocked_line_of_sight_to_source():
    actor = {
        "id": "target-1",
        "name": "Fleeing Guard",
        "conditions": ["frightened"],
        "condition_durations": {
            "frightened": {
                "duration": 10,
                "repeat_save": "end_of_turn",
                "repeat_save_requires": "no_line_of_sight_to_source",
                "save_ability": "wis",
                "save_dc": 12,
                "end_save_d20": 20,
                "source_id": "caster-1",
                "spell_name": "Fear",
            },
        },
        "derived": {"saving_throws": {"wis": 0}},
    }
    visible_combat = SimpleNamespace(
        grid_data={},
        entity_positions={"target-1": {"x": 0, "y": 0}, "caster-1": {"x": 2, "y": 0}},
    )

    visible_results = resolve_repeat_save_end_of_turn_saves(
        actor,
        entity_id="target-1",
        actor_name="Fleeing Guard",
        combat=visible_combat,
    )

    assert visible_results == []
    assert actor["conditions"] == ["frightened"]

    blocked_combat = SimpleNamespace(
        grid_data={"1_0": "total_cover"},
        entity_positions={"target-1": {"x": 0, "y": 0}, "caster-1": {"x": 2, "y": 0}},
    )
    blocked_results = resolve_repeat_save_end_of_turn_saves(
        actor,
        entity_id="target-1",
        actor_name="Fleeing Guard",
        combat=blocked_combat,
    )

    assert len(blocked_results) == 1
    assert blocked_results[0]["ended"] is True
    assert blocked_results[0]["repeat_save"]["requires"] == "no_line_of_sight_to_source"
    assert actor["conditions"] == []


def test_repeat_save_metadata_marks_supported_control_conditions():
    metadata = build_repeat_save_condition_metadata(
        "slowed",
        save_ability="wis",
        spell_save_dc=14,
        caster_id="caster-1",
        spell_name="Slow",
    )

    assert metadata == {
        "repeat_save": "end_of_turn",
        "save_ability": "wis",
        "save_dc": 14,
        "spell_name": "Slow",
        "caster_id": "caster-1",
        "source_id": "caster-1",
    }
