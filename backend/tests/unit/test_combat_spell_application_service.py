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
