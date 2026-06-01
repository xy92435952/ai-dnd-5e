import pytest


class FakeSpellService:
    def __init__(self, spell, spell_name="Magic Bolt"):
        self.spell = spell
        self.spell_name = spell_name

    def get(self, name):
        return self.spell if name == self.spell_name else None

    def resolve_damage(self, spell_name, spell_level, spell_mod):
        return 6 + spell_mod, {"formula": "1d6+mod", "total": 6 + spell_mod}

    def resolve_heal(self, spell_name, spell_level, spell_mod, bonus_healing):
        return 4 + spell_mod, {"formula": "1d4+mod", "total": 4 + spell_mod}


class FakeComponentSpellService(FakeSpellService):
    def __init__(self, spell, total, components):
        super().__init__(spell)
        self.total = total
        self.components = components

    def resolve_damage(self, spell_name, spell_level, spell_mod):
        return self.total + spell_mod, {
            "total": self.total + spell_mod,
            "damage_components": self.components,
        }


class FakeCombatService:
    def apply_damage(self, current_hp, damage, _max_hp):
        return max(0, current_hp - damage)

    def apply_damage_with_resistance(self, damage, damage_type, resistances, immunities, vulnerabilities):
        from services.combat_damage_service import apply_damage_with_resistance

        return apply_damage_with_resistance(damage, damage_type, resistances, immunities, vulnerabilities)


class FakeCaster:
    def __init__(self):
        self.id = "caster-1"
        self.spell_slots = {"1st": 1}
        self.concentration = None


class FakeSession:
    def __init__(
        self,
        *,
        game_state=None,
        player_character_id=None,
        is_multiplayer=False,
        session_id="session-1",
    ):
        self.id = session_id
        self.game_state = game_state or {}
        self.player_character_id = player_character_id
        self.is_multiplayer = is_multiplayer


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
    class_resources = {}
    death_saves = None

    def __init__(self, hp_current=20):
        self.hp_current = hp_current
        self.conditions = []
        self.condition_durations = {}
        self.class_resources = {}
        self.concentration = None
        self.death_saves = None


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
async def test_resolve_ai_spell_action_rejects_missing_damage_target_before_slot():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    class NoRollSpellService(FakeSpellService):
        def resolve_damage(self, *_args):
            raise AssertionError("invalid AI spell target should fail before damage")

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
        session=FakeSession(game_state=state),
        actor_name="Wizard",
        is_enemy=False,
        caster=caster,
        actor_derived={
            "spell_ability": "int",
            "ability_modifiers": {"int": 3},
            "spell_save_dc": 13,
        },
        decided_target_id="missing-target",
        decided_reason="bad target",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state=state,
        enemies=enemies,
        enemies_alive=enemies,
        all_characters=[],
        spell_service_obj=NoRollSpellService({
            "level": 1,
            "type": "damage",
            "aoe": False,
            "save": None,
        }),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: (_ for _ in ()).throw(AssertionError("no persistence expected")),
    )

    assert result is None
    assert caster.spell_slots == {"1st": 1}
    assert enemies[0]["hp_current"] == 10


@pytest.mark.asyncio
async def test_resolve_ai_spell_action_rejects_dead_damage_target_before_slot():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    class NoRollSpellService(FakeSpellService):
        def resolve_damage(self, *_args):
            raise AssertionError("dead AI spell target should fail before damage")

    dead_enemy = {
        "id": "goblin-1",
        "name": "Goblin",
        "hp_current": 0,
        "derived": {"hp_max": 10},
    }
    state = {"enemies": [dead_enemy]}
    caster = FakeCaster()

    result = await resolve_ai_spell_action(
        FakeDb(),
        session=FakeSession(game_state=state),
        actor_name="Wizard",
        is_enemy=False,
        caster=caster,
        actor_derived={
            "spell_ability": "int",
            "ability_modifiers": {"int": 3},
            "spell_save_dc": 13,
        },
        decided_target_id="goblin-1",
        decided_reason="bad target",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state=state,
        enemies=state["enemies"],
        enemies_alive=[],
        all_characters=[],
        spell_service_obj=NoRollSpellService({
            "level": 1,
            "type": "damage",
            "aoe": False,
            "save": None,
        }),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: (_ for _ in ()).throw(AssertionError("no persistence expected")),
    )

    assert result is None
    assert caster.spell_slots == {"1st": 1}
    assert dead_enemy["hp_current"] == 0


