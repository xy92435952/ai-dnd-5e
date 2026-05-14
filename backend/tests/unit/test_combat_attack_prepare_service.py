import pytest

from services.combat_attack_roll_service import CombatAttackRollError


class FakeDb:
    async def get(self, *_args):
        return None


class FakeCombat:
    def __init__(self):
        self.turn_states = {
            "char-1": {
                "attacks_made": 0,
                "action_used": False,
                "bonus_action_used": False,
                "being_helped": True,
            }
        }
        self.entity_positions = {
            "char-1": {"x": 0, "y": 0},
            "goblin-1": {"x": 1, "y": 0},
        }
        self.grid_data = {}


class FakePlayer:
    id = "char-1"
    name = "战士"
    char_class = "Fighter"
    level = 1
    conditions = []
    class_resources = {}
    equipment = {}
    derived = {
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }


def save_turn_state(combat, entity_id, turn_state):
    combat.turn_states[str(entity_id)] = turn_state


def fixed_roll_attack(**_kwargs):
    return {
        "d20": 12,
        "attack_bonus": 5,
        "attack_total": 17,
        "target_ac": 12,
        "hit": True,
        "is_crit": False,
        "is_fumble": False,
    }


@pytest.mark.asyncio
async def test_prepare_attack_roll_consumes_help_advantage_and_stores_pending_attack():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()

    prepared = await prepare_attack_roll(
        FakeDb(),
        combat=combat,
        player=FakePlayer(),
        player_id="char-1",
        target_id="goblin-1",
        action_type="melee",
        is_offhand=False,
        d20_value=None,
        enemies=[{
            "id": "goblin-1",
            "name": "哥布林",
            "hp_current": 7,
            "derived": {"ac": 12},
            "conditions": [],
        }],
        roll_attack_func=fixed_roll_attack,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.attacker_name == "战士"
    assert prepared.target_name == "哥布林"
    assert prepared.advantage is True
    assert prepared.disadvantage is False
    assert prepared.damage_dice == "1d8+3"
    assert prepared.attack_roll_result["hit"] is True
    assert prepared.turn_state["being_helped"] is False
    assert prepared.turn_state["attacks_made"] == 1
    assert prepared.turn_state["action_used"] is True
    assert prepared.pending_attack["pending_attack_id"] == prepared.pending_attack_id
    assert combat.turn_states["char-1"]["pending_attack"]["advantage"] is True


@pytest.mark.asyncio
async def test_prepare_attack_roll_rejects_melee_target_out_of_range():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.entity_positions["goblin-1"] = {"x": 4, "y": 0}

    with pytest.raises(CombatAttackRollError) as exc:
        await prepare_attack_roll(
            FakeDb(),
            combat=combat,
            player=FakePlayer(),
            player_id="char-1",
            target_id="goblin-1",
            action_type="melee",
            is_offhand=False,
            d20_value=None,
            enemies=[{
                "id": "goblin-1",
                "name": "哥布林",
                "hp_current": 7,
                "derived": {"ac": 12},
                "conditions": [],
            }],
            roll_attack_func=fixed_roll_attack,
            save_turn_state_func=save_turn_state,
        )

    assert exc.value.status_code == 400
    assert "目标不在近战范围内" in exc.value.detail
