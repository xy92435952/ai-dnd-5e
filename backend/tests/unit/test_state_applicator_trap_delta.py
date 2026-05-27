import json

import pytest

from models.character import Character
from models.session import Session
from services.state_applicator import StateApplicator


class FakeDb:
    def __init__(self):
        self.added = []

    def add(self, item):
        self.added.append(item)


@pytest.mark.asyncio
async def test_state_applicator_applies_trap_trigger_delta(monkeypatch):
    session = Session(
        id="session-1",
        module_id="module-1",
        game_state={},
    )
    character = Character(
        id="char-1",
        name="Scout",
        race="Human",
        char_class="Rogue",
        level=1,
        background="Urchin",
        ability_scores={"str": 8, "dex": 16, "con": 12, "int": 14, "wis": 10, "cha": 10},
        derived={
            "hp_max": 9,
            "ability_modifiers": {"dex": 3},
            "saving_throws": {"dex": 3},
            "proficiency_bonus": 2,
        },
        hp_current=9,
        conditions=[],
    )

    def fake_apply_trap_trigger_to_target(trap, target):
        target.hp_current = 4
        target.conditions = ["prone"]
        return {
            "trap_id": trap["id"],
            "name": trap["name"],
            "target_id": target.id,
            "target_name": target.name,
            "save_ability": "dex",
            "save_dc": 14,
            "save": {"d20": 7, "modifier": 3, "total": 10, "success": False},
            "saved": False,
            "damage_dice": "2d6",
            "damage_type": "piercing",
            "damage_roll": {"rolls": [2, 3], "total": 5},
            "rolled_damage": 5,
            "half_on_save": True,
            "final_damage": 5,
            "conditions_applied": ["prone"],
            "conditions_added": ["prone"],
            "mutates_hp": True,
            "hp_before": 9,
            "hp_after": 4,
        }

    monkeypatch.setattr(
        "services.state_applicator.apply_trap_trigger_to_target",
        fake_apply_trap_trigger_to_target,
    )
    applicator = StateApplicator(FakeDb())
    result = {
        "action_type": "investigation",
        "narrative": "A hidden dart snaps from the wall.",
        "state_delta": {
            "trap_triggers": [
                {
                    "target_character_id": "char-1",
                    "trap": {
                        "id": "dart-wall",
                        "name": "Dart Wall",
                        "save_ability": "dex",
                        "save_dc": 14,
                        "damage_dice": "2d6",
                        "damage_type": "piercing",
                        "conditions_on_fail": ["prone"],
                    },
                }
            ]
        },
    }

    applied = await applicator.apply(
        session,
        json.dumps(result),
        characters=[character],
    )

    assert character.hp_current == 4
    assert character.conditions == ["prone"]
    assert applied.dice_display == [
        {
            "label": "Dart Wall saving throw",
            "kind": "saving_throw",
            "ability": "dex",
            "dc": 14,
            "raw": 7,
            "modifier": 3,
            "total": 10,
            "success": False,
            "target_id": "char-1",
        },
        {
            "label": "Dart Wall damage",
            "kind": "damage",
            "damage_type": "piercing",
            "formula": "2d6",
            "rolls": [2, 3],
            "raw": 5,
            "total": 5,
            "halved": False,
            "target_id": "char-1",
        },
    ]


