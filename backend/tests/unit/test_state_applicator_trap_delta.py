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
