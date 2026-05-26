import asyncio

import pytest

from services.ws_manager import WSManager


class FakeWebSocket:
    def __init__(self, name, *, fail_send=False, close_delay=0):
        self.name = name
        self.fail_send = fail_send
        self.close_delay = close_delay
        self.sent = []
        self.closed = []

    async def send_json(self, event):
        if self.fail_send:
            raise RuntimeError(f"{self.name} send failed")
        self.sent.append(event)

    async def close(self, code=1000, reason=None):
        if self.close_delay:
            await asyncio.sleep(self.close_delay)
        self.closed.append({"code": code, "reason": reason})


@pytest.mark.asyncio
async def test_broadcast_isolated_to_target_room_and_can_exclude_sender():
    manager = WSManager()
    room_a_user_1 = FakeWebSocket("room-a-user-1")
    room_a_user_2 = FakeWebSocket("room-a-user-2")
    room_b_user_1 = FakeWebSocket("room-b-user-1")

    await manager.connect("room-a", "u1", room_a_user_1)
    await manager.connect("room-a", "u2", room_a_user_2)
    await manager.connect("room-b", "u3", room_b_user_1)

    sent = await manager.broadcast(
        "room-a",
        {"type": "typing", "user_id": "u1"},
        exclude_user_id="u1",
    )

    assert sent == 1
    assert room_a_user_1.sent == []
    assert room_a_user_2.sent == [{"type": "typing", "user_id": "u1"}]
    assert room_b_user_1.sent == []
    assert await manager.online_users("room-a") == ["u1", "u2"]
    assert await manager.online_users("room-b") == ["u3"]


@pytest.mark.asyncio
async def test_reconnect_replaces_only_the_same_user_in_the_same_room():
    manager = WSManager()
    old_ws = FakeWebSocket("old")
    replacement_ws = FakeWebSocket("replacement")
    other_user_ws = FakeWebSocket("other-user")
    same_user_other_room_ws = FakeWebSocket("same-user-other-room")

    await manager.connect("room-a", "u1", old_ws)
    await manager.connect("room-a", "u2", other_user_ws)
    await manager.connect("room-b", "u1", same_user_other_room_ws)
    await manager.connect("room-a", "u1", replacement_ws)

    assert old_ws.closed == [{"code": 4000, "reason": "Replaced by new connection"}]
    assert manager.user_ws[("room-a", "u1")] is replacement_ws
    assert manager.user_ws[("room-a", "u2")] is other_user_ws
    assert manager.user_ws[("room-b", "u1")] is same_user_other_room_ws
    assert old_ws not in manager.rooms["room-a"]
    assert replacement_ws in manager.rooms["room-a"]
    assert same_user_other_room_ws in manager.rooms["room-b"]


@pytest.mark.asyncio
async def test_connect_does_not_hold_manager_lock_while_closing_replaced_socket():
    manager = WSManager()
    old_ws = FakeWebSocket("old", close_delay=0.05)
    replacement_ws = FakeWebSocket("replacement")
    other_ws = FakeWebSocket("other")

    await manager.connect("room-a", "u1", old_ws)

    replace_task = asyncio.create_task(manager.connect("room-a", "u1", replacement_ws))
    await asyncio.sleep(0.005)
    await asyncio.wait_for(manager.connect("room-a", "u2", other_ws), timeout=0.02)
    await replace_task

    assert old_ws.closed == [{"code": 4000, "reason": "Replaced by new connection"}]
    assert set(await manager.online_users("room-a")) == {"u1", "u2"}


@pytest.mark.asyncio
async def test_failed_broadcast_connection_is_removed_without_affecting_roommates():
    manager = WSManager()
    bad_ws = FakeWebSocket("bad", fail_send=True)
    good_ws = FakeWebSocket("good")

    await manager.connect("room-a", "bad-user", bad_ws)
    await manager.connect("room-a", "good-user", good_ws)

    sent = await manager.broadcast("room-a", {"type": "combat_update"})
    await asyncio.sleep(0.02)

    assert sent == 1
    assert good_ws.sent == [{"type": "combat_update"}]
    assert bad_ws.closed == [{"code": 1000, "reason": None}]
    assert await manager.online_users("room-a") == ["good-user"]
    assert manager.ws_meta == {good_ws: ("room-a", "good-user")}


@pytest.mark.asyncio
async def test_disconnect_cleans_empty_room_and_preserves_newer_reconnect():
    manager = WSManager()
    old_ws = FakeWebSocket("old")
    new_ws = FakeWebSocket("new")

    await manager.connect("room-a", "u1", old_ws)
    await manager.connect("room-a", "u1", new_ws)

    assert await manager.disconnect(old_ws) is None
    assert await manager.online_users("room-a") == ["u1"]
    assert manager.user_ws[("room-a", "u1")] is new_ws

    assert await manager.disconnect(new_ws) == ("room-a", "u1")
    assert "room-a" not in manager.rooms
    assert manager.user_ws == {}
    assert manager.ws_meta == {}
