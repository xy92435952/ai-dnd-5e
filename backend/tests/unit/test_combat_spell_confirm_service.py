import pytest


class FakeCaster:
    name = "法师"
    char_class = "Wizard"
    is_player = True
    class_resources = {}
    derived = {
        "spell_ability": "int",
        "spell_save_dc": 13,
        "ability_modifiers": {"int": 3},
    }
    spell_slots = {"1st": 1}
    concentration = None


class FakeCombat:
    def __init__(self):
        self.turn_states = {
            "caster-1": {
                "pending_spell": {"pending_spell_id": "ps-1"},
                "action_used": False,
            }
        }


class FakeSpellService:
    def consume_slot(self, slots, spell_level):
        slots = dict(slots)
        slots["1st"] = slots.get("1st", 0) - 1
        return slots, None

    def resolve_damage(self, *_args):
        return 7, {"formula": "1d8+3", "total": 7}

    def resolve_heal(self, *_args):
        return 0, {}


class FakeDb:
    pass


def complete_pending_spell(combat, caster_entity_id, *, is_cantrip):
    turn_state = dict(combat.turn_states.get(caster_entity_id, {}))
    turn_state.pop("pending_spell", None)
    if not is_cantrip:
        turn_state["action_used"] = True
    combat.turn_states[caster_entity_id] = turn_state
    return turn_state


@pytest.mark.asyncio
async def test_confirm_pending_spell_consumes_slot_applies_damage_and_completes_turn(monkeypatch):
    from services import combat_spell_confirm_service as confirm_service

    async def fake_apply_effects(*_args, **_kwargs):
        from services.combat_spell_application_service import SpellApplicationResult

        return SpellApplicationResult(
            result_damage=7,
            dice_detail={"formula": "1d8+3", "total": 7},
            target_new_hp=0,
            enemies_changed=True,
        )

    monkeypatch.setattr(confirm_service, "apply_confirmed_spell_effects", fake_apply_effects)

    combat = FakeCombat()
    caster = FakeCaster()
    state = {"enemies": [{"id": "goblin-1", "hp_current": 7}]}

    result = await confirm_service.confirm_pending_spell(
        FakeDb(),
        session_id="sess-1",
        combat_obj=combat,
        caster=caster,
        caster_entity_id="caster-1",
        pending={
            "spell_name": "Magic Missile",
            "spell_level": 1,
            "target_ids": ["goblin-1"],
            "is_cantrip": False,
            "is_aoe": False,
            "spell_type": "damage",
        },
        spell={
            "type": "damage",
            "concentration": True,
            "damage_type": "force",
        },
        state=state,
        enemies=state["enemies"],
        damage_values=None,
        spell_service_obj=FakeSpellService(),
        flag_modified_func=lambda *_args: None,
        roll_dice_func=lambda expr: {"rolls": [5], "total": 5},
        roll_wild_magic_surge_func=lambda: {"index": 0, "effect": "spark"},
        check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
        complete_pending_spell_func=complete_pending_spell,
    )

    assert caster.spell_slots == {"1st": 0}
    assert caster.concentration == "Magic Missile"
    assert result.damage == 7
    assert result.target_new_hp == 0
    assert result.remaining_slots == {"1st": 0}
    assert result.turn_state["action_used"] is True
    assert "pending_spell" not in result.turn_state
    assert result.is_concentration is True
