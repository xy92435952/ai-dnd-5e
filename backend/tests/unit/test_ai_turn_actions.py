import pytest


class FakeCombat:
    def __init__(self):
        self.turn_states = {
            "enemy-1": {
                "action_used": False,
                "bonus_action_used": False,
                "reaction_used": False,
                "movement_used": 0,
                "movement_max": 6,
                "base_movement_max": 6,
            }
        }
        self.entity_positions = {
            "enemy-1": {"x": 0, "y": 0},
            "hero-1": {"x": 4, "y": 0},
        }
        self.current_turn_index = 0
        self.round_number = 1


class FakeSession:
    id = "session-1"

    def __init__(self):
        self.game_state = {"enemies": []}


class FakeDb:
    def __init__(self):
        self.committed = False
        self.added = []

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.committed = True


def fake_save_turn_state(combat, entity_id, turn_state):
    combat.turn_states[str(entity_id)] = turn_state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "flag"),
    [
        ("dodge", "dodging"),
        ("disengage", "disengaged"),
    ],
)
async def test_ai_simple_defensive_actions_consume_action(monkeypatch, action, flag):
    import api.combat.ai_turn_actions as actions

    async def fake_advance_ai_turn(combat, *_args):
        combat.current_turn_index = 1

    monkeypatch.setattr(actions, "advance_ai_turn", fake_advance_ai_turn)
    monkeypatch.setattr(actions, "_save_ts", fake_save_turn_state)

    combat = FakeCombat()
    db = FakeDb()

    result = await actions.handle_ai_simple_action(
        combat,
        FakeSession(),
        db,
        [{"character_id": "enemy-1"}, {"character_id": "hero-1"}],
        1,
        "enemy-1",
        "Goblin",
        action,
        None,
        "hold position",
        dict(combat.entity_positions),
        True,
        enemy={"id": "enemy-1", "conditions": []},
        session_id="session-1",
    )

    turn_state = combat.turn_states["enemy-1"]
    assert result["actor_id"] == "enemy-1"
    assert turn_state["action_used"] is True
    assert turn_state[flag] is True
    assert combat.current_turn_index == 1
    assert db.committed is True


@pytest.mark.asyncio
async def test_ai_dash_consumes_action_even_without_target(monkeypatch):
    import api.combat.ai_turn_actions as actions

    async def fake_advance_ai_turn(combat, *_args):
        combat.current_turn_index = 1

    monkeypatch.setattr(actions, "advance_ai_turn", fake_advance_ai_turn)
    monkeypatch.setattr(actions, "_save_ts", fake_save_turn_state)

    combat = FakeCombat()

    await actions.handle_ai_simple_action(
        combat,
        FakeSession(),
        FakeDb(),
        [{"character_id": "enemy-1"}, {"character_id": "hero-1"}],
        1,
        "enemy-1",
        "Goblin",
        "dash",
        None,
        "close distance",
        dict(combat.entity_positions),
        True,
        enemy={"id": "enemy-1", "conditions": []},
        session_id="session-1",
    )

    turn_state = combat.turn_states["enemy-1"]
    assert turn_state["action_used"] is True
    assert turn_state["movement_used"] == 0


@pytest.mark.asyncio
async def test_ai_dash_consumes_action_and_tracks_movement(monkeypatch):
    import api.combat.ai_turn_actions as actions

    async def fake_advance_ai_turn(combat, *_args):
        combat.current_turn_index = 1

    monkeypatch.setattr(actions, "advance_ai_turn", fake_advance_ai_turn)
    monkeypatch.setattr(actions, "_save_ts", fake_save_turn_state)

    combat = FakeCombat()

    result = await actions.handle_ai_simple_action(
        combat,
        FakeSession(),
        FakeDb(),
        [{"character_id": "enemy-1"}, {"character_id": "hero-1"}],
        1,
        "enemy-1",
        "Goblin",
        "dash",
        "hero-1",
        "close distance",
        dict(combat.entity_positions),
        True,
        enemy={"id": "enemy-1", "conditions": []},
        session_id="session-1",
    )

    turn_state = combat.turn_states["enemy-1"]
    assert result["actor_id"] == "enemy-1"
    assert turn_state["action_used"] is True
    assert turn_state["movement_used"] > 0
    assert combat.entity_positions["enemy-1"] != {"x": 0, "y": 0}
