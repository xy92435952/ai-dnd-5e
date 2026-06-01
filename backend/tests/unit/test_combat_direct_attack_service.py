import pytest

from services.combat_service import AttackResult


class FakeDb:
    async def get(self, *_args):
        return None


class FakeCombat:
    round_number = 1
    current_turn_index = 0
    turn_order = [
        {"character_id": "char-1"},
        {"character_id": "goblin-1"},
    ]
    entity_positions = {
        "char-1": {"x": 0, "y": 0},
        "goblin-1": {"x": 1, "y": 0},
    }
    grid_data = {}

    def __init__(self):
        self.turn_states = {
            "char-1": {
                "attacks_made": 0,
                "action_used": False,
                "being_helped": True,
            }
        }


class FakePlayer:
    id = "char-1"
    name = "刺客"
    char_class = "Rogue"
    level = 3
    hp_current = 18
    conditions = []
    class_resources = {}
    derived = {
        "attack_bonus": 8,
        "hit_die": 6,
        "subclass_effects": {"assassinate": True},
        "ability_modifiers": {"str": 3, "dex": 4},
    }


class FakeFighter:
    id = "char-1"
    name = "战士"
    char_class = "Fighter"
    level = 3
    hp_current = 18
    conditions = []
    class_resources = {}
    derived = {
        "attack_bonus": 8,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }


class FakeCombatService:
    def get_attack_count(self, *_args):
        return 1

    def get_attack_modifiers(self, *_args):
        return False, False

    def get_defense_modifiers(self, *_args):
        conditions = _args[0] if _args else []
        return False, "dodging" in conditions

    def resolve_melee_attack(self, **kwargs):
        self.last_attack_kwargs = kwargs
        is_forced_crit = (
            kwargs.get("target_conditions")
            and "unconscious" in kwargs["target_conditions"]
            and kwargs.get("distance", 999) <= 1
            and not kwargs.get("is_ranged", False)
        )
        return AttackResult(
            attack_roll={
                "d20": 14,
                "attack_bonus": 8,
                "attack_total": 22,
                "target_ac": 15,
                "hit": True,
                "is_crit": bool(is_forced_crit),
                **({"forced_crit": "incapacitated_target"} if is_forced_crit else {}),
                "is_fumble": False,
            },
            damage=9 if is_forced_crit else 5,
            damage_roll={"formula": "1d6+3", "rolls": [2], "total": 5},
            narration="命中",
        )

    def check_sneak_attack(self, *_args, **_kwargs):
        return False

    def calc_sneak_attack_dice(self, *_args):
        return 2

    def apply_damage_with_resistance(self, damage, *_args):
        return damage


def save_turn_state(combat, entity_id, turn_state):
    combat.turn_states[str(entity_id)] = turn_state


def ranged_fighter(*, ammo=5):
    player = FakeFighter()
    player.derived = {
        **FakeFighter.derived,
        "ranged_attack_bonus": 5,
    }
    player.equipment = {
        "weapons": [{
            "name": "Longbow",
            "damage": "1d8",
            "type": "martial_ranged",
            "properties": ["ammunition", "range(150/600)", "two-handed"],
            "equipped": True,
            "ammo": ammo,
        }]
    }
    return player


def javelin_fighter():
    player = FakeFighter()
    player.equipment = {
        "weapons": [
            {
                "name": "Javelin",
                "damage": "1d6",
                "type": "simple_melee",
                "properties": ["thrown(30/120)"],
                "equipped": True,
            },
            {
                "name": "Javelin",
                "damage": "1d6",
                "type": "simple_melee",
                "properties": ["thrown(30/120)"],
                "equipped": False,
            },
        ]
    }
    return player


@pytest.mark.asyncio
async def test_prepare_direct_attack_consumes_help_and_forces_assassinate_crit(monkeypatch):
    from services import combat_direct_attack_service as direct_attack

    monkeypatch.setattr(direct_attack, "roll_dice", lambda expr: {"formula": expr, "rolls": [3], "total": 3})
    combat_service = FakeCombatService()
    combat = FakeCombat()

    prepared = await direct_attack.prepare_direct_attack(
        FakeDb(),
        combat=combat,
        player=FakePlayer(),
        player_id="char-1",
        target_id="goblin-1",
        enemies=[{
            "id": "goblin-1",
            "name": "哥布林",
            "hp_current": 8,
            "derived": {"ac": 15},
            "conditions": [],
        }],
        is_ranged=False,
        combat_service=combat_service,
        save_turn_state_func=save_turn_state,
    )

    assert combat_service.last_attack_kwargs["advantage"] is True
    assert prepared.attack_result["is_crit"] is True
    assert prepared.damage == 8
    assert prepared.extra_damage_notes == ["暗杀暴击+3"]
    assert prepared.turn_state["being_helped"] is False
    assert prepared.ranged_penalty is False
    assert prepared.feat_power_attack is False


