import pytest


class FakeDb:
    def __init__(self, characters=None):
        self.characters = characters or {}

    async def get(self, _model, entity_id):
        return self.characters.get(entity_id)


class FakeCaster:
    id = "caster-1"
    name = "法师"
    is_player = True
    session_id = "sess-1"
    hp_current = 20
    conditions = []
    death_saves = {}
    concentration = None
    spell_slots = {"1st": 1}
    derived = {
        "spell_ability": "int",
        "ability_modifiers": {"int": 3},
        "spell_save_dc": 13,
        "bonus_healing": False,
    }


class FakeCombat:
    round_number = 2
    current_turn_index = 1

    def __init__(self):
        self.turn_states = {
            "caster-1": {
                "action_used": False,
                "bonus_action_used": False,
                "attacks_made": 0,
            }
        }


class FakeSession:
    id = "sess-1"
    player_character_id = "caster-1"
    combat_active = True

    def __init__(self):
        self.game_state = {
            "enemies": [
                {
                    "id": "goblin-1",
                    "name": "哥布林",
                    "hp_current": 10,
                    "derived": {"hp_max": 10},
                },
                {
                    "id": "goblin-2",
                    "name": "倒下的哥布林",
                    "hp_current": 0,
                    "derived": {"hp_max": 8},
                },
                {
                    "id": "orc-1",
                    "name": "兽人",
                    "hp_current": 12,
                    "derived": {"hp_max": 12},
                },
            ]
        }


class FakeSpellService:
    def get(self, name):
        return {
            "name": name,
            "level": 1,
            "type": "damage",
            "aoe": True,
            "concentration": True,
        }

    def validate_slot_level(self, *_args):
        return None

    def consume_slot(self, slots, _spell_level):
        slots = dict(slots)
        slots["1st"] = slots.get("1st", 0) - 1
        return slots, None

    def resolve_damage(self, *_args):
        return 6, {"formula": "1d6+3", "total": 6}

    def resolve_heal(self, *_args):
        return 0, {}


def save_turn_state(combat, entity_id, turn_state):
    combat.turn_states[str(entity_id)] = turn_state


@pytest.mark.asyncio
async def test_cast_direct_spell_defaults_empty_aoe_damage_to_alive_enemies():
    from services.combat_direct_spell_service import cast_direct_spell

    session = FakeSession()
    combat = FakeCombat()
    caster = FakeCaster()

    result = await cast_direct_spell(
        FakeDb(),
        session_id="sess-1",
        session=session,
        combat_obj=combat,
        caster=caster,
        caster_id="caster-1",
        spell_name="burning-hands",
        spell_level=1,
        target_id=None,
        target_ids=[],
        spell_service_obj=FakeSpellService(),
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
        check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
    )

    assert [item["target_id"] for item in result.aoe_results] == ["goblin-1", "orc-1"]
    assert session.game_state["enemies"][0]["hp_current"] == 4
    assert session.game_state["enemies"][2]["hp_current"] == 6
    assert caster.spell_slots == {"1st": 0}
    assert caster.concentration == "burning-hands"
    assert result.turn_state["action_used"] is True
    assert result.next_turn_index == 1
    assert result.round_number == 2
    assert result.remaining_slots == {"1st": 0}
    assert result.is_aoe is True
    assert result.is_concentration is True


@pytest.mark.asyncio
async def test_cast_direct_spell_rejects_incapacitated_caster():
    from services.combat_direct_spell_service import CombatDirectSpellError, cast_direct_spell

    session = FakeSession()
    combat = FakeCombat()
    caster = FakeCaster()
    caster.conditions = ["unconscious"]

    with pytest.raises(CombatDirectSpellError) as exc:
        await cast_direct_spell(
            FakeDb(),
            session_id="sess-1",
            session=session,
            combat_obj=combat,
            caster=caster,
            caster_id="caster-1",
            spell_name="burning-hands",
            spell_level=1,
            target_id=None,
            target_ids=[],
            spell_service_obj=FakeSpellService(),
            flag_modified_func=lambda *_args: None,
            save_turn_state_func=save_turn_state,
            check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
        )

    assert exc.value.status_code == 400
    assert "unconscious" in exc.value.detail


@pytest.mark.asyncio
async def test_cast_direct_spell_marks_action_cantrip_action_used():
    from services.combat_direct_spell_service import cast_direct_spell

    class CantripSpellService(FakeSpellService):
        def get(self, name):
            return {
                "name": name,
                "level": 0,
                "type": "damage",
                "aoe": False,
            }

        def consume_slot(self, *_args):
            raise AssertionError("cantrips should not consume spell slots")

    session = FakeSession()
    combat = FakeCombat()
    caster = FakeCaster()

    result = await cast_direct_spell(
        FakeDb(),
        session_id="sess-1",
        session=session,
        combat_obj=combat,
        caster=caster,
        caster_id="caster-1",
        spell_name="fire-bolt",
        spell_level=0,
        target_id="goblin-1",
        target_ids=None,
        spell_service_obj=CantripSpellService(),
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
        check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
    )

    assert result.damage == 6
    assert result.target_new_hp == 4
    assert result.turn_state["action_used"] is True
    assert result.remaining_slots == {"1st": 1}


