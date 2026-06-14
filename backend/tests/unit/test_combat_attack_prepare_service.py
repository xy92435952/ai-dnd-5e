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
    hp_current = 20
    conditions = []
    death_saves = {}
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


def fixed_miss_attack(**_kwargs):
    return {
        "d20": 4,
        "attack_bonus": 5,
        "attack_total": 9,
        "target_ac": 12,
        "hit": False,
        "is_crit": False,
        "is_fumble": False,
    }


def mobile_player():
    player = FakePlayer()
    player.derived = {
        **FakePlayer.derived,
        "feat_effects": {"Mobile": {"mobile": True}},
    }
    return player


def ranged_player(*, ammo=5):
    player = FakePlayer()
    player.derived = {
        **FakePlayer.derived,
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


def thrown_player():
    player = FakePlayer()
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


def two_weapon_player():
    player = FakePlayer()
    player.equipment = {
        "weapons": [
            {
                "name": "Shortsword",
                "damage": "1d6",
                "type": "martial_melee",
                "properties": ["finesse", "light"],
                "equipped": True,
            },
            {
                "name": "Dagger",
                "damage": "1d4",
                "type": "simple_melee",
                "properties": ["finesse", "light", "thrown(20/60)"],
                "equipped": True,
            },
        ],
        "shield": {"name": "Shield", "equipped": False},
    }
    return player


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
async def test_prepare_attack_roll_records_mobile_melee_target_even_on_miss():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False

    prepared = await prepare_attack_roll(
        FakeDb(),
        combat=combat,
        session=None,
        player=mobile_player(),
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
        roll_attack_func=fixed_miss_attack,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.attack_roll_result["hit"] is False
    assert combat.turn_states["char-1"]["mobile_opportunity_safe_targets"] == ["goblin-1"]


@pytest.mark.asyncio
async def test_prepare_ranged_attack_roll_consumes_ammunition_and_stores_resource():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    combat.entity_positions["goblin-1"] = {"x": 4, "y": 0}
    player = ranged_player(ammo=2)

    prepared = await prepare_attack_roll(
        FakeDb(),
        combat=combat,
        session=None,
        player=player,
        player_id="char-1",
        target_id="goblin-1",
        action_type="ranged",
        is_offhand=False,
        d20_value=None,
        enemies=[{
            "id": "goblin-1",
            "name": "Goblin",
            "hp_current": 7,
            "derived": {"ac": 12},
            "conditions": [],
        }],
        roll_attack_func=fixed_roll_attack,
        save_turn_state_func=save_turn_state,
    )

    assert player.equipment["weapons"][0]["ammo"] == 1
    assert prepared.weapon_resource == {
        "weapon": "Longbow",
        "resource_type": "ammunition",
        "consumed": True,
        "ammo_remaining": 1,
    }
    assert prepared.pending_attack["weapon_resource"] == prepared.weapon_resource


@pytest.mark.asyncio
async def test_prepare_ranged_attack_roll_rejects_empty_ammunition():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    combat.entity_positions["goblin-1"] = {"x": 4, "y": 0}
    player = ranged_player(ammo=0)

    with pytest.raises(CombatAttackRollError) as exc:
        await prepare_attack_roll(
            FakeDb(),
            combat=combat,
            session=None,
            player=player,
            player_id="char-1",
            target_id="goblin-1",
            action_type="ranged",
            is_offhand=False,
            d20_value=None,
            enemies=[{
                "id": "goblin-1",
                "name": "Goblin",
                "hp_current": 7,
                "derived": {"ac": 12},
                "conditions": [],
            }],
            roll_attack_func=fixed_roll_attack,
            save_turn_state_func=save_turn_state,
        )

    assert exc.value.status_code == 400
    assert "No ammunition remaining for Longbow" in exc.value.detail
    assert player.equipment["weapons"][0]["ammo"] == 0
    assert combat.turn_states["char-1"]["attacks_made"] == 0


@pytest.mark.asyncio
async def test_prepare_ranged_attack_roll_consumes_thrown_weapon_copy():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    combat.entity_positions["goblin-1"] = {"x": 4, "y": 0}
    player = thrown_player()

    prepared = await prepare_attack_roll(
        FakeDb(),
        combat=combat,
        session=None,
        player=player,
        player_id="char-1",
        target_id="goblin-1",
        action_type="ranged",
        is_offhand=False,
        d20_value=None,
        enemies=[{
            "id": "goblin-1",
            "name": "Goblin",
            "hp_current": 7,
            "derived": {"ac": 12},
            "conditions": [],
        }],
        roll_attack_func=fixed_roll_attack,
        save_turn_state_func=save_turn_state,
    )

    assert [weapon["name"] for weapon in player.equipment["weapons"]] == ["Javelin"]
    assert player.equipment["weapons"][0]["equipped"] is True
    assert prepared.damage_dice == "1d6+1"
    assert prepared.weapon_resource == {
        "weapon": "Javelin",
        "resource_type": "thrown_weapon",
        "consumed": True,
        "weapon_removed": True,
    }
    assert prepared.pending_attack["weapon_resource"] == prepared.weapon_resource


@pytest.mark.asyncio
async def test_prepare_offhand_attack_roll_consumes_bonus_action_not_attack_count():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.turn_states["char-1"] = {
        "attacks_made": 1,
        "attacks_max": 1,
        "action_used": True,
        "bonus_action_used": False,
        "being_helped": False,
    }

    prepared = await prepare_attack_roll(
        FakeDb(),
        combat=combat,
        session=None,
        player=two_weapon_player(),
        player_id="char-1",
        target_id="goblin-1",
        action_type="melee",
        is_offhand=True,
        d20_value=None,
        enemies=[{
            "id": "goblin-1",
            "name": "Goblin",
            "hp_current": 7,
            "derived": {"ac": 12},
            "conditions": [],
        }],
        roll_attack_func=fixed_roll_attack,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.pending_attack["is_offhand"] is True
    assert prepared.damage_dice == "1d6+0"
    assert prepared.turn_state["attacks_made"] == 1
    assert prepared.turn_state["action_used"] is True
    assert prepared.turn_state["bonus_action_used"] is True


@pytest.mark.asyncio
async def test_prepare_offhand_attack_roll_rejects_non_light_weapon_pair():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.turn_states["char-1"] = {
        "attacks_made": 1,
        "attacks_max": 1,
        "action_used": True,
        "bonus_action_used": False,
        "being_helped": False,
    }
    player = two_weapon_player()
    player.equipment["weapons"][0] = {"name": "Longsword", "equipped": True}

    with pytest.raises(CombatAttackRollError) as exc:
        await prepare_attack_roll(
            FakeDb(),
            combat=combat,
            session=None,
            player=player,
            player_id="char-1",
            target_id="goblin-1",
            action_type="melee",
            is_offhand=True,
            d20_value=None,
            enemies=[{
                "id": "goblin-1",
                "name": "Goblin",
                "hp_current": 7,
                "derived": {"ac": 12},
                "conditions": [],
            }],
            roll_attack_func=fixed_roll_attack,
            save_turn_state_func=save_turn_state,
        )

    assert exc.value.status_code == 400
    assert "two equipped light melee weapons" in exc.value.detail


@pytest.mark.asyncio
async def test_prepare_attack_roll_rejects_incapacitated_attacker():
    from services.combat_attack_prepare_service import prepare_attack_roll

    player = FakePlayer()
    player.conditions = ["stunned"]

    with pytest.raises(CombatAttackRollError) as exc:
        await prepare_attack_roll(
            FakeDb(),
            combat=FakeCombat(),
            session=None,
            player=player,
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
            roll_attack_func=fixed_roll_attack,
            save_turn_state_func=save_turn_state,
        )

    assert exc.value.status_code == 400
    assert "stunned" in exc.value.detail


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
        player=ranged_player(),
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
async def test_prepare_attack_roll_uses_enemy_defender_interception():
    from services.combat_attack_prepare_service import prepare_attack_roll

    combat = FakeCombat()
    combat.turn_states["char-1"]["being_helped"] = False
    combat.entity_positions["guard-1"] = {"x": 1, "y": 1}
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
        enemies=[
            {
                "id": "goblin-1",
                "name": "哥布林",
                "hp_current": 7,
                "derived": {"ac": 12},
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
        roll_attack_func=capture_roll_attack,
        save_turn_state_func=save_turn_state,
    )

    assert prepared.disadvantage is True
    assert captured["disadvantage"] is True
    assert prepared.defender_interception["defender_id"] == "guard-1"
    assert prepared.attack_roll_result["defender_interception"]["defender_name"] == "盾卫"
    assert prepared.pending_attack["defender_interception"]["effect"] == "disadvantage"
    assert combat.turn_states["guard-1"]["reaction_used"] is True


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
        player=ranged_player(),
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
        player=ranged_player(),
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
