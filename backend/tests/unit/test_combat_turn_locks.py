import pytest


def test_turn_advance_locks_are_scoped_by_session_and_released():
    from api.combat._shared import (
        _TURN_ADVANCE_LOCKS,
        _get_turn_advance_lock,
        _release_turn_advance_lock,
    )

    _TURN_ADVANCE_LOCKS.clear()

    first = _get_turn_advance_lock("session-a")
    again = _get_turn_advance_lock("session-a")
    other = _get_turn_advance_lock("session-b")

    assert first is again
    assert first is not other
    assert set(_TURN_ADVANCE_LOCKS) == {"session-a", "session-b"}

    assert _release_turn_advance_lock("session-a") is True
    assert "session-a" not in _TURN_ADVANCE_LOCKS
    assert "session-b" in _TURN_ADVANCE_LOCKS

    _TURN_ADVANCE_LOCKS.clear()


@pytest.mark.asyncio
async def test_turn_advance_lock_release_keeps_active_lock():
    from api.combat._shared import (
        _TURN_ADVANCE_LOCKS,
        _get_turn_advance_lock,
        _release_turn_advance_lock,
    )

    _TURN_ADVANCE_LOCKS.clear()
    lock = _get_turn_advance_lock("session-a")

    async with lock:
        assert _release_turn_advance_lock("session-a") is False
        assert _TURN_ADVANCE_LOCKS["session-a"] is lock

    assert _release_turn_advance_lock("session-a") is True
    assert "session-a" not in _TURN_ADVANCE_LOCKS

    _TURN_ADVANCE_LOCKS.clear()