@pytest.mark.asyncio
async def test_cast_direct_spell_rejects_action_cantrip_after_action_used():
    from services.combat_direct_spell_service import CombatDirectSpellError, cast_direct_spell

    class CantripSpellService(FakeSpellService):
        def get(self, name):
            return {
                "name": name,
                "level": 0,
                "type": "damage",
                "aoe": False,
                "casting_time": "action",
            }

        def consume_slot(self, *_args):
            raise AssertionError("cantrips should not consume spell slots")

    session = FakeSession()
    combat = FakeCombat()
    combat.turn_states["caster-1"]["action_used"] = True
    caster = FakeCaster()

    with pytest.raises(CombatDirectSpellError) as exc:
        await cast_direct_spell(
            FakeDb(),
            session_id="sess-1",
            session=session,
            combat_obj=combat,
            caster=caster,
            caster_id="caster-1",
            spell_name="fire-bolt",
            spell_level=0,
            target_id="goblin-1",
            target_ids=None,
            spell_service_obj=CantripSpellService(),
            flag_modified_func=lambda *_args: None,
            save_turn_state_func=save_turn_state,
            check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
        )

    assert exc.value.status_code == 400
    assert "行动已用尽" in exc.value.detail


@pytest.mark.asyncio
async def test_cast_direct_spell_marks_bonus_action_spell_bonus_used():
    from services.combat_direct_spell_service import cast_direct_spell

    class BonusSpellService(FakeSpellService):
        def get(self, name):
            return {
                "name": name,
                "level": 1,
                "type": "heal",
                "aoe": False,
                "casting_time": "bonus_action",
            }

        def resolve_damage(self, *_args):
            return 0, {}

        def resolve_heal(self, *_args):
            return 5, {"formula": "1d4+3", "total": 5}

    session = FakeSession()
    combat = FakeCombat()
    combat.turn_states["caster-1"]["action_used"] = True
    caster = FakeCaster()

    result = await cast_direct_spell(
        FakeDb({"caster-1": caster}),
        session_id="sess-1",
        session=session,
        combat_obj=combat,
        caster=caster,
        caster_id="caster-1",
        spell_name="healing-word",
        spell_level=1,
        target_id="caster-1",
        target_ids=None,
        spell_service_obj=BonusSpellService(),
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
        check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
    )

    assert result.heal == 5
    assert result.turn_state["action_used"] is True
    assert result.turn_state["bonus_action_used"] is True
    assert result.remaining_slots == {"1st": 0}


@pytest.mark.asyncio
async def test_cast_direct_spell_rejects_reaction_spell_in_ordinary_flow():
    from services.combat_direct_spell_service import CombatDirectSpellError, cast_direct_spell

    class ReactionSpellService(FakeSpellService):
        def get(self, name):
            return {
                "name": name,
                "level": 1,
                "type": "utility",
                "aoe": False,
                "casting_time": "reaction",
            }

    session = FakeSession()
    combat = FakeCombat()
    caster = FakeCaster()

    with pytest.raises(CombatDirectSpellError) as exc:
        await cast_direct_spell(
            FakeDb(),
            session_id="sess-1",
            session=session,
            combat_obj=combat,
            caster=caster,
            caster_id="caster-1",
            spell_name="shield",
            spell_level=1,
            target_id=None,
            target_ids=None,
            spell_service_obj=ReactionSpellService(),
            flag_modified_func=lambda *_args: None,
            save_turn_state_func=save_turn_state,
            check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
        )

    assert exc.value.status_code == 400
    assert "反应法术" in exc.value.detail


@pytest.mark.asyncio
async def test_cast_direct_control_spell_applies_condition_and_duration():
    from services.combat_direct_spell_service import cast_direct_spell

    class ControlSpellService(FakeSpellService):
        def get(self, name):
            return {
                "name": name,
                "name_en": "Command",
                "level": 1,
                "type": "utility",
                "aoe": False,
                "save": None,
                "concentration": False,
                "desc": "下回合执行命令。",
            }

    session = FakeSession()
    combat = FakeCombat()
    caster = FakeCaster()

    result = await cast_direct_spell(
        FakeDb(),
        session_id="sess-1",
        session=session,
        combat_obj=combat,
        caster=caster,
        caster_id="caster-1",
        spell_name="命令术",
        spell_level=1,
        target_id="goblin-1",
        target_ids=None,
        spell_service_obj=ControlSpellService(),
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
        check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
    )

    enemy = session.game_state["enemies"][0]
    assert enemy["conditions"] == ["commanded"]
    assert enemy["condition_durations"] == {"commanded": 1}
    assert result.target_state["condition_durations"] == {"commanded": 1}
    assert result.remaining_slots == {"1st": 0}


