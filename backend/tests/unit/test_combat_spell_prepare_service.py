import pytest

from services.combat_spell_prepare_service import prepare_spell_roll
from services.combat_spell_roll_service import CombatSpellRollError
from services.combat_turn_state_service import DEFAULT_TURN_STATE


class FakeDb:
    async def get(self, *_args):
        return None


class FakeCaster:
    spell_slots = {"1st": 1}
    derived = {"spell_save_dc": 14}


@pytest.mark.asyncio
async def test_prepare_spell_roll_builds_cantrip_preview_without_consuming_slot():
    prepared = await prepare_spell_roll(
        FakeDb(),
        combat_obj=None,
        session=None,
        caster=FakeCaster(),
        caster_id="caster-1",
        spell_name="Fire Bolt",
        spell_level=0,
        spell={
            "level": 0,
            "type": "damage",
            "damage_dice": "1d10",
            "aoe": False,
            "range": 0,
        },
        target_id="goblin-1",
        target_ids=None,
        enemies=[{"id": "goblin-1", "name": "哥布林", "hp_current": 7}],
        default_turn_state=DEFAULT_TURN_STATE,
        get_turn_state=lambda *_args: (_ for _ in ()).throw(AssertionError("no combat object")),
        consume_slot=lambda *_args: (_ for _ in ()).throw(AssertionError("cantrip should not consume")),
        calc_upcast_dice=lambda *_args: None,
    )

    assert prepared.damage_dice == "1d10"
    assert prepared.is_cantrip is True
    assert prepared.targets == [{"id": "goblin-1", "name": "哥布林"}]
    assert prepared.pending_spell["spell_name"] == "Fire Bolt"


@pytest.mark.asyncio
async def test_prepare_spell_roll_raises_slot_error():
    with pytest.raises(CombatSpellRollError) as exc:
        await prepare_spell_roll(
            FakeDb(),
            combat_obj=None,
            session=None,
            caster=FakeCaster(),
            caster_id="caster-1",
            spell_name="Magic Missile",
            spell_level=1,
            spell={"level": 1, "type": "damage", "damage_dice": "1d4", "aoe": False},
            target_id="goblin-1",
            target_ids=None,
            enemies=[{"id": "goblin-1", "name": "哥布林", "hp_current": 7}],
            default_turn_state=DEFAULT_TURN_STATE,
            get_turn_state=lambda *_args: DEFAULT_TURN_STATE,
            consume_slot=lambda slots, level: (slots, "没有可用的1环法术位"),
            calc_upcast_dice=lambda *_args: None,
        )

    assert exc.value.status_code == 400
    assert "没有可用" in exc.value.detail
