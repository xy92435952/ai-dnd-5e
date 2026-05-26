from types import SimpleNamespace

import pytest

from services import item_effects


def make_character(**overrides):
    data = {
        "id": "char-1",
        "name": "测试战士",
        "session_id": "sess-1",
        "hp_current": 4,
        "derived": {"hp_max": 12},
        "conditions": [],
        "condition_durations": {},
        "death_saves": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_apply_healing_effect_caps_at_hp_max(monkeypatch):
    monkeypatch.setattr(
        item_effects,
        "roll_dice",
        lambda formula: {"formula": formula, "rolls": [4, 4], "bonus": 2, "total": 10},
    )
    actor = make_character(hp_current=5, derived={"hp_max": 12})

    result = item_effects.apply_item_effect(
        actor=actor,
        item_name="Healing Potion",
        item_data={"consumable": True, "effect": "heal", "heal_dice": "2d4+2"},
    )

    assert actor.hp_current == 12
    assert result["heal_amount"] == 10
    assert result["hp_before"] == 5
    assert result["hp_after"] == 12


def test_apply_healing_effect_caps_at_exhaustion_hp_max(monkeypatch):
    monkeypatch.setattr(
        item_effects,
        "roll_dice",
        lambda formula: {"formula": formula, "rolls": [4, 4], "bonus": 2, "total": 10},
    )
    actor = make_character(
        hp_current=4,
        derived={"hp_max": 12},
        conditions=["exhaustion"],
        condition_durations={"exhaustion_level": 4},
    )

    result = item_effects.apply_item_effect(
        actor=actor,
        item_name="Healing Potion",
        item_data={"consumable": True, "effect": "heal", "heal_dice": "2d4+2"},
    )

    assert actor.hp_current == 6
    assert result["hp_after"] == 6


def test_apply_healing_effect_revives_and_clears_death_saves(monkeypatch):
    monkeypatch.setattr(
        item_effects,
        "roll_dice",
        lambda formula: {"formula": formula, "rolls": [3, 3], "bonus": 2, "total": 8},
    )
    actor = make_character(
        hp_current=0,
        death_saves={"successes": 1, "failures": 2, "stable": False},
    )

    result = item_effects.apply_item_effect(
        actor=actor,
        item_name="Healing Potion",
        item_data={"consumable": True, "effect": "heal", "heal_dice": "2d4+2"},
    )

    assert actor.hp_current == 8
    assert actor.death_saves is None
    assert result["revived"] is True
    assert result["death_saves"] is None


def test_apply_fire_resistance_adds_condition_once():
    actor = make_character(conditions=["fire_resistance"])

    result = item_effects.apply_item_effect(
        actor=actor,
        item_name="Potion of Fire Resistance",
        item_data={"consumable": True, "effect": "fire_resistance"},
    )

    assert actor.conditions == ["fire_resistance"]
    assert result["conditions"] == ["fire_resistance"]
    assert "added_condition" not in result


def test_apply_stabilize_effect_updates_target_death_saves():
    actor = make_character(id="char-1", name="医者", session_id="sess-1", hp_current=8)
    target = make_character(
        id="ally-1",
        name="濒死队友",
        session_id="sess-1",
        hp_current=0,
        death_saves={"successes": 1, "failures": 2, "stable": False},
    )

    result = item_effects.apply_item_effect(
        actor=actor,
        item_name="Healer's Kit",
        item_data={"consumable": True, "effect": "stabilize"},
        target=target,
    )

    assert target.hp_current == 0
    assert target.death_saves == {"successes": 0, "failures": 0, "stable": True}
    assert result["target_character_id"] == "ally-1"
    assert result["target_name"] == "濒死队友"
    assert result["death_saves"] == {"successes": 0, "failures": 0, "stable": True}


def test_apply_stabilize_rejects_target_with_positive_hp():
    actor = make_character(id="char-1", session_id="sess-1", hp_current=8)
    target = make_character(id="ally-1", session_id="sess-1", hp_current=3)

    with pytest.raises(item_effects.ItemEffectError, match="目标并未濒死"):
        item_effects.apply_item_effect(
            actor=actor,
            item_name="Healer's Kit",
            item_data={"consumable": True, "effect": "stabilize"},
            target=target,
        )