@pytest.mark.asyncio
async def test_resolve_ai_spell_action_rejects_out_of_range_target_before_slot():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    class NoRollSpellService(FakeSpellService):
        def resolve_damage(self, *_args):
            raise AssertionError("out-of-range AI spell target should fail before damage")

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
        session=FakeSession(game_state=state),
        actor_name="Wizard",
        is_enemy=False,
        caster=caster,
        actor_derived={
            "spell_ability": "int",
            "ability_modifiers": {"int": 3},
            "spell_save_dc": 13,
        },
        decided_target_id="goblin-1",
        decided_reason="bad range",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state=state,
        enemies=enemies,
        enemies_alive=enemies,
        all_characters=[],
        spell_service_obj=NoRollSpellService({
            "level": 1,
            "type": "damage",
            "aoe": False,
            "save": None,
            "range": 12,
        }),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: (_ for _ in ()).throw(AssertionError("no persistence expected")),
        positions={
            "caster-1": {"x": 0, "y": 0},
            "goblin-1": {"x": 13, "y": 0},
        },
    )

    assert result is None
    assert caster.spell_slots == {"1st": 1}
    assert enemies[0]["hp_current"] == 10


@pytest.mark.asyncio
async def test_resolve_enemy_ai_spell_action_consumes_dict_slot_and_sets_concentration():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    enemy_caster = {
        "id": "enemy-mage",
        "name": "Enemy Mage",
        "spell_slots": {"1st": 1},
        "concentration": None,
    }
    state = {"enemies": [enemy_caster]}
    session = FakeSession()
    flagged = []

    result = await resolve_ai_spell_action(
        FakeDb(),
        session=session,
        actor_name="Enemy Mage",
        is_enemy=True,
        caster=enemy_caster,
        actor_derived={},
        decided_target_id=None,
        decided_reason="test concentration",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state=state,
        enemies=state["enemies"],
        enemies_alive=state["enemies"],
        all_characters=[],
        spell_service_obj=FakeSpellService({
            "level": 1,
            "type": "utility",
            "concentration": True,
        }),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda _obj, attr: flagged.append(attr),
    )

    assert result is not None
    assert enemy_caster["spell_slots"] == {"1st": 0}
    assert enemy_caster["concentration"] == "Magic Bolt"
    assert session.game_state["enemies"][0]["concentration"] == "Magic Bolt"
    assert "game_state" in flagged


@pytest.mark.asyncio
async def test_resolve_enemy_ai_heal_spell_restores_enemy_ally_and_persists_state():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    enemy_healer = {
        "id": "enemy-priest",
        "name": "Enemy Priest",
        "spell_slots": {"1st": 1},
    }
    wounded_ally = {
        "id": "enemy-guard",
        "name": "Enemy Guard",
        "hp_current": 3,
        "hp_max": 12,
        "derived": {"hp_max": 12},
    }
    state = {"enemies": [enemy_healer, wounded_ally]}
    session = FakeSession(game_state=state)
    flagged = []

    result = await resolve_ai_spell_action(
        FakeDb(),
        session=session,
        actor_name="Enemy Priest",
        is_enemy=True,
        caster=enemy_healer,
        actor_derived={
            "spell_ability": "wis",
            "ability_modifiers": {"wis": 2},
        },
        decided_target_id="enemy-guard",
        decided_reason="heal ally",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state=state,
        enemies=state["enemies"],
        enemies_alive=state["enemies"],
        all_characters=[],
        spell_service_obj=FakeSpellService(
            {"level": 1, "type": "heal", "heal_dice": "1d4"},
            spell_name="Magic Bolt",
        ),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda _obj, attr: flagged.append(attr),
    )

    assert result is not None
    assert enemy_healer["spell_slots"] == {"1st": 0}
    assert wounded_ally["hp_current"] == 9
    assert result.heal == 6
    assert result.target_new_hp == 9
    assert result.target_name == "Enemy Guard"
    assert session.game_state["enemies"][1]["hp_current"] == 9
    assert "game_state" in flagged


