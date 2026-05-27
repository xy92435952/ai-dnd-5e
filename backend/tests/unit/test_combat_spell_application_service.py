import pytest

from services.combat_spell_application_service import apply_confirmed_spell_effects


class FakeDb:
    async def get(self, *_args):
        return None


class CharacterDb:
    def __init__(self, character):
        self.character = character

    async def get(self, *_args):
        return self.character


class FakeCharacter:
    id = "rogue-1"
    name = "Rogue"
    char_class = "Rogue"
    level = 7
    derived = {
        "hp_max": 20,
        "ability_modifiers": {"dex": 5},
        "saving_throws": {"dex": 8},
    }
    conditions = []
    condition_durations = {}
    concentration = None
    death_saves = None
    class_resources = {}
    proficient_saves = []

    def __init__(self, hp_current=20):
        self.hp_current = hp_current


@pytest.mark.asyncio
async def test_apply_confirmed_spell_effects_damages_enemy_target():
    enemies = [{
        "id": "goblin-1",
        "name": "哥布林",
        "hp_current": 10,
        "derived": {"hp_max": 10},
    }]

    result = await apply_confirmed_spell_effects(
        FakeDb(),
        session_id="sess",
        enemies=enemies,
        target_ids=["goblin-1"],
        is_aoe=False,
        spell_type="damage",
        spell_name="Magic Missile",
        spell_level=1,
        spell_mod=0,
        bonus_healing=False,
        spell={},
        damage_values=None,
        spell_save_dc=13,
        resolve_damage=lambda *_args: (7, {"total": 7}),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert result.result_damage == 7
    assert result.target_new_hp == 3
    assert result.enemies_changed is True
    assert enemies[0]["hp_current"] == 3


@pytest.mark.asyncio
async def test_apply_confirmed_spell_effects_single_target_save_cantrip_deals_no_damage_on_success():
    enemies = [{
        "id": "goblin-1",
        "name": "Goblin",
        "hp_current": 10,
        "derived": {"hp_max": 10, "ability_modifiers": {"dex": 20}, "saving_throws": {"dex": 20}},
    }]

    result = await apply_confirmed_spell_effects(
        FakeDb(),
        session_id="sess",
        enemies=enemies,
        target_ids=["goblin-1"],
        is_aoe=False,
        spell_type="damage",
        spell_name="Sacred Flame",
        spell_level=0,
        spell_mod=0,
        bonus_healing=False,
        spell={"save": "dex", "desc": "DEX豁免失败受伤，豁免无效"},
        damage_values=None,
        spell_save_dc=10,
        resolve_damage=lambda *_args: (8, {"total": 8}),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert result.result_damage == 8
    assert result.target_state["damage"] == 0
    assert result.target_state["save"]["success"] is True
    assert enemies[0]["hp_current"] == 10


@pytest.mark.asyncio
async def test_apply_confirmed_spell_effects_legendary_resistance_turns_failed_save_into_success():
    enemies = [{
        "id": "dragon-1",
        "name": "Dragon",
        "hp_current": 60,
        "derived": {"hp_max": 60, "ability_modifiers": {"dex": -5}, "saving_throws": {"dex": -5}},
        "legendary_resistances": 3,
        "legendary_resistances_remaining": 1,
    }]

    result = await apply_confirmed_spell_effects(
        FakeDb(),
        session_id="sess",
        enemies=enemies,
        target_ids=["dragon-1"],
        is_aoe=False,
        spell_type="damage",
        spell_name="Sacred Flame",
        spell_level=0,
        spell_mod=0,
        bonus_healing=False,
        spell={"save": "dex", "desc": "DEX save negates damage."},
        damage_values=None,
        spell_save_dc=30,
        resolve_damage=lambda *_args: (8, {"total": 8}),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert result.target_state["damage"] == 0
    assert result.target_state["save"]["success"] is True
    assert result.target_state["save"]["legendary_resistance_used"] is True
    assert result.target_state["save"]["legendary_resistance_remaining"] == 0
    assert enemies[0]["legendary_resistances_remaining"] == 0
    assert enemies[0]["hp_current"] == 60


@pytest.mark.asyncio
async def test_apply_confirmed_spell_effects_aoe_evasion_success_takes_no_damage():
    rogue = FakeCharacter(hp_current=20)
    rogue.derived = {
        "hp_max": 20,
        "ability_modifiers": {"dex": 20},
        "saving_throws": {"dex": 20},
    }

    result = await apply_confirmed_spell_effects(
        CharacterDb(rogue),
        session_id="sess",
        enemies=[],
        target_ids=[rogue.id],
        is_aoe=True,
        spell_type="damage",
        spell_name="Fireball",
        spell_level=3,
        spell_mod=0,
        bonus_healing=False,
        spell={"save": "dex", "half_on_save": True},
        damage_values=None,
        spell_save_dc=10,
        resolve_damage=lambda *_args: (28, {"total": 28}),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert rogue.hp_current == 20
    assert result.aoe_results[0]["damage"] == 0
    assert result.aoe_results[0]["base_damage"] == 28
    assert result.aoe_results[0]["evasion_applied"] is True


@pytest.mark.asyncio
async def test_apply_confirmed_spell_effects_aoe_applies_resistance_after_save():
    enemies = [{
        "id": "fire-elemental-1",
        "name": "Fire Elemental",
        "hp_current": 20,
        "derived": {"hp_max": 20, "ability_modifiers": {"dex": -5}, "saving_throws": {"dex": -5}},
        "immunities": ["火焰"],
    }]

    result = await apply_confirmed_spell_effects(
        FakeDb(),
        session_id="sess",
        enemies=enemies,
        target_ids=["fire-elemental-1"],
        is_aoe=True,
        spell_type="damage",
        spell_name="Fireball",
        spell_level=3,
        spell_mod=0,
        bonus_healing=False,
        spell={"name_en": "Fireball", "save": "dex", "half_on_save": True},
        damage_values=None,
        spell_save_dc=30,
        resolve_damage=lambda *_args: (28, {"total": 28}),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert result.aoe_results[0]["base_damage"] == 28
    assert result.aoe_results[0]["damage_before_resistance"] == 28
    assert result.aoe_results[0]["damage"] == 0
    assert result.aoe_results[0]["damage_type"] == "fire"
    assert enemies[0]["hp_current"] == 20


@pytest.mark.asyncio
async def test_apply_confirmed_spell_effects_aoe_applies_component_resistance_after_save():
    enemies = [{
        "id": "ice-troll-1",
        "name": "Ice Troll",
        "hp_current": 40,
        "derived": {"hp_max": 40, "ability_modifiers": {"dex": -5}, "saving_throws": {"dex": -5}},
        "resistances": ["cold"],
    }]

    result = await apply_confirmed_spell_effects(
        FakeDb(),
        session_id="sess",
        enemies=enemies,
        target_ids=["ice-troll-1"],
        is_aoe=True,
        spell_type="damage",
        spell_name="Ice Storm",
        spell_level=4,
        spell_mod=0,
        bonus_healing=False,
        spell={"name_en": "Ice Storm", "save": "dex", "half_on_save": True},
        damage_values=None,
        spell_save_dc=30,
        resolve_damage=lambda *_args: (
            20,
            {
                "base_roll": {
                    "total": 20,
                    "parts": [
                        {"notation": "2d8", "rolls": [4, 4], "total": 8},
                        {"notation": "4d6", "rolls": [3, 3, 3, 3], "total": 12},
                    ],
                },
                "total": 20,
            },
        ),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert result.result_damage == 20
    assert result.aoe_results[0]["damage_before_resistance"] == 20
    assert result.aoe_results[0]["damage"] == 14
    assert [component["damage"] for component in result.aoe_results[0]["damage_components"]] == [8, 6]
    assert enemies[0]["hp_current"] == 26


@pytest.mark.asyncio
async def test_apply_confirmed_spell_effects_aoe_halves_each_component_then_resistance():
    enemies = [{
        "id": "ice-troll-1",
        "name": "Ice Troll",
        "hp_current": 40,
        "derived": {"hp_max": 40, "ability_modifiers": {"dex": 20}, "saving_throws": {"dex": 20}},
        "resistances": ["cold"],
    }]

    result = await apply_confirmed_spell_effects(
        FakeDb(),
        session_id="sess",
        enemies=enemies,
        target_ids=["ice-troll-1"],
        is_aoe=True,
        spell_type="damage",
        spell_name="Ice Storm",
        spell_level=4,
        spell_mod=0,
        bonus_healing=False,
        spell={"name_en": "Ice Storm", "save": "dex", "half_on_save": True},
        damage_values=None,
        spell_save_dc=10,
        resolve_damage=lambda *_args: (
            21,
            {
                "base_roll": {
                    "total": 21,
                    "parts": [
                        {"notation": "2d8", "rolls": [4, 5], "total": 9},
                        {"notation": "4d6", "rolls": [4, 3, 3, 2], "total": 12},
                    ],
                },
                "total": 21,
            },
        ),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert result.aoe_results[0]["base_damage"] == 21
    assert result.aoe_results[0]["damage_before_resistance"] == 10
    assert result.aoe_results[0]["damage"] == 7
    assert [component["damage_before_save"] for component in result.aoe_results[0]["damage_components"]] == [9, 12]
    assert [component["damage_before_resistance"] for component in result.aoe_results[0]["damage_components"]] == [4, 6]
    assert [component["damage"] for component in result.aoe_results[0]["damage_components"]] == [4, 3]
    assert enemies[0]["hp_current"] == 33


@pytest.mark.asyncio
async def test_apply_confirmed_spell_effects_aoe_evasion_failure_takes_half_damage():
    rogue = FakeCharacter(hp_current=20)
    rogue.derived = {
        "hp_max": 20,
        "ability_modifiers": {"dex": -5},
        "saving_throws": {"dex": -5},
    }

    result = await apply_confirmed_spell_effects(
        CharacterDb(rogue),
        session_id="sess",
        enemies=[],
        target_ids=[rogue.id],
        is_aoe=True,
        spell_type="damage",
        spell_name="Fireball",
        spell_level=3,
        spell_mod=0,
        bonus_healing=False,
        spell={"save": "dex", "half_on_save": True},
        damage_values=None,
        spell_save_dc=30,
        resolve_damage=lambda *_args: (28, {"total": 28}),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert rogue.hp_current == 6
    assert result.aoe_results[0]["damage"] == 14
    assert result.aoe_results[0]["evasion_failed_half"] is True


@pytest.mark.asyncio
async def test_apply_confirmed_spell_effects_control_blocked_by_legendary_resistance():
    enemies = [{
        "id": "lich-1",
        "name": "Lich",
        "hp_current": 90,
        "derived": {"ability_modifiers": {"wis": -5}, "saving_throws": {"wis": -5}},
        "conditions": [],
        "legendary_resistances": 3,
        "legendary_resistances_remaining": 1,
    }]

    result = await apply_confirmed_spell_effects(
        FakeDb(),
        session_id="sess",
        enemies=enemies,
        target_ids=["lich-1"],
        is_aoe=False,
        spell_type="control",
        spell_name="Hold Person",
        spell_level=2,
        spell_mod=0,
        bonus_healing=False,
        spell={"save": "wis"},
        damage_values=None,
        spell_save_dc=30,
        resolve_damage=lambda *_args: (_ for _ in ()).throw(AssertionError("should not damage")),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert result.save_detail["success"] is True
    assert result.save_detail["legendary_resistance_used"] is True
    assert result.target_state["conditions"] == []
    assert enemies[0]["conditions"] == []
    assert enemies[0]["legendary_resistances_remaining"] == 0
    assert result.enemies_changed is False


@pytest.mark.asyncio
async def test_apply_confirmed_spell_effects_control_marks_enemy_changed():
    enemies = [{
        "id": "goblin-1",
        "name": "哥布林",
        "conditions": [],
    }]

    result = await apply_confirmed_spell_effects(
        FakeDb(),
        session_id="sess",
        enemies=enemies,
        target_ids=["goblin-1"],
        is_aoe=False,
        spell_type="control",
        spell_name="Sleep",
        spell_level=1,
        spell_mod=0,
        bonus_healing=False,
        spell={},
        damage_values=None,
        spell_save_dc=13,
        resolve_damage=lambda *_args: (_ for _ in ()).throw(AssertionError("should not damage")),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert result.condition_name == "unconscious"
    assert result.enemies_changed is True
    assert enemies[0]["conditions"] == ["unconscious"]
    assert enemies[0]["condition_durations"] == {"unconscious": 10}
    assert result.target_state["condition_durations"] == {"unconscious": 10}


@pytest.mark.asyncio
async def test_apply_confirmed_spell_effects_aoe_control_applies_per_target_duration():
    enemies = [
        {
            "id": "goblin-1",
            "name": "Goblin A",
            "hp_current": 7,
            "derived": {"ability_modifiers": {"dex": -5}, "saving_throws": {"dex": -5}},
            "conditions": [],
        },
        {
            "id": "goblin-2",
            "name": "Goblin B",
            "hp_current": 7,
            "derived": {"ability_modifiers": {"dex": -5}, "saving_throws": {"dex": -5}},
            "conditions": [],
        },
    ]

    result = await apply_confirmed_spell_effects(
        FakeDb(),
        session_id="sess",
        enemies=enemies,
        target_ids=["goblin-1", "goblin-2"],
        is_aoe=True,
        spell_type="utility",
        spell_name="网",
        spell_level=2,
        spell_mod=0,
        bonus_healing=False,
        spell={"name_en": "Web", "save": "dex", "concentration": True, "desc": "专注1小时。"},
        damage_values=None,
        spell_save_dc=30,
        resolve_damage=lambda *_args: (_ for _ in ()).throw(AssertionError("should not damage")),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert result.condition_name == "restrained"
    assert result.enemies_changed is True
    assert [item["target_id"] for item in result.aoe_results] == ["goblin-1", "goblin-2"]
    assert enemies[0]["conditions"] == ["restrained"]
    assert enemies[1]["conditions"] == ["restrained"]
    assert enemies[0]["condition_durations"] == {"restrained": 600}
    assert enemies[1]["condition_durations"] == {"restrained": 600}
