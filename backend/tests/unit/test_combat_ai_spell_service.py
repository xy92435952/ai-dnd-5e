import pytest


class FakeSpellService:
    def __init__(self, spell):
        self.spell = spell

    def get(self, name):
        return self.spell if name == "Magic Bolt" else None

    def resolve_damage(self, spell_name, spell_level, spell_mod):
        return 6 + spell_mod, {"formula": "1d6+mod", "total": 6 + spell_mod}

    def resolve_heal(self, spell_name, spell_level, spell_mod, bonus_healing):
        return 4 + spell_mod, {"formula": "1d4+mod", "total": 4 + spell_mod}


class FakeCombatService:
    def apply_damage(self, current_hp, damage, _max_hp):
        return max(0, current_hp - damage)


class FakeCaster:
    def __init__(self):
        self.spell_slots = {"1st": 1}
        self.concentration = None


class FakeSession:
    def __init__(self):
        self.game_state = {}


class FakeDb:
    async def get(self, *_args):
        return None


@pytest.mark.asyncio
async def test_resolve_ai_spell_action_damages_enemy_and_consumes_slot():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    session = FakeSession()
    state = {
        "enemies": [{
            "id": "goblin-1",
            "name": "哥布林",
            "hp_current": 10,
            "derived": {"hp_max": 10},
        }]
    }
    enemies = state["enemies"]
    caster = FakeCaster()

    result = await resolve_ai_spell_action(
        FakeDb(),
        session=session,
        actor_name="法师",
        is_enemy=False,
        caster=caster,
        actor_derived={
            "spell_ability": "int",
            "ability_modifiers": {"int": 3},
            "spell_save_dc": 13,
        },
        decided_target_id="goblin-1",
        decided_reason="测试施法",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state=state,
        enemies=enemies,
        enemies_alive=enemies,
        all_characters=[],
        spell_service_obj=FakeSpellService({
            "level": 1,
            "type": "damage",
            "aoe": False,
            "save": None,
        }),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: None,
    )

    assert result is not None
    assert caster.spell_slots == {"1st": 0}
    assert result.damage == 9
    assert result.target_new_hp == 1
    assert result.target_name == "哥布林"
    assert "Magic Bolt" in result.mechanical_narration
    assert "测试施法" in result.mechanical_narration
    assert enemies[0]["hp_current"] == 1


@pytest.mark.asyncio
async def test_resolve_ai_spell_action_returns_none_without_slot():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    caster = FakeCaster()
    caster.spell_slots = {"1st": 0}

    result = await resolve_ai_spell_action(
        FakeDb(),
        session=FakeSession(),
        actor_name="法师",
        is_enemy=False,
        caster=caster,
        actor_derived={},
        decided_target_id="goblin-1",
        decided_reason="",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state={"enemies": []},
        enemies=[],
        enemies_alive=[],
        all_characters=[],
        spell_service_obj=FakeSpellService({"level": 1, "type": "damage", "aoe": False}),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: None,
    )

    assert result is None