@pytest.mark.asyncio
async def test_resolve_enemy_ai_heal_spell_skips_undead_ally_before_consuming_slot():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    class NoRollHealSpellService(FakeSpellService):
        def resolve_heal(self, *_args):
            raise AssertionError("undead healing should fail before rolling")

    enemy_healer = {
        "id": "enemy-priest",
        "name": "Enemy Priest",
        "spell_slots": {"1st": 1},
    }
    undead_ally = {
        "id": "enemy-wight",
        "name": "Enemy Wight",
        "type": "undead",
        "hp_current": 3,
        "hp_max": 12,
        "derived": {"hp_max": 12},
    }
    state = {"enemies": [enemy_healer, undead_ally]}
    session = FakeSession(game_state=state)
    flagged = []

    result = await resolve_ai_spell_action(
        FakeDb(),
        session=session,
        actor_name="Enemy Priest",
        is_enemy=True,
        caster=enemy_healer,
        actor_derived={
            "spell_ability": "wis",
            "ability_modifiers": {"wis": 2},
        },
        decided_target_id="enemy-wight",
        decided_reason="heal ally",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state=state,
        enemies=state["enemies"],
        enemies_alive=state["enemies"],
        all_characters=[],
        spell_service_obj=NoRollHealSpellService(
            {"level": 1, "type": "heal", "heal_dice": "1d4"},
            spell_name="Magic Bolt",
        ),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda _obj, attr: flagged.append(attr),
    )

    assert result is None
    assert enemy_healer["spell_slots"] == {"1st": 1}
    assert undead_ally["hp_current"] == 3
    assert flagged == []


@pytest.mark.asyncio
async def test_ai_heal_spell_effect_skips_undead_enemy_before_rolling():
    from services.combat_ai_spell_effect_service import apply_ai_heal_spell
    from services.combat_ai_spell_models import AiSpellResolution

    class NoRollHealSpellService(FakeSpellService):
        def resolve_heal(self, *_args):
            raise AssertionError("undead healing should fail before rolling")

    undead_ally = {
        "id": "enemy-wight",
        "name": "Enemy Wight",
        "type": "undead",
        "hp_current": 3,
        "hp_max": 12,
        "derived": {"hp_max": 12},
    }
    enemies = [undead_ally]
    state = {"enemies": enemies}
    resolution = AiSpellResolution(
        spell_name="Magic Bolt",
        spell_level=1,
        spell_target="enemy-wight",
        spell_data={"level": 1, "type": "heal", "heal_dice": "1d4"},
        is_cantrip=False,
    )
    flagged = []

    await apply_ai_heal_spell(
        FakeDb(),
        resolution=resolution,
        spell_mod=2,
        bonus_healing=False,
        spell_service_obj=NoRollHealSpellService(
            {"level": 1, "type": "heal", "heal_dice": "1d4"},
            spell_name="Magic Bolt",
        ),
        session=FakeSession(game_state=state),
        state=state,
        enemies=enemies,
        flag_modified_func=lambda _obj, attr: flagged.append(attr),
    )

    assert resolution.heal == 0
    assert resolution.target_new_hp is None
    assert undead_ally["hp_current"] == 3
    assert flagged == []


