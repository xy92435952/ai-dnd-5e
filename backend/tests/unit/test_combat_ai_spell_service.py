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
            "name": "Goblin",
            "hp_current": 10,
            "derived": {"hp_max": 10},
        }]
    }
    enemies = state["enemies"]
    caster = FakeCaster()

    result = await resolve_ai_spell_action(
        FakeDb(),
        session=session,
        actor_name="Wizard",
        is_enemy=False,
        caster=caster,
        actor_derived={
            "spell_ability": "int",
            "ability_modifiers": {"int": 3},
            "spell_save_dc": 13,
        },
        decided_target_id="goblin-1",
        decided_reason="test cast",
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
    assert result.target_name == "Goblin"
    assert "Magic Bolt" in result.mechanical_narration
    assert "test cast" in result.mechanical_narration
    assert enemies[0]["hp_current"] == 1


@pytest.mark.asyncio
async def test_resolve_ai_spell_action_returns_none_without_slot():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    caster = FakeCaster()
    caster.spell_slots = {"1st": 0}

    result = await resolve_ai_spell_action(
        FakeDb(),
        session=FakeSession(),
        actor_name="Wizard",
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


def test_damage_after_ai_save_auto_fails_dex_save_when_stunned():
    from services.combat_ai_spell_damage_service import damage_after_ai_save

    damage = damage_after_ai_save(
        {
            "derived": {
                "ability_modifiers": {"dex": 20},
                "saving_throws": {"dex": 20},
            },
            "conditions": ["stunned"],
        },
        base_damage=24,
        spell_data={"save": "dex", "half_on_save": True},
        spell_save_dc=10,
        roll_dice_func=lambda expr: {"rolls": [20], "total": 20},
    )

    assert damage == 24


@pytest.mark.asyncio
async def test_ai_control_spell_auto_fails_unconscious_enemy_dex_save():
    from services.combat_ai_spell_effect_service import apply_ai_control_spell
    from services.combat_ai_spell_models import AiSpellResolution

    enemies = [{
        "id": "goblin-1",
        "name": "Goblin",
        "derived": {
            "ability_modifiers": {"dex": 20},
            "saving_throws": {"dex": 20},
        },
        "conditions": ["unconscious"],
    }]
    state = {"enemies": enemies}
    resolution = AiSpellResolution(
        spell_name="Faerie Fire",
        spell_level=1,
        spell_target="goblin-1",
        spell_data={"save": "dex"},
        is_cantrip=False,
    )

    await apply_ai_control_spell(
        FakeDb(),
        resolution=resolution,
        session=FakeSession(),
        enemies=enemies,
        spell_save_dc=10,
        state=state,
        flag_modified_func=lambda *_args: None,
        roll_dice_func=lambda expr: {"rolls": [20], "total": 20},
    )

    assert "faerie_fire" in enemies[0]["conditions"]
    assert enemies[0]["condition_durations"] == {"faerie_fire": 10}
    assert resolution.target_state["condition_durations"] == {"faerie_fire": 10}
    assert resolution.target_name == "Goblin"


@pytest.mark.asyncio
async def test_ai_control_spell_applies_no_save_bless_condition():
    from services.combat_ai_spell_effect_service import apply_ai_control_spell
    from services.combat_ai_spell_models import AiSpellResolution

    enemies = [{
        "id": "ally-1",
        "name": "Ally",
        "conditions": [],
    }]
    state = {"enemies": enemies}
    session = FakeSession()
    resolution = AiSpellResolution(
        spell_name="Bless",
        spell_level=1,
        spell_target="ally-1",
        spell_data={"name_en": "Bless", "save": None},
        is_cantrip=False,
    )

    await apply_ai_control_spell(
        FakeDb(),
        resolution=resolution,
        session=session,
        enemies=enemies,
        spell_save_dc=13,
        state=state,
        flag_modified_func=lambda *_args: None,
    )

    assert enemies[0]["conditions"] == ["blessed"]
    assert enemies[0]["condition_durations"] == {"blessed": 10}
    assert resolution.target_state["conditions"] == ["blessed"]
    assert session.game_state["enemies"][0]["conditions"] == ["blessed"]
