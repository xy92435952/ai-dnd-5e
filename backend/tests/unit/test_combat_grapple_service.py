import pytest


class FakePlayer:
    id = "player-1"
    name = "战士"
    char_class = "Fighter"
    level = 5
    hp_current = 42
    conditions = []
    death_saves = {}
    derived = {"ability_modifiers": {"str": 4}, "proficiency_bonus": 3}
    proficient_skills = ["运动"]


class FakeDb:
    async def get(self, _model, entity_id):
        if entity_id == "player-1":
            return FakePlayer()
        return None


class FakeSession:
    combat_active = True
    player_character_id = "player-1"

    def __init__(self):
        self.game_state = {
            "enemies": [{
                "id": "goblin-1",
                "name": "哥布林",
                "conditions": [],
                "derived": {"ability_modifiers": {"str": 0, "dex": 2}, "proficiency_bonus": 2},
            }]
        }


class FakeCombat:
    def __init__(self):
        self.turn_states = {"player-1": {"action_used": False, "attacks_made": 0}}
        self.entity_positions = {
            "player-1": {"x": 5, "y": 5},
            "goblin-1": {"x": 6, "y": 5},
        }


class FakeCombatService:
    def get_attack_count(self, *_args):
        return 2

    def resolve_grapple(self, *_args):
        return {
            "success": True,
            "attacker_roll": {"total": 18},
            "target_roll": {"total": 10},
        }

    def resolve_shove(self, *_args):
        return {
            "success": True,
            "attacker_roll": {"total": 18},
            "target_roll": {"total": 10},
        }


def save_turn_state(combat, entity_id, turn_state):
    combat.turn_states[str(entity_id)] = turn_state


@pytest.mark.asyncio
async def test_resolve_grapple_adds_condition_and_consumes_one_attack():
    from services.combat_grapple_service import resolve_grapple_shove

    session = FakeSession()
    combat = FakeCombat()

    result = await resolve_grapple_shove(
        FakeDb(),
        session=session,
        combat=combat,
        action_type="grapple",
        target_id="goblin-1",
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
        narrate_action_func=lambda **_kwargs: None,
    )

    assert session.game_state["enemies"][0]["conditions"] == ["grappled"]
    assert result.payload["success"] is True
    assert result.payload["turn_state"]["attacks_made"] == 1
    assert result.payload["turn_state"]["attacks_max"] == 2
    assert result.payload["turn_state"]["action_used"] is False
    assert "成功擒抱" in result.narration


@pytest.mark.asyncio
async def test_resolve_shove_push_moves_enemy_away_and_marks_action_when_last_attack():
    from services.combat_grapple_service import resolve_grapple_shove

    session = FakeSession()
    combat = FakeCombat()
    combat.turn_states["player-1"]["attacks_made"] = 1

    result = await resolve_grapple_shove(
        FakeDb(),
        session=session,
        combat=combat,
        action_type="shove",
        shove_type="push",
        target_id="goblin-1",
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
        narrate_action_func=lambda **_kwargs: None,
    )

    assert combat.entity_positions["goblin-1"] == {"x": 7, "y": 5}
    assert result.payload["turn_state"]["attacks_made"] == 2
    assert result.payload["turn_state"]["action_used"] is True


@pytest.mark.asyncio
async def test_resolve_grapple_shove_rejects_unknown_action():
    from services.combat_grapple_service import CombatGrappleError, resolve_grapple_shove

    with pytest.raises(CombatGrappleError) as exc:
        await resolve_grapple_shove(
            FakeDb(),
            session=FakeSession(),
            combat=FakeCombat(),
            action_type="throw",
            target_id="goblin-1",
            combat_service=FakeCombatService(),
            narrate_action_func=lambda **_kwargs: None,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "未知动作类型：throw"