@pytest.mark.asyncio
async def test_resolve_enemy_ai_control_spell_tracks_character_condition_source():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    character = FakeCharacter(hp_current=20)
    enemy_caster = {
        "id": "enemy-mage",
        "name": "Enemy Mage",
        "spell_slots": {"1st": 1},
        "concentration": None,
    }
    state = {"enemies": [enemy_caster]}

    result = await resolve_ai_spell_action(
        CharacterDb(character),
        session=FakeSession(player_character_id=character.id),
        actor_name="Enemy Mage",
        is_enemy=True,
        caster=enemy_caster,
        actor_derived={"spell_save_dc": 13},
        decided_target_id=character.id,
        decided_reason="test hex",
        decision={"action_type": "spell", "action_name": "Hex", "spell_level": 1},
        state=state,
        enemies=state["enemies"],
        enemies_alive=state["enemies"],
        all_characters=[{"id": character.id, "hp_current": 20}],
        spell_service_obj=FakeSpellService(
            {
                "level": 1,
                "type": "control",
                "concentration": True,
                "condition": "hexed",
                "save": None,
                "duration_rounds": 600,
            },
            spell_name="Hex",
        ),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: None,
    )

    assert result is not None
    assert enemy_caster["spell_slots"] == {"1st": 0}
    assert enemy_caster["concentration"] == "Hex"
    assert character.conditions == ["hexed"]
    assert character.condition_durations == {"hexed": 600}
    sources = character.class_resources["condition_sources"]["hexed"]
    assert sources[0]["caster_id"] == "enemy-mage"
    assert sources[0]["spell_name"] == "Hex"
    assert sources[0]["added_condition"] is True


@pytest.mark.asyncio
async def test_enemy_ai_concentration_replacement_clears_previous_character_condition():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    character = FakeCharacter(hp_current=20)
    character.conditions = ["hexed"]
    character.condition_durations = {"hexed": 600}
    character.class_resources = {
        "condition_sources": {
            "hexed": [{
                "source_type": "concentration",
                "caster_id": "enemy-mage",
                "spell_name": "Hex",
                "target_id": character.id,
                "added_condition": True,
                "had_previous_duration": False,
                "previous_duration": None,
            }]
        }
    }
    enemy_caster = {
        "id": "enemy-mage",
        "name": "Enemy Mage",
        "spell_slots": {"1st": 1},
        "concentration": "Hex",
    }
    state = {"enemies": [enemy_caster]}

    result = await resolve_ai_spell_action(
        CharacterDb(character),
        session=FakeSession(player_character_id=character.id),
        actor_name="Enemy Mage",
        is_enemy=True,
        caster=enemy_caster,
        actor_derived={},
        decided_target_id=None,
        decided_reason="replace concentration",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state=state,
        enemies=state["enemies"],
        enemies_alive=state["enemies"],
        all_characters=[{"id": character.id, "hp_current": 20}],
        spell_service_obj=FakeSpellService({
            "level": 1,
            "type": "utility",
            "concentration": True,
        }),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: None,
    )

    assert result is not None
    assert enemy_caster["concentration"] == "Magic Bolt"
    assert character.conditions == []
    assert character.condition_durations == {}
    assert "condition_sources" not in character.class_resources


