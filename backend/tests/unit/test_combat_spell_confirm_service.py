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
    def __init__(self, characters=None):
        self.characters = characters or {}

    async def get(self, _model, entity_id):
        return self.characters.get(entity_id)


def complete_pending_spell(
    combat,
    caster_entity_id,
    *,
    is_cantrip,
    action_cost="action",
):
    del is_cantrip
    turn_state = dict(combat.turn_states.get(caster_entity_id, {}))
    turn_state.pop("pending_spell", None)
    if action_cost == "bonus":
        turn_state["bonus_action_used"] = True
    elif action_cost == "action":
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
            "action_cost": "action",
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


@pytest.mark.asyncio
async def test_confirm_pending_spell_completes_bonus_action_cost(monkeypatch):
    from services import combat_spell_confirm_service as confirm_service

    async def fake_apply_effects(*_args, **_kwargs):
        from services.combat_spell_application_service import SpellApplicationResult

        return SpellApplicationResult(result_heal=5)

    monkeypatch.setattr(confirm_service, "apply_confirmed_spell_effects", fake_apply_effects)

    combat = FakeCombat()
    combat.turn_states["caster-1"]["action_used"] = True
    combat.turn_states["caster-1"]["bonus_action_used"] = False
    caster = FakeCaster()

    result = await confirm_service.confirm_pending_spell(
        FakeDb({"caster-1": caster}),
        session_id="sess-1",
        combat_obj=combat,
        caster=caster,
        caster_entity_id="caster-1",
        pending={
            "spell_name": "Healing Word",
            "spell_level": 1,
            "target_ids": ["caster-1"],
            "is_cantrip": False,
            "is_aoe": False,
            "spell_type": "heal",
            "action_cost": "bonus",
        },
        spell={"type": "heal"},
        state={"enemies": []},
        enemies=[],
        damage_values=None,
        spell_service_obj=FakeSpellService(),
        check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
        complete_pending_spell_func=complete_pending_spell,
    )

    assert result.heal == 5
    assert result.turn_state["action_used"] is True
    assert result.turn_state["bonus_action_used"] is True


@pytest.mark.asyncio
async def test_confirm_pending_heal_rejects_dead_target_before_consuming_slot():
    from types import SimpleNamespace

    from fastapi import HTTPException

    from services import combat_spell_confirm_service as confirm_service

    combat = FakeCombat()
    caster = FakeCaster()
    dead_target = SimpleNamespace(
        id="ally-1",
        name="Ally",
        hp_current=0,
        death_saves={"successes": 0, "failures": 3, "stable": False},
        conditions=["unconscious"],
    )

    with pytest.raises(HTTPException, match="Ordinary healing cannot revive"):
        await confirm_service.confirm_pending_spell(
            FakeDb({"ally-1": dead_target}),
            session_id="sess-1",
            combat_obj=combat,
            caster=caster,
            caster_entity_id="caster-1",
            pending={
                "spell_name": "Cure Wounds",
                "spell_level": 1,
                "target_ids": ["ally-1"],
                "is_cantrip": False,
                "is_aoe": False,
                "spell_type": "heal",
            },
            spell={"type": "heal"},
            state={"enemies": []},
            enemies=[],
            damage_values=None,
            spell_service_obj=FakeSpellService(),
            complete_pending_spell_func=complete_pending_spell,
        )

    assert caster.spell_slots == {"1st": 1}
    assert "pending_spell" in combat.turn_states["caster-1"]
    assert dead_target.hp_current == 0


@pytest.mark.asyncio
async def test_confirm_pending_damage_rejects_missing_target_before_consuming_slot():
    from fastapi import HTTPException

    from services import combat_spell_confirm_service as confirm_service

    combat = FakeCombat()
    caster = FakeCaster()

    with pytest.raises(HTTPException, match="Target does not exist"):
        await confirm_service.confirm_pending_spell(
            FakeDb(),
            session_id="sess-1",
            combat_obj=combat,
            caster=caster,
            caster_entity_id="caster-1",
            pending={
                "spell_name": "Chromatic Orb",
                "spell_level": 1,
                "target_ids": ["missing-target"],
                "is_cantrip": False,
                "is_aoe": False,
                "spell_type": "damage",
            },
            spell={"type": "damage"},
            state={"enemies": []},
            enemies=[],
            damage_values=[5],
            spell_service_obj=FakeSpellService(),
            complete_pending_spell_func=complete_pending_spell,
        )

    assert caster.spell_slots == {"1st": 1}
    assert "pending_spell" in combat.turn_states["caster-1"]


@pytest.mark.asyncio
async def test_confirm_pending_damage_rejects_empty_target_list_before_consuming_slot():
    from fastapi import HTTPException

    from services import combat_spell_confirm_service as confirm_service

    combat = FakeCombat()
    caster = FakeCaster()

    with pytest.raises(HTTPException, match="法术目标"):
        await confirm_service.confirm_pending_spell(
            FakeDb(),
            session_id="sess-1",
            combat_obj=combat,
            caster=caster,
            caster_entity_id="caster-1",
            pending={
                "spell_name": "Fire Bolt",
                "spell_level": 0,
                "target_ids": [],
                "is_cantrip": True,
                "is_aoe": False,
                "spell_type": "damage",
            },
            spell={"type": "damage"},
            state={"enemies": []},
            enemies=[],
            damage_values=[5],
            spell_service_obj=FakeSpellService(),
            complete_pending_spell_func=complete_pending_spell,
        )

    assert caster.spell_slots == {"1st": 1}
    assert "pending_spell" in combat.turn_states["caster-1"]
    assert combat.turn_states["caster-1"]["action_used"] is False


@pytest.mark.asyncio
async def test_confirm_pending_resurrection_returns_target_state():
    from types import SimpleNamespace

    from services import combat_spell_confirm_service as confirm_service

    class ResurrectionSpellService(FakeSpellService):
        def consume_slot(self, slots, spell_level):
            slots = dict(slots)
            slots["5th"] = slots.get("5th", 0) - 1
            return slots, None

    combat = FakeCombat()
    caster = FakeCaster()
    caster.spell_slots = {"5th": 1}
    dead_target = SimpleNamespace(
        id="ally-1",
        name="Ally",
        hp_current=0,
        derived={"hp_max": 12},
        condition_durations={},
        death_saves={"successes": 0, "failures": 3, "stable": False},
        conditions=["unconscious"],
    )

    result = await confirm_service.confirm_pending_spell(
        FakeDb({"ally-1": dead_target}),
        session_id="sess-1",
        combat_obj=combat,
        caster=caster,
        caster_entity_id="caster-1",
        pending={
            "spell_name": "复活死者",
            "spell_level": 5,
            "target_ids": ["ally-1"],
            "is_cantrip": False,
            "is_aoe": False,
            "spell_type": "utility",
        },
        spell={"name_en": "Raise Dead", "type": "utility"},
        state={"enemies": []},
        enemies=[],
        damage_values=None,
        spell_service_obj=ResurrectionSpellService(),
        check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
        complete_pending_spell_func=complete_pending_spell,
    )

    assert result.target_new_hp == 1
    assert result.target_state == {
        "target_id": "ally-1",
        "target_name": "Ally",
        "resurrected": True,
        "new_hp": 1,
        "hp_current": 1,
        "hp_max": 12,
        "death_saves": None,
        "conditions": [],
        "life_state": "alive",
    }
    assert result.resurrection_results == [result.target_state]
    assert result.remaining_slots == {"5th": 0}
    assert dead_target.hp_current == 1
    assert result.turn_state["action_used"] is True
