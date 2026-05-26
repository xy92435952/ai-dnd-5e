from types import SimpleNamespace

import pytest


class FakeDb:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commits += 1


class FakeCombat:
    def __init__(self):
        self.turn_states = {
            "hero-1": {
                "action_used": False,
                "movement_used": 0,
                "movement_max": 6,
            }
        }


@pytest.mark.asyncio
async def test_dodge_action_marks_actor_as_dodging(monkeypatch):
    from api.combat.attack_actions import maybe_handle_pre_attack_action

    db = FakeDb()
    combat = FakeCombat()
    monkeypatch.setattr(
        "api.combat.attack_actions._save_ts",
        lambda combat_obj, entity_id, turn_state: combat_obj.turn_states.__setitem__(str(entity_id), turn_state),
    )

    result = await maybe_handle_pre_attack_action(
        session_id="sess-1",
        action_text="闪避",
        target_id=None,
        db=db,
        session=SimpleNamespace(),
        combat=combat,
        player=None,
        player_id="hero-1",
        player_name="英雄",
        state={},
        enemies=[],
    )

    assert result["action"] == "dodge"
    assert result["turn_state"]["action_used"] is True
    assert result["turn_state"]["dodging"] is True
    assert combat.turn_states["hero-1"]["dodging"] is True
    assert db.commits == 1
