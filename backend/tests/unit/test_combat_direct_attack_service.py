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
        is_ranged=True,
        combat_service=combat_service,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.attack_result["hit"] is True
    assert prepared.attack_result["is_crit"] is False
    assert prepared.damage == 5
    assert prepared.extra_damage_notes == []
