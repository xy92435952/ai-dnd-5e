from types import SimpleNamespace

import pytest


class FakeCombat:
    def __init__(self):
        self.turn_states = {
            "ally-1": {
                "action_used": False,
                "bonus_action_used": False,
                "reaction_used": False,
                "attacks_made": 0,
                "movement_used": 0,
                "movement_max": 6,
            }
        }
        self.entity_positions = {
            "ally-1": {"x": 0, "y": 0},
            "enemy-1": {"x": 1, "y": 0},
        }
        self.grid_data = {}
        self.current_turn_index = 0
        self.round_number = 1


class FakeSession:
    id = "session-1"
    player_character_id = "player-1"
    combat_active = True

    def __init__(self, enemies):
        self.game_state = {"enemies": enemies}


class FakeDb:
    def __init__(self):
        self.added = []
        self.committed = False
        self.player = SimpleNamespace(id="player-1", hp_current=20)

    async def get(self, _model, entity_id):
        if str(entity_id) == "player-1":
            return self.player
        return None

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.committed = True


def fake_save_turn_state(combat, entity_id, turn_state):
    combat.turn_states[str(entity_id)] = turn_state


@pytest.mark.asyncio
async def test_ai_attack_action_records_action_usage(monkeypatch):
    import api.combat.ai_turn_attack as attack

    async def fake_advance_ai_turn(combat, *_args):
        combat.current_turn_index = 1

    async def fake_narrate_batch(_actions):
        return [""]

    enemy = {
        "id": "enemy-1",
        "name": "Training Dummy",
        "hp_current": 10,
        "derived": {"hp_max": 10, "ac": 10},
    }
    combat = FakeCombat()
    db = FakeDb()

    monkeypatch.setattr(attack, "advance_ai_turn", fake_advance_ai_turn)
    monkeypatch.setattr(attack, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(attack, "flag_modified", lambda *_args: None)
    monkeypatch.setattr(attack, "_save_ts", fake_save_turn_state)
    monkeypatch.setattr(
        attack.svc,
        "resolve_melee_attack",
        lambda **_kwargs: SimpleNamespace(
            attack_roll={
                "d20": 12,
                "attack_total": 17,
                "target_ac": 10,
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
            },
            damage=4,
        ),
    )
    monkeypatch.setattr(attack.svc, "_build_narration", lambda *_args: "Ally hits.")
    monkeypatch.setattr(attack.svc, "check_combat_over", lambda *_args: (False, None))

    result = await attack.handle_ai_attack_action(
        session_id="session-1",
        db=db,
        session=FakeSession([enemy]),
        combat=combat,
        turn_order=[{"character_id": "ally-1"}, {"character_id": "player-1"}],
        next_index=1,
        actor_id="ally-1",
        actor_name="Ally",
        is_enemy=False,
        e=None,
        achar=SimpleNamespace(
            id="ally-1",
            char_class="Fighter",
            level=1,
            class_resources={},
            concentration=None,
            conditions=[],
            condition_durations={},
            equipment={},
        ),
        actor_derived={"attack_bonus": 5, "damage_type": "slashing"},
        player=SimpleNamespace(id="player-1", hp_current=20),
        companions_alive=[],
        enemies=[enemy],
        enemies_alive=[enemy],
        all_characters=[{"id": "player-1", "hp_current": 20}],
        positions=dict(combat.entity_positions),
        decided_target_id="enemy-1",
        decided_reason="test attack",
        decision={"action_type": "attack"},
    )

    turn_state = combat.turn_states["ally-1"]
    assert result["actor_id"] == "ally-1"
    assert result["damage"] == 4
    assert turn_state["action_used"] is True
    assert turn_state["attacks_made"] == 1
    assert combat.current_turn_index == 1
    assert db.committed is True


@pytest.mark.asyncio
async def test_ai_unreachable_attack_ticks_actor_conditions(monkeypatch):
    import api.combat.ai_turn_attack as attack

    async def fake_advance_ai_turn(combat, *_args):
        combat.current_turn_index = 1

    async def fake_narrate_batch(_actions):
        return [""]

    enemy = {
        "id": "enemy-1",
        "name": "Far Dummy",
        "hp_current": 10,
        "derived": {"hp_max": 10, "ac": 10},
    }
    combat = FakeCombat()
    combat.entity_positions["enemy-1"] = {"x": 10, "y": 0}
    combat.turn_states["ally-1"]["movement_max"] = 0
    db = FakeDb()
    actor = SimpleNamespace(
        id="ally-1",
        char_class="Fighter",
        level=1,
        class_resources={},
        concentration=None,
        conditions=["poisoned"],
        condition_durations={"poisoned": 1},
        equipment={},
    )

    monkeypatch.setattr(attack, "advance_ai_turn", fake_advance_ai_turn)
    monkeypatch.setattr(attack, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(attack, "flag_modified", lambda *_args: None)

    result = await attack.handle_ai_attack_action(
        session_id="session-1",
        db=db,
        session=FakeSession([enemy]),
        combat=combat,
        turn_order=[{"character_id": "ally-1"}, {"character_id": "player-1"}],
        next_index=1,
        actor_id="ally-1",
        actor_name="Ally",
        is_enemy=False,
        e=None,
        achar=actor,
        actor_derived={"attack_bonus": 5, "damage_type": "slashing"},
        player=SimpleNamespace(id="player-1", hp_current=20),
        companions_alive=[],
        enemies=[enemy],
        enemies_alive=[enemy],
        all_characters=[{"id": "player-1", "hp_current": 20}],
        positions=dict(combat.entity_positions),
        decided_target_id="enemy-1",
        decided_reason="test unreachable",
        decision={"action_type": "attack"},
    )

    assert result["damage"] == 0
    assert result["attack_result"] == {}
    assert actor.conditions == []
    assert actor.condition_durations == {}
    assert any("poisoned" in log.content for log in db.added)
    assert combat.current_turn_index == 1
    assert db.committed is True