@pytest.mark.asyncio
async def test_cast_direct_aoe_control_defaults_to_alive_enemies():
    from services.combat_direct_spell_service import cast_direct_spell

    class AoeControlSpellService(FakeSpellService):
        def get(self, name):
            return {
                "name": name,
                "level": 2,
                "type": "utility",
                "aoe": True,
                "condition": "restrained",
                "save": None,
                "concentration": True,
                "duration_rounds": 600,
                "desc": "专注1小时。",
            }

        def consume_slot(self, slots, _spell_level):
            slots = dict(slots)
            slots["2nd"] = slots.get("2nd", 0) - 1
            return slots, None

    session = FakeSession()
    combat = FakeCombat()
    caster = FakeCaster()
    caster.spell_slots = {"2nd": 1}

    result = await cast_direct_spell(
        FakeDb(),
        session_id="sess-1",
        session=session,
        combat_obj=combat,
        caster=caster,
        caster_id="caster-1",
        spell_name="网",
        spell_level=2,
        target_id=None,
        target_ids=[],
        spell_service_obj=AoeControlSpellService(),
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
        check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
    )

    assert [item["target_id"] for item in result.aoe_results] == ["goblin-1", "orc-1"]
    assert session.game_state["enemies"][0]["condition_durations"] == {"restrained": 600}
    assert session.game_state["enemies"][1].get("condition_durations") is None
    assert session.game_state["enemies"][2]["condition_durations"] == {"restrained": 600}
    assert result.remaining_slots == {"2nd": 0}
    assert caster.concentration == "网"


@pytest.mark.asyncio
async def test_cast_direct_concentration_spell_clears_previous_tracked_effects():
    from services.combat_direct_spell_service import cast_direct_spell

    class AoeControlSpellService(FakeSpellService):
        def get(self, name):
            return {
                "name": name,
                "name_en": "Web" if name == "Web" else "Bless",
                "level": 2 if name == "Web" else 1,
                "type": "utility",
                "aoe": name == "Web",
                "condition": "restrained" if name == "Web" else "blessed",
                "save": None,
                "concentration": True,
                "duration_rounds": 600 if name == "Web" else 10,
            }

        def consume_slot(self, slots, spell_level):
            slots = dict(slots)
            key = "2nd" if spell_level == 2 else "1st"
            slots[key] = slots.get(key, 0) - 1
            return slots, None

    session = FakeSession()
    combat = FakeCombat()
    caster = FakeCaster()
    caster.spell_slots = {"1st": 1, "2nd": 1}

    web = await cast_direct_spell(
        FakeDb(),
        session_id="sess-1",
        session=session,
        combat_obj=combat,
        caster=caster,
        caster_id="caster-1",
        spell_name="Web",
        spell_level=2,
        target_id=None,
        target_ids=[],
        spell_service_obj=AoeControlSpellService(),
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
        check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
    )

    assert [item["target_id"] for item in web.aoe_results] == ["goblin-1", "orc-1"]
    assert session.game_state["enemies"][0]["conditions"] == ["restrained"]
    assert session.game_state["enemies"][0]["condition_sources"]["restrained"][0]["caster_id"] == "caster-1"
    assert caster.concentration == "Web"

    combat.turn_states["caster-1"]["action_used"] = False
    bless = await cast_direct_spell(
        FakeDb(),
        session_id="sess-1",
        session=session,
        combat_obj=combat,
        caster=caster,
        caster_id="caster-1",
        spell_name="Bless",
        spell_level=1,
        target_id="goblin-1",
        target_ids=None,
        spell_service_obj=AoeControlSpellService(),
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
        check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
    )

    assert bless.target_state["conditions"] == ["blessed"]
    assert session.game_state["enemies"][0]["conditions"] == ["blessed"]
    assert session.game_state["enemies"][0]["condition_durations"] == {"blessed": 10}
    assert "condition_sources" in session.game_state["enemies"][0]
    assert "restrained" not in session.game_state["enemies"][0]["condition_sources"]
    assert session.game_state["enemies"][2].get("conditions", []) == []
    assert caster.concentration == "Bless"


