import pytest

from services.combat_spell_application_service import apply_confirmed_spell_effects


class FakeDb:
    async def get(self, *_args):
        return None


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