@pytest.mark.asyncio
async def test_state_applicator_applies_trap_attack_delta(monkeypatch):
    session = Session(
        id="session-1",
        module_id="module-1",
        game_state={},
    )
    character = Character(
        id="char-1",
        name="Scout",
        race="Human",
        char_class="Rogue",
        level=1,
        background="Urchin",
        ability_scores={"dex": 16},
        derived={"ac": 15, "hp_max": 9},
        hp_current=9,
        conditions=[],
    )

    def fake_apply_trap_attack_to_target(trap, target):
        target.hp_current = 5
        target.conditions = ["poisoned"]
        return {
            "trap_id": trap["id"],
            "name": trap["name"],
            "target_id": target.id,
            "target_name": target.name,
            "attack_bonus": 5,
            "attack": {
                "d20": 13,
                "attack_bonus": 5,
                "attack_total": 18,
                "target_ac": 15,
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
            },
            "hit": True,
            "damage_dice": "1d8",
            "damage_type": "poison",
            "damage_roll": {"rolls": [4], "total": 4},
            "rolled_damage": 4,
            "final_damage": 4,
            "conditions_applied": ["poisoned"],
            "conditions_added": ["poisoned"],
            "mutates_hp": True,
            "hp_before": 9,
            "hp_after": 5,
        }

    monkeypatch.setattr(
        "services.state_applicator.apply_trap_attack_to_target",
        fake_apply_trap_attack_to_target,
    )
    applicator = StateApplicator(FakeDb())
    result = {
        "action_type": "investigation",
        "narrative": "A needle springs from the lock.",
        "state_delta": {
            "trap_attacks": [
                {
                    "target_character_id": "char-1",
                    "trap": {
                        "id": "needle",
                        "name": "Poison Needle",
                        "attack_bonus": 5,
                        "damage_dice": "1d8",
                        "damage_type": "poison",
                    },
                }
            ]
        },
    }

    applied = await applicator.apply(
        session,
        json.dumps(result),
        characters=[character],
    )

    assert character.hp_current == 5
    assert character.conditions == ["poisoned"]
    assert session.game_state["trap_states"]["needle"]["triggered"] is True
    assert session.game_state["trap_states"]["needle"]["last_attack"] == {
        "target_ac": 15,
        "total": 18,
        "hit": True,
        "damage": 4,
    }
    assert [item["kind"] for item in applied.dice_display] == ["attack_roll", "damage"]


@pytest.mark.asyncio
async def test_state_applicator_skips_disarmed_trap_attack(monkeypatch):
    session = Session(
        id="session-1",
        module_id="module-1",
        game_state={"trap_states": {"needle": {"disarmed": True}}},
    )
    character = Character(
        id="char-1",
        name="Scout",
        race="Human",
        char_class="Rogue",
        level=1,
        background="Urchin",
        ability_scores={"dex": 16},
        derived={"ac": 15, "hp_max": 9},
        hp_current=9,
        conditions=[],
    )

    monkeypatch.setattr(
        "services.state_applicator.apply_trap_attack_to_target",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not attack")),
    )
    applicator = StateApplicator(FakeDb())
    result = {
        "action_type": "investigation",
        "narrative": "The disabled needle stays still.",
        "state_delta": {
            "trap_attacks": [
                {
                    "target_character_id": "char-1",
                    "trap": {"id": "needle", "name": "Poison Needle", "attack_bonus": 5},
                }
            ]
        },
    }

    applied = await applicator.apply(
        session,
        json.dumps(result),
        characters=[character],
    )

    assert character.hp_current == 9
    assert character.conditions == []
    assert applied.dice_display == []
    assert session.game_state["trap_states"]["needle"] == {"disarmed": True}


@pytest.mark.asyncio
async def test_state_applicator_records_successful_trap_disarm(monkeypatch):
    session = Session(
        id="session-1",
        module_id="module-1",
        game_state={},
    )
    character = Character(
        id="char-1",
        name="Scout",
        race="Human",
        char_class="Rogue",
        level=1,
        background="Urchin",
        ability_scores={"dex": 16},
        derived={"ability_modifiers": {"dex": 3}, "proficiency_bonus": 2},
        hp_current=9,
        conditions=[],
    )

    def fake_resolve_trap_disarm(trap, actor):
        return {
            "trap_id": trap["id"],
            "name": trap["name"],
            "actor_id": actor.id,
            "actor_name": actor.name,
            "ability": "dex",
            "tool": "thieves' tools",
            "tool_proficient": True,
            "dc": 14,
            "d20": 12,
            "modifier": 5,
            "total": 17,
            "success": True,
            "triggered": False,
        }

    monkeypatch.setattr(
        "services.state_applicator.resolve_trap_disarm",
        fake_resolve_trap_disarm,
    )
    applicator = StateApplicator(FakeDb())
    result = {
        "action_type": "investigation",
        "narrative": "The wire slackens.",
        "state_delta": {
            "trap_disarms": [
                {
                    "actor_character_id": "char-1",
                    "trap": {"id": "wire", "name": "Tripwire", "disarm_dc": 14},
                }
            ]
        },
    }

    applied = await applicator.apply(
        session,
        json.dumps(result),
        characters=[character],
    )

    assert session.game_state["trap_states"]["wire"]["disarmed"] is True
    assert session.game_state["trap_states"]["wire"]["triggered"] is False
    assert session.game_state["trap_states"]["wire"]["last_check"] == {
        "ability": "dex",
        "tool": "thieves' tools",
        "dc": 14,
        "total": 17,
        "success": True,
    }
    assert applied.dice_display == [
        {
            "label": "Tripwire disarm check",
            "kind": "ability_check",
            "ability": "dex",
            "tool": "thieves' tools",
            "tool_proficient": True,
            "dc": 14,
            "raw": 12,
            "modifier": 5,
            "total": 17,
            "success": True,
            "triggered": False,
            "actor_id": "char-1",
            "trap_id": "wire",
        },
    ]


