import pytest

from services.combat_spell_prepare_service import prepare_spell_roll
from services.combat_spell_roll_service import CombatSpellRollError
from services.combat_turn_state_service import DEFAULT_TURN_STATE


class FakeDb:
    def __init__(self, characters=None):
        self.characters = characters or {}

    async def get(self, _model, entity_id):
        return self.characters.get(entity_id)


class FakeCaster:
    hp_current = 20
    conditions = []
    death_saves = {}
    spell_slots = {"1st": 1}
    feats = []
    class_resources = {}
    derived = {
        "spell_save_dc": 14,
        "spell_ability": "int",
        "spell_attack_bonus": 5,
        "ability_modifiers": {"int": 3},
    }


class FakeCombat:
    entity_positions = {}
    turn_states = {}


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
    assert prepared.pending_spell["action_cost"] == "action"
    assert prepared.spell_attack_required is True
    assert prepared.attack_roll_result["d20"] >= 1


@pytest.mark.asyncio
async def test_prepare_spell_roll_marks_magic_initiate_resource_without_slot():
    caster = FakeCaster()
    caster.spell_slots = {"1st": 0}
    caster.feats = [{"name": "Magic Initiate", "spell": "Shield"}]
    caster.class_resources = {"magic_initiate_spell_uses_remaining": 1}

    prepared = await prepare_spell_roll(
        FakeDb(),
        combat_obj=None,
        session=None,
        caster=caster,
        caster_id="caster-1",
        spell_name="Shield",
        spell_level=1,
        spell={
            "name_en": "Shield",
            "level": 1,
            "type": "utility",
            "aoe": False,
            "range": 0,
        },
        target_id=None,
        target_ids=None,
        enemies=[],
        default_turn_state=DEFAULT_TURN_STATE,
        get_turn_state=lambda *_args: DEFAULT_TURN_STATE,
        consume_slot=lambda *_args: (_ for _ in ()).throw(AssertionError("Magic Initiate should satisfy validation")),
        calc_upcast_dice=lambda *_args: None,
    )

    assert prepared.pending_spell["resource_source"] == "magic_initiate"
    assert prepared.pending_spell["resource_key"] == "magic_initiate_spell_uses_remaining"
    assert caster.spell_slots == {"1st": 0}


@pytest.mark.asyncio
async def test_prepare_spell_roll_rejects_spent_magic_initiate_without_slot():
    caster = FakeCaster()
    caster.spell_slots = {"1st": 0}
    caster.feats = [{"name": "Magic Initiate", "spell": "Shield"}]
    caster.class_resources = {"magic_initiate_spell_uses_remaining": 0}

    with pytest.raises(CombatSpellRollError) as exc:
        await prepare_spell_roll(
            FakeDb(),
            combat_obj=None,
            session=None,
            caster=caster,
            caster_id="caster-1",
            spell_name="Shield",
            spell_level=1,
            spell={"name_en": "Shield", "level": 1, "type": "utility", "aoe": False},
            target_id=None,
            target_ids=None,
            enemies=[],
            default_turn_state=DEFAULT_TURN_STATE,
            get_turn_state=lambda *_args: DEFAULT_TURN_STATE,
            consume_slot=lambda slots, level: (slots, "No 1st-level spell slots available"),
            calc_upcast_dice=lambda *_args: None,
        )

    assert exc.value.status_code == 400
    assert "No 1st-level spell slots" in exc.value.detail


@pytest.mark.asyncio
async def test_prepare_spell_roll_uses_frontend_d20_for_spell_attack_crit():
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
            "save": None,
        },
        target_id="goblin-1",
        target_ids=None,
        enemies=[{"id": "goblin-1", "name": "Goblin", "hp_current": 7, "derived": {"ac": 15}}],
        d20_value=20,
        default_turn_state=DEFAULT_TURN_STATE,
        get_turn_state=lambda *_args: DEFAULT_TURN_STATE,
        consume_slot=lambda *_args: (_ for _ in ()).throw(AssertionError("cantrip should not consume")),
        calc_upcast_dice=lambda *_args: None,
    )

    assert prepared.attack_roll_result["hit"] is True
    assert prepared.attack_roll_result["is_crit"] is True
    assert prepared.pending_spell["attack_roll"]["is_crit"] is True


@pytest.mark.asyncio
async def test_prepare_spell_roll_rejects_action_cantrip_after_action_used():
    with pytest.raises(CombatSpellRollError) as exc:
        await prepare_spell_roll(
            FakeDb(),
            combat_obj=FakeCombat(),
            session=None,
            caster=FakeCaster(),
            caster_id="caster-1",
            spell_name="Fire Bolt",
            spell_level=0,
            spell={
                "level": 0,
                "type": "damage",
                "damage_dice": "1d10",
                "casting_time": "action",
                "aoe": False,
                "range": 0,
            },
            target_id="goblin-1",
            target_ids=None,
            enemies=[{"id": "goblin-1", "name": "Goblin", "hp_current": 7}],
            default_turn_state=DEFAULT_TURN_STATE,
            get_turn_state=lambda *_args: {"action_used": True, "bonus_action_used": False},
            consume_slot=lambda *_args: (_ for _ in ()).throw(AssertionError("cantrip should not consume")),
            calc_upcast_dice=lambda *_args: None,
        )

    assert exc.value.status_code == 400
    assert "行动已用尽" in exc.value.detail


