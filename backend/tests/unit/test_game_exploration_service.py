import pytest
from types import SimpleNamespace

from models.session import Session
from services.game_exploration_service import (
    _broadcast_exploration_result,
    _send_exploration_reaction_prompt,
)


class FakeWsManager:
    def __init__(self):
        self.sent = []

    async def send_to_user(self, session_id, user_id, event):
        self.sent.append((session_id, user_id, event))
        return True


@pytest.mark.asyncio
async def test_send_exploration_reaction_prompt_targets_reactor_user(monkeypatch):
    import services.ws_manager as ws_manager_module

    fake_ws = FakeWsManager()
    monkeypatch.setattr(ws_manager_module, "ws_manager", fake_ws)
    session = Session(id="session-1", module_id="module-1", is_multiplayer=True)
    prompt = {
        "type": "feather_fall",
        "reactor_character_id": "bard-1",
        "reactor_user_id": "user-2",
        "options": [{"type": "feather_fall"}],
    }

    sent = await _send_exploration_reaction_prompt(session=session, prompt=prompt)

    assert sent is True
    assert len(fake_ws.sent) == 1
    session_id, user_id, event = fake_ws.sent[0]
    assert session_id == "session-1"
    assert user_id == "user-2"
    assert event.model_dump(mode="json") == {
        "type": "exploration_reaction_prompt",
        "prompt": prompt,
    }


@pytest.mark.asyncio
async def test_send_exploration_reaction_prompt_skips_prompt_without_reactor_user(monkeypatch):
    import services.ws_manager as ws_manager_module

    fake_ws = FakeWsManager()
    monkeypatch.setattr(ws_manager_module, "ws_manager", fake_ws)
    session = Session(id="session-1", module_id="module-1", is_multiplayer=True)

    sent = await _send_exploration_reaction_prompt(
        session=session,
        prompt={"type": "feather_fall", "reactor_character_id": "bard-1"},
    )

    assert sent is False
    assert fake_ws.sent == []


@pytest.mark.asyncio
async def test_broadcast_exploration_result_sends_private_prompt_to_reactor(monkeypatch):
    import services.game_exploration_service as exploration_module
    import services.ws_manager as ws_manager_module

    dm_events = []

    async def fake_send_dm_responded_with_visibility(**kwargs):
        dm_events.append(kwargs)

    fake_ws = FakeWsManager()
    monkeypatch.setattr(ws_manager_module, "ws_manager", fake_ws)
    monkeypatch.setattr(
        exploration_module,
        "send_dm_responded_with_visibility",
        fake_send_dm_responded_with_visibility,
    )
    session = Session(id="session-1", module_id="module-1", is_multiplayer=True)
    prompt = {
        "type": "feather_fall",
        "reactor_character_id": "bard-1",
        "reactor_user_id": "user-2",
        "options": [{"type": "feather_fall"}],
    }
    applied = SimpleNamespace(
        action_type="exploration",
        narrative="The floor gives way.",
        companion_reactions="",
        dice_display=[],
        combat_triggered=False,
        combat_ended=False,
        exploration_reaction_prompt=prompt,
    )

    await _broadcast_exploration_result(
        db=object(),
        session=session,
        actor_user_id="user-1",
        applied=applied,
        multiplayer_visibility={},
        multiplayer_table_reason="",
        multiplayer_table_decision={},
    )

    assert len(dm_events) == 1
    assert dm_events[0]["event"].model_dump(mode="json")["type"] == "dm_responded"
    assert len(fake_ws.sent) == 1
    assert fake_ws.sent[0][1] == "user-2"
    assert fake_ws.sent[0][2].model_dump(mode="json")["prompt"] == prompt