@pytest.mark.asyncio
async def test_cast_direct_armor_of_agathys_defaults_to_self_target():
    from services.combat_direct_spell_service import cast_direct_spell

    class ArmorSpellService(FakeSpellService):
        def get(self, name):
            return {
                "name": name,
                "name_en": "Armor of Agathys",
                "level": 1,
                "type": "utility",
                "aoe": False,
                "concentration": False,
                "desc": "持续1小时。",
            }

    session = FakeSession()
    combat = FakeCombat()
    caster = FakeCaster()
    caster.name = "术士"
    caster.session_id = "sess-1"
    caster.hp_current = 8
    caster.death_saves = None
    caster.conditions = []
    caster.condition_durations = {}
    caster.class_resources = {}

    result = await cast_direct_spell(
        FakeDb({"caster-1": caster}),
        session_id="sess-1",
        session=session,
        combat_obj=combat,
        caster=caster,
        caster_id="caster-1",
        spell_name="寒甲",
        spell_level=2,
        target_id=None,
        target_ids=None,
        spell_service_obj=ArmorSpellService(),
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
        check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
    )

    assert result.target_id == "caster-1"
    assert result.target_state["temporary_hp_after"] == 10
    assert caster.class_resources["temporary_hp"] == 10
    assert caster.class_resources["armor_of_agathys_damage"] == 10
    assert "armor_of_agathys" in caster.conditions
    assert result.remaining_slots == {"1st": 0}
    assert result.turn_state["action_used"] is True


@pytest.mark.asyncio
async def test_cast_direct_heal_rejects_dead_target_before_consuming_slot():
    from types import SimpleNamespace

    from fastapi import HTTPException
    from services.combat_direct_spell_service import cast_direct_spell

    class HealSpellService(FakeSpellService):
        def get(self, name):
            return {
                "name": name,
                "level": 1,
                "type": "heal",
                "aoe": False,
            }

        def resolve_damage(self, *_args):
            return 0, {}

        def resolve_heal(self, *_args):
            return 8, {"formula": "1d8+3", "total": 8}

    dead_target = SimpleNamespace(
        id="ally-1",
        name="Ally",
        session_id="sess-1",
        hp_current=0,
        death_saves={"successes": 0, "failures": 3, "stable": False},
        conditions=["unconscious"],
    )
    session = FakeSession()
    combat = FakeCombat()
    caster = FakeCaster()

    with pytest.raises(HTTPException, match="Ordinary healing cannot revive"):
        await cast_direct_spell(
            FakeDb({"ally-1": dead_target}),
            session_id="sess-1",
            session=session,
            combat_obj=combat,
            caster=caster,
            caster_id="caster-1",
            spell_name="cure-wounds",
            spell_level=1,
            target_id="ally-1",
            target_ids=None,
            spell_service_obj=HealSpellService(),
            flag_modified_func=lambda *_args: None,
            save_turn_state_func=save_turn_state,
            check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
        )

    assert caster.spell_slots == {"1st": 1}
    assert combat.turn_states["caster-1"]["action_used"] is False
    assert dead_target.hp_current == 0


@pytest.mark.asyncio
async def test_cast_direct_resurrection_spell_revives_dead_target():
    from types import SimpleNamespace

    from services.combat_direct_spell_service import cast_direct_spell

    class ResurrectionSpellService(FakeSpellService):
        def get(self, name):
            return {
                "name": name,
                "name_en": "Raise Dead",
                "level": 5,
                "type": "utility",
                "aoe": False,
            }

        def consume_slot(self, slots, _spell_level):
            slots = dict(slots)
            slots["5th"] = slots.get("5th", 0) - 1
            return slots, None

    dead_target = SimpleNamespace(
        id="ally-1",
        name="Ally",
        session_id="sess-1",
        hp_current=0,
        derived={"hp_max": 12},
        condition_durations={},
        death_saves={"successes": 0, "failures": 3, "stable": False},
        conditions=["unconscious"],
    )
    session = FakeSession()
    combat = FakeCombat()
    caster = FakeCaster()
    caster.spell_slots = {"5th": 1}

    result = await cast_direct_spell(
        FakeDb({"ally-1": dead_target}),
        session_id="sess-1",
        session=session,
        combat_obj=combat,
        caster=caster,
        caster_id="caster-1",
        spell_name="复活死者",
        spell_level=5,
        target_id="ally-1",
        target_ids=None,
        spell_service_obj=ResurrectionSpellService(),
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
        check_combat_outcome_func=lambda *_args, **_kwargs: (False, None),
    )

    assert dead_target.hp_current == 1
    assert dead_target.death_saves is None
    assert dead_target.conditions == []
    assert result.target_new_hp == 1
    assert result.resurrection_results[0]["resurrected"] is True
    assert result.remaining_slots == {"5th": 0}
    assert result.turn_state["action_used"] is True
