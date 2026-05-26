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
        session=None,
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
            session=None,
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


@pytest.mark.asyncio
async def test_prepare_ranged_attack_against_distant_prone_target_has_disadvantage():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    combat.entity_positions["goblin-1"] = {"x": 4, "y": 0}
    captured = {}

    def capture_roll_attack(**kwargs):
        captured.update(kwargs)
        return fixed_roll_attack(**kwargs)

    prepared = await prepare_attack_roll(
        FakeDb(),
        combat=combat,
        session=None,
        player=FakePlayer(),
        player_id="char-1",
        target_id="goblin-1",
        action_type="ranged",
        is_offhand=False,
        d20_value=None,
        enemies=[{
            "id": "goblin-1",
            "name": "哥布林",
            "hp_current": 7,
            "derived": {"ac": 12},
            "conditions": ["prone"],
        }],
        roll_attack_func=capture_roll_attack,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.advantage is False
    assert prepared.disadvantage is True
    assert prepared.pending_attack["advantage"] is False
    assert prepared.pending_attack["disadvantage"] is True
    assert captured["advantage"] is False
    assert captured["disadvantage"] is True


@pytest.mark.asyncio
async def test_prepare_attack_roll_applies_disadvantage_against_dodging_target():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    combat.turn_states["goblin-1"] = {"dodging": True}
    captured = {}

    def capture_roll_attack(**kwargs):
        captured.update(kwargs)
        return fixed_roll_attack(**kwargs)

    prepared = await prepare_attack_roll(
        FakeDb(),
        combat=combat,
        session=None,
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
        roll_attack_func=capture_roll_attack,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.advantage is False
    assert prepared.disadvantage is True
    assert prepared.pending_attack["disadvantage"] is True
    assert captured["disadvantage"] is True


@pytest.mark.asyncio
async def test_prepare_attack_roll_passes_attacker_conditions_to_roll_attack():
    from services.combat_attack_prepare_service import prepare_attack_roll

    class BlessedPlayer(FakePlayer):
        conditions = ["blessed"]

    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    captured = {}

    def capture_roll_attack(**kwargs):
        captured.update(kwargs)
        return fixed_roll_attack(**kwargs)

    await prepare_attack_roll(
        FakeDb(),
        combat=combat,
        session=None,
        player=BlessedPlayer(),
        player_id="char-1",
        target_id="goblin-1",
        action_type="melee",
        is_offhand=False,
        d20_value=None,
        enemies=[{
            "id": "goblin-1",
            "name": "Goblin",
            "hp_current": 7,
            "derived": {"ac": 12},
            "conditions": [],
        }],
        roll_attack_func=capture_roll_attack,
        save_turn_state_func=save_turn_state,
    )

    assert captured["attacker"]["conditions"] == ["blessed"]


@pytest.mark.asyncio
async def test_prepare_attack_roll_consumes_guiding_bolt_advantage():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    captured = {}
    state = {
        "enemies": [{
            "id": "goblin-1",
            "name": "Goblin",
            "hp_current": 7,
            "derived": {"ac": 12},
            "conditions": ["guiding_bolt"],
            "condition_durations": {"guiding_bolt": 1},
        }]
    }

    class FakeSession:
        game_state = state

    def capture_roll_attack(**kwargs):
        captured.update(kwargs)
        return fixed_roll_attack(**kwargs)

    prepared = await prepare_attack_roll(
        FakeDb(),
        combat=combat,
        session=FakeSession(),
        player=FakePlayer(),
        player_id="char-1",
        target_id="goblin-1",
        action_type="melee",
        is_offhand=False,
        d20_value=None,
        enemies=state["enemies"],
        roll_attack_func=capture_roll_attack,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.advantage is True
    assert captured["advantage"] is True
    assert state["enemies"][0]["conditions"] == []
    assert state["enemies"][0]["condition_durations"] == {}
    assert prepared.pending_attack["target_conditions"] == ["guiding_bolt"]


@pytest.mark.asyncio
async def test_prepare_attack_roll_forces_close_unconscious_target_crit():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False

    prepared = await prepare_attack_roll(
        FakeDb(),
        combat=combat,
        session=None,
        player=FakePlayer(),
        player_id="char-1",
        target_id="goblin-1",
        action_type="melee",
        is_offhand=False,
        d20_value=12,
        enemies=[{
            "id": "goblin-1",
            "name": "哥布林",
            "hp_current": 7,
            "derived": {"ac": 12},
            "conditions": ["unconscious"],
        }],
        roll_attack_func=fixed_roll_attack,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.attack_roll_result["hit"] is True
    assert prepared.attack_roll_result["is_crit"] is True
    assert prepared.attack_roll_result["forced_crit"] == "incapacitated_target"
    assert prepared.pending_attack["is_crit"] is True


@pytest.mark.asyncio
async def test_prepare_attack_roll_does_not_force_ranged_unconscious_target_crit():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False

    prepared = await prepare_attack_roll(
        FakeDb(),
        combat=combat,
        session=None,
        player=FakePlayer(),
        player_id="char-1",
        target_id="goblin-1",
        action_type="ranged",
        is_offhand=False,
        d20_value=12,
        enemies=[{
            "id": "goblin-1",
            "name": "哥布林",
            "hp_current": 7,
            "derived": {"ac": 12},
            "conditions": ["unconscious"],
        }],
        roll_attack_func=fixed_roll_attack,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.attack_roll_result["hit"] is True
    assert prepared.attack_roll_result["is_crit"] is False
