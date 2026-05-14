from types import SimpleNamespace

import pytest

from services.combat_item_service import (
    CombatItemAction,
    CombatItemActionError,
    consume_combat_item_action,
    validate_combat_item_action,
)


def make_session(**overrides):
    data = {"combat_active": True}
    data.update(overrides)
    return SimpleNamespace(**data)


def make_combat(**overrides):
    data = {
        "turn_order": [{"character_id": "char-1"}],
        "current_turn_index": 0,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_validate_combat_item_action_rejects_non_current_turn():
    combat = make_combat(turn_order=[{"character_id": "other-char"}])

    with pytest.raises(CombatItemActionError) as exc:
        validate_combat_item_action(
            session=make_session(),
            combat=combat,
            character_id="char-1",
            get_turn_state=lambda *_: {"action_used": False},
        )

    assert exc.value.status_code == 400
    assert "不是该角色的回合" in exc.value.detail


def test_validate_combat_item_action_rejects_spent_action():
    with pytest.raises(CombatItemActionError) as exc:
        validate_combat_item_action(
            session=make_session(),
            combat=make_combat(),
            character_id="char-1",
            get_turn_state=lambda *_: {"action_used": True},
        )

    assert exc.value.status_code == 400
    assert "行动已用尽" in exc.value.detail


def test_consume_combat_item_action_marks_action_used_and_saves():
    combat = make_combat()
    turn_state = {"action_used": False, "bonus_action_used": False}
    saved = {}

    result = consume_combat_item_action(
        CombatItemAction(combat=combat, turn_state=turn_state),
        character_id="char-1",
        save_turn_state=lambda c, cid, ts: saved.update({"combat": c, "character_id": cid, "turn_state": ts}),
    )

    assert result["action_used"] is True
    assert saved == {
        "combat": combat,
        "character_id": "char-1",
        "turn_state": turn_state,
    }