@pytest.mark.asyncio
async def test_prepare_direct_attack_doubles_sneak_attack_on_critical_hit(monkeypatch):
    from services import combat_damage_bonus_service
    from services import combat_direct_attack_service as direct_attack

    rolls = iter([
        {"formula": "2d6", "rolls": [3, 4], "total": 7},
        {"formula": "2d6", "rolls": [2, 4], "total": 6},
    ])
    monkeypatch.setattr(combat_damage_bonus_service, "roll_dice", lambda expr: next(rolls))
    combat_service = FakeCombatService()
    combat_service.check_sneak_attack = lambda *_args, **_kwargs: True
    combat = FakeCombat()

    def crit_attack(**kwargs):
        result = FakeCombatService.resolve_melee_attack(combat_service, **kwargs)
        result.attack_roll["is_crit"] = True
        return result

    combat_service.resolve_melee_attack = crit_attack

    prepared = await direct_attack.prepare_direct_attack(
        FakeDb(),
        combat=combat,
        player=FakePlayer(),
        player_id="char-1",
        target_id="goblin-1",
        enemies=[{
            "id": "goblin-1",
            "name": "Goblin",
            "hp_current": 20,
            "derived": {"ac": 15},
            "conditions": [],
        }],
        is_ranged=False,
        combat_service=combat_service,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.damage == 18
    assert prepared.sneak_attack_damage == 13
    assert prepared.extra_damage_notes[-1].endswith("13")


@pytest.mark.asyncio
async def test_prepare_direct_attack_applies_disadvantage_against_dodging_target():
    from services import combat_direct_attack_service as direct_attack

    combat_service = FakeCombatService()
    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    combat.turn_states["goblin-1"] = {"dodging": True}

    prepared = await direct_attack.prepare_direct_attack(
        FakeDb(),
        combat=combat,
        player=FakeFighter(),
        player_id="char-1",
        target_id="goblin-1",
        enemies=[{
            "id": "goblin-1",
            "name": "哥布林",
            "hp_current": 8,
            "derived": {"ac": 15},
            "conditions": [],
        }],
        is_ranged=False,
        combat_service=combat_service,
        save_turn_state_func=save_turn_state,
    )

    assert combat_service.last_attack_kwargs["advantage"] is False
    assert combat_service.last_attack_kwargs["disadvantage"] is True
    assert prepared.turn_state["being_helped"] is False


@pytest.mark.asyncio
async def test_prepare_direct_attack_uses_enemy_defender_interception():
    from services import combat_direct_attack_service as direct_attack

    combat_service = FakeCombatService()
    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    combat.entity_positions["guard-1"] = {"x": 1, "y": 1}

    prepared = await direct_attack.prepare_direct_attack(
        FakeDb(),
        combat=combat,
        player=FakeFighter(),
        player_id="char-1",
        target_id="goblin-1",
        enemies=[
            {
                "id": "goblin-1",
                "name": "哥布林",
                "hp_current": 8,
                "derived": {"ac": 15},
                "conditions": [],
                "tactical_role": "striker",
            },
            {
                "id": "guard-1",
                "name": "盾卫",
                "hp_current": 18,
                "derived": {"ac": 16},
                "conditions": [],
                "tactical_role": "defender",
            },
        ],
        is_ranged=False,
        combat_service=combat_service,
        save_turn_state_func=save_turn_state,
    )

    assert combat_service.last_attack_kwargs["disadvantage"] is True
    assert prepared.defender_interception["defender_id"] == "guard-1"
    assert prepared.attack_result["defender_interception"]["defender_name"] == "盾卫"
    assert prepared.extra_damage_notes == ["盾卫护卫干扰"]
    assert combat.turn_states["guard-1"]["reaction_used"] is True


@pytest.mark.asyncio
async def test_prepare_direct_attack_applies_hex_on_marked_target(monkeypatch):
    from services import combat_damage_bonus_service
    from services import combat_direct_attack_service as direct_attack

    monkeypatch.setattr(combat_damage_bonus_service, "roll_dice", lambda expr: {"formula": expr, "rolls": [4], "total": 4})
    combat_service = FakeCombatService()
    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    player = FakeFighter()
    player.concentration = "Hex"

    prepared = await direct_attack.prepare_direct_attack(
        FakeDb(),
        combat=combat,
        player=player,
        player_id="char-1",
        target_id="goblin-1",
        enemies=[{
            "id": "goblin-1",
            "name": "哥布林",
            "hp_current": 12,
            "derived": {"ac": 15},
            "conditions": ["hexed"],
        }],
        is_ranged=False,
        combat_service=combat_service,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.damage == 9
    assert prepared.extra_damage_notes == ["Hex+4"]


@pytest.mark.asyncio
async def test_prepare_direct_attack_doubles_hex_on_critical_hit(monkeypatch):
    from services import combat_damage_bonus_service
    from services import combat_direct_attack_service as direct_attack

    rolls = iter([
        {"formula": "1d6", "rolls": [4], "total": 4},
        {"formula": "1d6", "rolls": [5], "total": 5},
    ])
    monkeypatch.setattr(combat_damage_bonus_service, "roll_dice", lambda expr: next(rolls))
    combat_service = FakeCombatService()
    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    player = FakeFighter()
    player.concentration = "Hex"

    def crit_attack(**kwargs):
        result = FakeCombatService.resolve_melee_attack(combat_service, **kwargs)
        result.attack_roll["is_crit"] = True
        return result

    combat_service.resolve_melee_attack = crit_attack

    prepared = await direct_attack.prepare_direct_attack(
        FakeDb(),
        combat=combat,
        player=player,
        player_id="char-1",
        target_id="goblin-1",
        enemies=[{
            "id": "goblin-1",
            "name": "Goblin",
            "hp_current": 12,
            "derived": {"ac": 15},
            "conditions": ["hexed"],
        }],
        is_ranged=False,
        combat_service=combat_service,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.damage == 14
    assert prepared.extra_damage_notes == ["Hex+9"]


@pytest.mark.asyncio
async def test_prepare_direct_attack_forces_close_unconscious_target_crit(monkeypatch):
    from services import combat_direct_attack_service as direct_attack

    combat_service = FakeCombatService()
    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False

    prepared = await direct_attack.prepare_direct_attack(
        FakeDb(),
        combat=combat,
        player=FakeFighter(),
        player_id="char-1",
        target_id="goblin-1",
        enemies=[{
            "id": "goblin-1",
            "name": "哥布林",
            "hp_current": 8,
            "derived": {"ac": 15},
            "conditions": ["unconscious"],
        }],
        is_ranged=False,
        combat_service=combat_service,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.attack_result["hit"] is True
    assert prepared.attack_result["is_crit"] is True
    assert prepared.attack_result["forced_crit"] == "incapacitated_target"
    assert prepared.damage == 9
    assert prepared.extra_damage_notes == []


@pytest.mark.asyncio
async def test_prepare_direct_attack_does_not_force_ranged_unconscious_target_crit(monkeypatch):
    from services import combat_direct_attack_service as direct_attack

    monkeypatch.setattr(direct_attack, "roll_dice", lambda expr: {"formula": expr, "rolls": [4], "total": 4})
    combat_service = FakeCombatService()
    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False

    prepared = await direct_attack.prepare_direct_attack(
        FakeDb(),
        combat=combat,
        player=ranged_fighter(),
        player_id="char-1",
        target_id="goblin-1",
        enemies=[{
            "id": "goblin-1",
            "name": "哥布林",
            "hp_current": 8,
            "derived": {"ac": 15},
            "conditions": ["unconscious"],
        }],
        is_ranged=True,
        combat_service=combat_service,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.attack_result["hit"] is True
    assert prepared.attack_result["is_crit"] is False
    assert prepared.damage == 5
    assert prepared.extra_damage_notes == []


@pytest.mark.asyncio
async def test_prepare_direct_ranged_attack_against_distant_prone_target_has_disadvantage():
    from services import combat_direct_attack_service as direct_attack

    combat_service = FakeCombatService()
    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    combat.entity_positions["goblin-1"] = {"x": 4, "y": 0}

    prepared = await direct_attack.prepare_direct_attack(
        FakeDb(),
        combat=combat,
        player=ranged_fighter(),
        player_id="char-1",
        target_id="goblin-1",
        enemies=[{
            "id": "goblin-1",
            "name": "Goblin",
            "hp_current": 8,
            "derived": {"ac": 15},
            "conditions": ["prone"],
        }],
        is_ranged=True,
        combat_service=combat_service,
        save_turn_state_func=save_turn_state,
    )

    assert combat_service.last_attack_kwargs["advantage"] is False
    assert combat_service.last_attack_kwargs["disadvantage"] is True
    assert prepared.attack_result["hit"] is True


@pytest.mark.asyncio
async def test_prepare_direct_ranged_attack_consumes_ammunition():
    from services import combat_direct_attack_service as direct_attack

    combat_service = FakeCombatService()
    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    player = ranged_fighter(ammo=2)

    prepared = await direct_attack.prepare_direct_attack(
        FakeDb(),
        combat=combat,
        player=player,
        player_id="char-1",
        target_id="goblin-1",
        enemies=[{
            "id": "goblin-1",
            "name": "Goblin",
            "hp_current": 8,
            "derived": {"ac": 15},
            "conditions": [],
        }],
        is_ranged=True,
        combat_service=combat_service,
        save_turn_state_func=save_turn_state,
    )

    assert player.equipment["weapons"][0]["ammo"] == 1
    assert prepared.weapon_resource == {
        "weapon": "Longbow",
        "resource_type": "ammunition",
        "consumed": True,
        "ammo_remaining": 1,
    }


@pytest.mark.asyncio
async def test_prepare_direct_ranged_attack_consumes_thrown_weapon_copy():
    from services import combat_direct_attack_service as direct_attack

    combat_service = FakeCombatService()
    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    player = javelin_fighter()

    prepared = await direct_attack.prepare_direct_attack(
        FakeDb(),
        combat=combat,
        player=player,
        player_id="char-1",
        target_id="goblin-1",
        enemies=[{
            "id": "goblin-1",
            "name": "Goblin",
            "hp_current": 8,
            "derived": {"ac": 15},
            "conditions": [],
        }],
        is_ranged=True,
        combat_service=combat_service,
        save_turn_state_func=save_turn_state,
    )

    assert [weapon["name"] for weapon in player.equipment["weapons"]] == ["Javelin"]
    assert player.equipment["weapons"][0]["equipped"] is True
    assert prepared.weapon_resource == {
        "weapon": "Javelin",
        "resource_type": "thrown_weapon",
        "consumed": True,
        "weapon_removed": True,
    }


@pytest.mark.asyncio
async def test_prepare_direct_ranged_attack_rejects_missing_ranged_weapon():
    from services import combat_direct_attack_service as direct_attack
    from services.combat_attack_roll_service import CombatAttackRollError

    combat_service = FakeCombatService()
    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False

    with pytest.raises(CombatAttackRollError) as exc:
        await direct_attack.prepare_direct_attack(
            FakeDb(),
            combat=combat,
            player=FakeFighter(),
            player_id="char-1",
            target_id="goblin-1",
            enemies=[{
                "id": "goblin-1",
                "name": "Goblin",
                "hp_current": 8,
                "derived": {"ac": 15},
                "conditions": [],
            }],
            is_ranged=True,
            combat_service=combat_service,
            save_turn_state_func=save_turn_state,
        )

    assert exc.value.status_code == 400
    assert "No ranged or thrown weapon available" in exc.value.detail


def test_dark_ones_blessing_note_grants_real_temporary_hp():
    from services.combat_direct_attack_service import apply_dark_ones_blessing_note

    player = FakeFighter()
    player.class_resources = {}
    player.condition_durations = {}
    notes = apply_dark_ones_blessing_note(
        player=player,
        target_new_hp=0,
        target_is_enemy=True,
        subclass_effects={"dark_ones_blessing": True},
        player_derived={"ability_modifiers": {"cha": 3}},
        player_level=4,
        extra_damage_notes=[],
    )

    assert notes == ["黑暗祝福+7临时HP"]
    assert player.class_resources["temporary_hp"] == 7
    assert player.class_resources["temporary_hp_source"] == "dark_ones_blessing"