@pytest.mark.asyncio
async def test_state_applicator_failed_trap_disarm_triggers_trap(monkeypatch):
    session = Session(
        id="session-1",
        module_id="module-1",
        game_state={},
    )
    character = Character(
        id="char-1",
        name="Scout",
        race="Human",
        char_class="Rogue",
        level=1,
        background="Urchin",
        ability_scores={"dex": 16},
        derived={"ability_modifiers": {"dex": 3}, "proficiency_bonus": 2},
        hp_current=9,
        conditions=[],
    )

    def fake_resolve_trap_disarm(trap, actor):
        return {
            "trap_id": trap["id"],
            "name": trap["name"],
            "actor_id": actor.id,
            "actor_name": actor.name,
            "ability": "dex",
            "tool": "thieves' tools",
            "tool_proficient": True,
            "dc": 15,
            "d20": 4,
            "modifier": 5,
            "total": 9,
            "success": False,
            "triggered": True,
        }

    def fake_apply_trap_trigger_to_target(trap, target):
        target.hp_current = 6
        target.conditions = ["poisoned"]
        return {
            "trap_id": trap["id"],
            "name": trap["name"],
            "target_id": target.id,
            "target_name": target.name,
            "save_ability": "dex",
            "save_dc": 15,
            "save": {"d20": 6, "modifier": 3, "total": 9, "success": False},
            "saved": False,
            "damage_dice": "1d6",
            "damage_type": "poison",
            "damage_roll": {"rolls": [3], "total": 3},
            "rolled_damage": 3,
            "half_on_save": True,
            "final_damage": 3,
            "conditions_applied": ["poisoned"],
            "conditions_added": ["poisoned"],
            "mutates_hp": True,
            "hp_before": 9,
            "hp_after": 6,
        }

    monkeypatch.setattr(
        "services.state_applicator.resolve_trap_disarm",
        fake_resolve_trap_disarm,
    )
    monkeypatch.setattr(
        "services.state_applicator.apply_trap_trigger_to_target",
        fake_apply_trap_trigger_to_target,
    )
    applicator = StateApplicator(FakeDb())
    result = {
        "action_type": "investigation",
        "narrative": "The needle fires.",
        "state_delta": {
            "trap_disarms": [
                {
                    "actor_character_id": "char-1",
                    "trap": {
                        "id": "needle",
                        "name": "Poison Needle",
                        "disarm_dc": 15,
                        "save_dc": 15,
                        "damage_dice": "1d6",
                        "damage_type": "poison",
                    },
                }
            ]
        },
    }

    applied = await applicator.apply(
        session,
        json.dumps(result),
        characters=[character],
    )

    assert character.hp_current == 6
    assert character.conditions == ["poisoned"]
    assert session.game_state["trap_states"]["needle"]["disarmed"] is False
    assert session.game_state["trap_states"]["needle"]["triggered"] is True
    assert [item["kind"] for item in applied.dice_display] == [
        "ability_check",
        "saving_throw",
        "damage",
    ]
