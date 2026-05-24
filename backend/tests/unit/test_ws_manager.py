import pytest

from services.ws_manager import WSManager


def test_ws_manager_stats_counts_rooms_and_connections():
    manager = WSManager()
    ws1 = object()
    ws2 = object()
    ws3 = object()
    manager.rooms = {
        "s1": {ws1, ws2},
        "s2": {ws3},
    }
    manager.user_ws = {
        ("s1", "u1"): ws1,
        ("s1", "u2"): ws2,
        ("s2", "u3"): ws3,
    }
    manager.ws_meta = {
        ws1: ("s1", "u1"),
        ws2: ("s1", "u2"),
        ws3: ("s2", "u3"),
    }

    assert manager.stats() == {
        "rooms": 2,
        "connections": 3,
        "users": 3,
        "room_connections": {
            "s1": 2,
            "s2": 1,
        },
    }


@pytest.mark.asyncio
async def test_same_user_can_stay_connected_to_independent_rooms():
    manager = WSManager()

    class FakeWS:
        def __init__(self):
            self.sent = []
            self.closed = None

        async def send_json(self, payload):
            self.sent.append(payload)

        async def close(self, code=None, reason=None):
            self.closed = {"code": code, "reason": reason}

    room_a = FakeWS()
    room_b = FakeWS()

    await manager.connect("session-a", "same-user", room_a)
    await manager.connect("session-b", "same-user", room_b)

    assert manager.user_ws[("session-a", "same-user")] is room_a
    assert manager.user_ws[("session-b", "same-user")] is room_b
    assert room_a.closed is None
    assert room_b.closed is None

    await manager.broadcast("session-a", {"type": "only_a"})
    await manager.broadcast("session-b", {"type": "only_b"})

    assert room_a.sent == [{"type": "only_a"}]
    assert room_b.sent == [{"type": "only_b"}]

    assert await manager.disconnect(room_a) == ("session-a", "same-user")
    assert ("session-a", "same-user") not in manager.user_ws
    assert manager.user_ws[("session-b", "same-user")] is room_b
    assert "session-b" in manager.rooms