@pytest.mark.asyncio
async def test_prepare_spell_roll_rejects_single_target_damage_without_target():
    combat = FakeCombat()
    combat.turn_states = {}

    with pytest.raises(CombatSpellRollError) as exc:
        await prepare_spell_roll(
            FakeDb(),
            combat_obj=combat,
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
                "range": 120,
            },
            target_id=None,
            target_ids=None,
            enemies=[{"id": "goblin-1", "name": "Goblin", "hp_current": 7}],
            default_turn_state=DEFAULT_TURN_STATE,
            get_turn_state=lambda *_args: {"action_used": False, "bonus_action_used": False},
            consume_slot=lambda *_args: (_ for _ in ()).throw(AssertionError("cantrip should not consume")),
            calc_upcast_dice=lambda *_args: None,
        )

    assert exc.value.status_code == 400
    assert "法术目标" in exc.value.detail
    assert combat.turn_states == {}


@pytest.mark.asyncio
async def test_prepare_spell_roll_allows_bonus_spell_after_action_used():
    from models import CombatState

    caster = FakeCaster()
    caster.spell_slots = {"1st": 1}
    combat = CombatState(
        id="combat-1",
        session_id="sess-1",
        entity_positions={},
        turn_states={},
    )

    prepared = await prepare_spell_roll(
        FakeDb(),
        combat_obj=combat,
        session=None,
        caster=caster,
        caster_id="caster-1",
        spell_name="Healing Word",
        spell_level=1,
        spell={
            "level": 1,
            "type": "heal",
            "heal_dice": "1d4",
            "casting_time": "bonus_action",
            "aoe": False,
            "range": 0,
        },
        target_id="ally-1",
        target_ids=None,
        enemies=[{"id": "ally-1", "name": "Ally", "hp_current": 7}],
        default_turn_state=DEFAULT_TURN_STATE,
        get_turn_state=lambda *_args: {"action_used": True, "bonus_action_used": False},
        consume_slot=lambda slots, _level: (slots, None),
        calc_upcast_dice=lambda *_args: None,
    )

    assert prepared.pending_spell["action_cost"] == "bonus"
    assert prepared.heal_dice == "1d4"


@pytest.mark.asyncio
async def test_prepare_spell_roll_rejects_reaction_spell_in_ordinary_flow():
    with pytest.raises(CombatSpellRollError) as exc:
        await prepare_spell_roll(
            FakeDb(),
            combat_obj=FakeCombat(),
            session=None,
            caster=FakeCaster(),
            caster_id="caster-1",
            spell_name="Shield",
            spell_level=1,
            spell={
                "level": 1,
                "type": "utility",
                "casting_time": "reaction",
                "aoe": False,
                "range": 0,
            },
            target_id=None,
            target_ids=None,
            enemies=[],
            default_turn_state=DEFAULT_TURN_STATE,
            get_turn_state=lambda *_args: {"action_used": False, "bonus_action_used": False},
            consume_slot=lambda *_args: (_ for _ in ()).throw(AssertionError("reaction spell should stop first")),
            calc_upcast_dice=lambda *_args: None,
        )

    assert exc.value.status_code == 400
    assert "反应法术" in exc.value.detail


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


@pytest.mark.asyncio
async def test_prepare_spell_roll_rejects_incapacitated_caster():
    caster = FakeCaster()
    caster.conditions = ["incapacitated"]

    with pytest.raises(CombatSpellRollError) as exc:
        await prepare_spell_roll(
            FakeDb(),
            combat_obj=None,
            session=None,
            caster=caster,
            caster_id="caster-1",
            spell_name="Fire Bolt",
            spell_level=0,
            spell={"level": 0, "type": "damage", "damage_dice": "1d10", "aoe": False, "range": 0},
            target_id="goblin-1",
            target_ids=None,
            enemies=[{"id": "goblin-1", "name": "Goblin", "hp_current": 7}],
            default_turn_state=DEFAULT_TURN_STATE,
            get_turn_state=lambda *_args: DEFAULT_TURN_STATE,
            consume_slot=lambda *_args: (_ for _ in ()).throw(AssertionError("cantrip should not consume")),
            calc_upcast_dice=lambda *_args: None,
        )

    assert exc.value.status_code == 400
    assert "incapacitated" in exc.value.detail


@pytest.mark.asyncio
async def test_prepare_armor_of_agathys_defaults_to_self_target():
    from types import SimpleNamespace

    caster = SimpleNamespace(
        id="caster-1",
        name="术士",
        hp_current=20,
        conditions=[],
        death_saves={},
        spell_slots={"1st": 1},
        derived={"spell_save_dc": 14},
    )

    prepared = await prepare_spell_roll(
        FakeDb({"caster-1": caster}),
        combat_obj=None,
        session=None,
        caster=caster,
        caster_id="caster-1",
        spell_name="寒甲",
        spell_level=1,
        spell={
            "name_en": "Armor of Agathys",
            "level": 1,
            "type": "utility",
            "aoe": False,
            "range": 0,
        },
        target_id=None,
        target_ids=None,
        enemies=[],
        default_turn_state=DEFAULT_TURN_STATE,
        get_turn_state=lambda *_args: DEFAULT_TURN_STATE,
        consume_slot=lambda slots, level: (slots, None),
        calc_upcast_dice=lambda *_args: None,
    )

    assert prepared.pending_spell["target_ids"] == ["caster-1"]
    assert prepared.targets == [{"id": "caster-1", "name": "术士"}]