@pytest.mark.asyncio
async def test_resolve_ai_spell_action_respects_enemy_spell_immunity():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    session = FakeSession()
    state = {
        "enemies": [{
            "id": "fire-elemental-1",
            "name": "Fire Elemental",
            "hp_current": 10,
            "derived": {"hp_max": 10},
            "immunities": ["火焰"],
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
        decided_target_id="fire-elemental-1",
        decided_reason="test cast",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state=state,
        enemies=enemies,
        enemies_alive=enemies,
        all_characters=[],
        spell_service_obj=FakeSpellService({
            "name_en": "Fireball",
            "level": 1,
            "type": "damage",
            "aoe": False,
            "save": None,
            "damage_type": "fire",
        }),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: None,
    )

    assert result is not None
    assert result.damage == 0
    assert result.target_new_hp == 10
    assert enemies[0]["hp_current"] == 10


@pytest.mark.asyncio
async def test_resolve_ai_spell_action_respects_enemy_component_immunity():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    session = FakeSession()
    state = {
        "enemies": [{
            "id": "fire-elemental-1",
            "name": "Fire Elemental",
            "hp_current": 40,
            "derived": {"hp_max": 40},
            "immunities": ["fire"],
        }]
    }
    enemies = state["enemies"]

    result = await resolve_ai_spell_action(
        FakeDb(),
        session=session,
        actor_name="Wizard",
        is_enemy=False,
        caster=FakeCaster(),
        actor_derived={
            "spell_ability": "int",
            "ability_modifiers": {"int": 0},
            "spell_save_dc": 13,
        },
        decided_target_id="fire-elemental-1",
        decided_reason="test cast",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state=state,
        enemies=enemies,
        enemies_alive=enemies,
        all_characters=[],
        spell_service_obj=FakeComponentSpellService(
            {
                "name_en": "Meteor Swarm",
                "level": 1,
                "type": "damage",
                "aoe": False,
                "save": None,
            },
            40,
            [
                {"damage": 24, "damage_type": "fire"},
                {"damage": 16, "damage_type": "bludgeoning"},
            ],
        ),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: None,
    )

    assert result is not None
    assert result.damage == 16
    assert result.target_new_hp == 24
    assert enemies[0]["hp_current"] == 24


@pytest.mark.asyncio
async def test_resolve_enemy_ai_spell_respects_character_fire_resistance():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    character = FakeCharacter(hp_current=20)
    character.conditions = ["fire_resistance"]
    session = FakeSession()

    result = await resolve_ai_spell_action(
        CharacterDb(character),
        session=session,
        actor_name="Enemy Mage",
        is_enemy=True,
        caster=FakeCaster(),
        actor_derived={
            "spell_ability": "int",
            "ability_modifiers": {"int": 3},
            "spell_save_dc": 13,
        },
        decided_target_id=character.id,
        decided_reason="test cast",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state={"enemies": []},
        enemies=[],
        enemies_alive=[],
        all_characters=[{"id": character.id, "hp_current": 20}],
        spell_service_obj=FakeSpellService({
            "name_en": "Fireball",
            "level": 1,
            "type": "damage",
            "aoe": False,
            "save": None,
            "damage_type": "fire",
        }),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: None,
    )

    assert result is not None
    assert result.damage == 4
    assert result.target_new_hp == 16
    assert character.hp_current == 16


@pytest.mark.asyncio
async def test_resolve_enemy_ai_spell_respects_character_component_resistance():
    from services.combat_ai_spell_service import resolve_ai_spell_action

    character = FakeCharacter(hp_current=30)
    character.conditions = ["cold_resistance"]
    session = FakeSession()

    result = await resolve_ai_spell_action(
        CharacterDb(character),
        session=session,
        actor_name="Enemy Mage",
        is_enemy=True,
        caster=FakeCaster(),
        actor_derived={
            "spell_ability": "int",
            "ability_modifiers": {"int": 0},
            "spell_save_dc": 13,
        },
        decided_target_id=character.id,
        decided_reason="test cast",
        decision={"action_type": "spell", "action_name": "Magic Bolt", "spell_level": 1},
        state={"enemies": []},
        enemies=[],
        enemies_alive=[],
        all_characters=[{"id": character.id, "hp_current": 30}],
        spell_service_obj=FakeComponentSpellService(
            {
                "name_en": "Ice Storm",
                "level": 1,
                "type": "damage",
                "aoe": False,
                "save": None,
            },
            20,
            [
                {"damage": 8, "damage_type": "bludgeoning"},
                {"damage": 12, "damage_type": "cold"},
            ],
        ),
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: None,
    )

    assert result is not None
    assert result.damage == 14
    assert result.target_new_hp == 16
    assert character.hp_current == 16


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


def test_damage_after_ai_save_evasion_success_takes_no_damage():
    from services.combat_ai_spell_damage_service import damage_after_ai_save

    damage = damage_after_ai_save(
        {
            "id": "rogue-1",
            "char_class": "Rogue",
            "level": 7,
            "derived": {
                "ability_modifiers": {"dex": 5},
                "saving_throws": {"dex": 8},
            },
        },
        base_damage=24,
        spell_data={"save": "dex", "half_on_save": True},
        spell_save_dc=10,
        roll_dice_func=lambda expr: {"rolls": [10], "total": 10},
    )

    assert damage == 0


def test_damage_after_ai_enemy_save_infers_single_target_half_on_save_from_description():
    from services.combat_ai_spell_damage_service import damage_after_ai_enemy_save

    damage = damage_after_ai_enemy_save(
        {
            "id": "goblin-1",
            "derived": {
                "ability_modifiers": {"dex": 5},
                "saving_throws": {"dex": 8},
            },
        },
        base_damage=22,
        spell_data={"save": "dex", "desc": "DEX豁免失败受伤，成功减半"},
        spell_save_dc=10,
        roll_dice_func=lambda expr: {"rolls": [10], "total": 10},
    )

    assert damage == 11


def test_damage_after_ai_enemy_save_success_zeroes_cantrip_without_half_on_save():
    from services.combat_ai_spell_damage_service import damage_after_ai_enemy_save

    damage = damage_after_ai_enemy_save(
        {
            "id": "goblin-1",
            "derived": {
                "ability_modifiers": {"dex": 5},
                "saving_throws": {"dex": 8},
            },
        },
        base_damage=8,
        spell_data={"save": "dex", "desc": "DEX豁免失败受伤，豁免无效"},
        spell_save_dc=10,
        roll_dice_func=lambda expr: {"rolls": [10], "total": 10},
    )

    assert damage == 0


def test_damage_after_ai_enemy_save_uses_legendary_resistance():
    from services.combat_ai_spell_damage_service import resolve_ai_save_damage

    enemy = {
        "id": "dragon-1",
        "derived": {
            "ability_modifiers": {"dex": -5},
            "saving_throws": {"dex": -5},
        },
        "legendary_resistances": 3,
        "legendary_resistances_remaining": 1,
    }

    result = resolve_ai_save_damage(
        enemy,
        base_damage=22,
        spell_data={"save": "dex", "half_on_save": False},
        spell_save_dc=30,
        roll_dice_func=lambda expr: {"rolls": [1], "total": 1},
        half_on_save_default=False,
    )

    assert result["damage"] == 0
    assert result["save_result"]["success"] is True
    assert result["save_result"]["legendary_resistance_used"] is True
    assert enemy["legendary_resistances_remaining"] == 0


def test_damage_after_ai_character_save_applies_evasion_to_character_object():
    from services.combat_ai_spell_damage_service import damage_after_ai_character_save

    damage = damage_after_ai_character_save(
        FakeCharacter(),
        base_damage=24,
        spell_data={"save": "dex", "half_on_save": True},
        spell_save_dc=10,
        roll_dice_func=lambda expr: {"rolls": [10], "total": 10},
    )

    assert damage == 0


def test_resolve_ai_spell_level_defaults_to_spell_registry_level():
    from services.combat_ai_spell_service import resolve_ai_spell_level

    assert resolve_ai_spell_level({}, {"level": 3}) == 3
    assert resolve_ai_spell_level({"spell_level": 1}, {"level": 3}) == 3
    assert resolve_ai_spell_level({"spell_level": 5}, {"level": 3}) == 5


@pytest.mark.asyncio
async def test_ai_control_spell_uses_legendary_resistance():
    from services.combat_ai_spell_effect_service import apply_ai_control_spell
    from services.combat_ai_spell_models import AiSpellResolution

    enemies = [{
        "id": "dragon-1",
        "name": "Dragon",
        "derived": {
            "ability_modifiers": {"wis": -5},
            "saving_throws": {"wis": -5},
        },
        "conditions": [],
        "legendary_resistances": 3,
        "legendary_resistances_remaining": 1,
    }]
    state = {"enemies": enemies}
    session = FakeSession()
    resolution = AiSpellResolution(
        spell_name="Hold Person",
        spell_level=2,
        spell_target="dragon-1",
        spell_data={"save": "wis"},
        is_cantrip=False,
    )

    await apply_ai_control_spell(
        FakeDb(),
        resolution=resolution,
        session=session,
        enemies=enemies,
        spell_save_dc=30,
        state=state,
        flag_modified_func=lambda *_args: None,
        roll_dice_func=lambda expr: {"rolls": [1], "total": 1},
    )

    assert enemies[0]["conditions"] == []
    assert enemies[0]["legendary_resistances_remaining"] == 0
    assert resolution.target_state is None
    assert resolution.target_name == "Dragon"
    assert len(resolution.narration_parts) == 1


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
