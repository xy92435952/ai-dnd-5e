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
async def test_fifty_online_websockets_stay_partitioned_across_rooms():
    manager = WSManager()
    sockets = []
    room_sizes = [4] * 12 + [2]

    user_index = 0
    for room_index, room_size in enumerate(room_sizes):
        session_id = f"room-{room_index:02d}"
        for seat_index in range(room_size):
            user_id = f"user-{user_index:02d}"
            ws = FakeWebSocket(f"{session_id}-{user_id}")
            sockets.append({
                "session_id": session_id,
                "seat_index": seat_index,
                "user_id": user_id,
                "ws": ws,
            })
            await manager.connect(session_id, user_id, ws)
            user_index += 1

    assert user_index == 50
    assert len(manager.rooms) == 13
    assert sum(len(room) for room in manager.rooms.values()) == 50

    for room_index, room_size in enumerate(room_sizes):
        session_id = f"room-{room_index:02d}"
        assert len(await manager.online_users(session_id)) == room_size
        assert len(manager.rooms[session_id]) <= 4

    sent = await manager.broadcast(
        "room-03",
        {"type": "combat_update", "session_id": "room-03"},
        exclude_user_id="user-12",
    )
    assert sent == 3

    for item in sockets:
        should_receive = item["session_id"] == "room-03" and item["user_id"] != "user-12"
        assert item["ws"].sent == (
            [{"type": "combat_update", "session_id": "room-03"}]
            if should_receive else []
        )

    whispered = await manager.send_to_user(
        "room-07",
        "user-29",
        {"type": "private_notice", "session_id": "room-07"},
    )
    assert whispered is True
    assert [
        item["ws"].sent[-1]
        for item in sockets
        if item["user_id"] == "user-29"
    ] == [{"type": "private_notice", "session_id": "room-07"}]
    assert all(
        all(event.get("session_id") == item["session_id"] for event in item["ws"].sent)
        for item in sockets
    )


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


@pytest.mark.asyncio
async def test_disconnect_user_closes_only_target_user_in_target_room():
    manager = WSManager()
    target_ws = FakeWebSocket("target")
    roommate_ws = FakeWebSocket("roommate")
    same_user_other_room_ws = FakeWebSocket("same-user-other-room")

    await manager.connect("room-a", "u1", target_ws)
    await manager.connect("room-a", "u2", roommate_ws)
    await manager.connect("room-b", "u1", same_user_other_room_ws)

    removed = await manager.disconnect_user(
        "room-a",
        "u1",
        code=4101,
        reason="Left target room",
    )

    assert removed is True
    assert target_ws.closed == [{"code": 4101, "reason": "Left target room"}]
    assert roommate_ws.closed == []
    assert same_user_other_room_ws.closed == []
    assert await manager.online_users("room-a") == ["u2"]
    assert await manager.online_users("room-b") == ["u1"]
    assert ("room-a", "u1") not in manager.user_ws
    assert manager.user_ws[("room-a", "u2")] is roommate_ws
    assert manager.user_ws[("room-b", "u1")] is same_user_other_room_ws

    assert await manager.disconnect_user("room-a", "missing") is False


@pytest.mark.asyncio
async def test_disconnect_room_closes_only_target_room_sockets():
    manager = WSManager()
    room_a_user_1 = FakeWebSocket("room-a-user-1")
    room_a_user_2 = FakeWebSocket("room-a-user-2")
    room_b_user_1 = FakeWebSocket("room-b-user-1")

    await manager.connect("room-a", "u1", room_a_user_1)
    await manager.connect("room-a", "u2", room_a_user_2)
    await manager.connect("room-b", "u1", room_b_user_1)

    removed = await manager.disconnect_room(
        "room-a",
        code=4102,
        reason="Room dissolved",
    )

    assert removed == 2
    assert room_a_user_1.closed == [{"code": 4102, "reason": "Room dissolved"}]
    assert room_a_user_2.closed == [{"code": 4102, "reason": "Room dissolved"}]
    assert room_b_user_1.closed == []
    assert "room-a" not in manager.rooms
    assert await manager.online_users("room-a") == []
    assert await manager.online_users("room-b") == ["u1"]
    assert manager.user_ws == {("room-b", "u1"): room_b_user_1}
    assert manager.ws_meta == {room_b_user_1: ("room-b", "u1")}
