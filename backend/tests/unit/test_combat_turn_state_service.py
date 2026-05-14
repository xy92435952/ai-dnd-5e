from types import SimpleNamespace

from services.combat_turn_state_service import (
    DEFAULT_TURN_STATE,
    get_turn_state,
    reset_turn_state,
    save_turn_state,
)


def test_get_turn_state_returns_default_copy():
    combat = SimpleNamespace(turn_states=None)

    state = get_turn_state(combat, "hero")
    state["action_used"] = True

    assert DEFAULT_TURN_STATE["action_used"] is False


def test_save_and_reset_turn_state_updates_combat_state(monkeypatch):
    monkeypatch.setattr(
        "services.combat_turn_state_service.flag_modified",
        lambda *_args: None,
    )
    combat = SimpleNamespace(turn_states={})

    save_turn_state(combat, "hero", {"action_used": True})
    assert combat.turn_states["hero"] == {"action_used": True}

    reset_turn_state(combat, "hero", attacks_max=2, movement_max=8)
    assert combat.turn_states["hero"]["action_used"] is False
    assert combat.turn_states["hero"]["attacks_max"] == 2
    assert combat.turn_states["hero"]["movement_max"] == 8
