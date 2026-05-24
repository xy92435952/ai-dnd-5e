"""多人 WebSocket 实时链路模拟。"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy.ext.asyncio import async_sessionmaker

pytestmark = pytest.mark.integration


async def _register(client, username, password="password", display_name=None):
    r = await client.post("/auth/register", json={
        "username": username,
        "password": password,
        "display_name": display_name or username,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


class QueueWebSocket:
    def __init__(self):
        self.incoming = asyncio.Queue()
        self.sent = []
        self.accepted = asyncio.Event()
        self.closed = None

    async def accept(self):
        self.accepted.set()

    async def receive_json(self):
        item = await self.incoming.get()
        if isinstance(item, BaseException):
            raise item
        return item

    async def send_json(self, payload):
        self.sent.append(payload)

    async def close(self, code=1000, reason=None):
        self.closed = {"code": code, "reason": reason}

    async def push(self, payload):
        await self.incoming.put(payload)

    async def disconnect(self):
        await self.incoming.put(WebSocketDisconnect())


async def _wait_for_event(ws: QueueWebSocket, event_type: str, timeout: float = 1.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        for event in ws.sent:
            if event.get("type") == event_type:
                return event
        await asyncio.sleep(0.01)
    raise AssertionError(f"did not receive {event_type}; sent={ws.sent!r}")


async def test_ws_disconnect_marks_member_offline_in_realtime_snapshot(
    client,
    engine,
    sample_module,
    monkeypatch,
):
    """断开 WebSocket 后，member_offline 事件里的成员快照也应立即显示离线。"""
    import api.ws as ws_api
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    host = await _register(client, "ws_host", display_name="房主玩家")
    guest = await _register(client, "ws_guest", display_name="队友玩家")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS 模拟房",
        "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": created["room_code"],
    })

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, created["session_id"], token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, created["session_id"], token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        await guest_ws.disconnect()
        offline = await _wait_for_event(host_ws, "member_offline")

        guest_member = next(item for item in offline["members"] if item["user_id"] == guest["user_id"])
        assert guest_member["is_online"] is False
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_ws_typing_and_speak_done_drive_table_realtime_events(
    client,
    engine,
    sample_module,
    monkeypatch,
):
    """typing 只给其他玩家；speak_done 推进发言权并同步给房间。"""
    import api.ws as ws_api
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    host = await _register(client, "ws_speak_host", display_name="房主玩家")
    guest = await _register(client, "ws_speak_guest", display_name="队友玩家")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS 发言房",
        "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": created["room_code"],
    })

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, created["session_id"], token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, created["session_id"], token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        await host_ws.push({"type": "typing", "is_typing": True})
        typing = await _wait_for_event(guest_ws, "typing")
        assert typing["user_id"] == host["user_id"]
        assert typing["is_typing"] is True
        assert not any(event.get("type") == "typing" for event in host_ws.sent)

        await host_ws.push({"type": "speak_done"})
        host_turn = await _wait_for_event(host_ws, "dm_speak_turn")
        guest_turn = await _wait_for_event(guest_ws, "dm_speak_turn")
        assert host_turn == guest_turn
        assert host_turn["user_id"] == guest["user_id"]
        assert host_turn["auto"] is False

        room = await client.get(
            f"/game/rooms/{created['session_id']}",
            headers=_h(host["token"]),
        )
        assert room.status_code == 200, room.text
        assert room.json()["current_speaker_user_id"] == guest["user_id"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_ws_rejects_non_member_before_accepting(
    client,
    engine,
    sample_module,
    monkeypatch,
):
    import api.ws as ws_api
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    host = await _register(client, "ws_auth_host")
    outsider = await _register(client, "ws_auth_outsider")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "ws auth room",
        "max_players": 4,
    })).json()

    outsider_ws = QueueWebSocket()
    await ws_api.ws_endpoint(
        outsider_ws,
        created["session_id"],
        token=outsider["token"],
    )

    assert outsider_ws.accepted.is_set() is False
    assert outsider_ws.closed["code"] == 4403
    assert ws_manager.stats()["connections"] == 0


async def test_same_user_ws_disconnect_is_session_scoped(
    client,
    engine,
    sample_module,
    monkeypatch,
):
    import api.ws as ws_api
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    shared = await _register(client, "ws_multiroom_user")
    room_a = (await client.post("/game/rooms/create", headers=_h(shared["token"]), json={
        "module_id": sample_module.id,
        "save_name": "ws room a",
        "max_players": 4,
    })).json()
    room_b = (await client.post("/game/rooms/create", headers=_h(shared["token"]), json={
        "module_id": sample_module.id,
        "save_name": "ws room b",
        "max_players": 4,
    })).json()

    ws_a = QueueWebSocket()
    ws_b = QueueWebSocket()
    task_a = asyncio.create_task(ws_api.ws_endpoint(ws_a, room_a["session_id"], token=shared["token"]))
    task_b = asyncio.create_task(ws_api.ws_endpoint(ws_b, room_b["session_id"], token=shared["token"]))

    try:
        await asyncio.wait_for(ws_a.accepted.wait(), timeout=1)
        await asyncio.wait_for(ws_b.accepted.wait(), timeout=1)
        assert sorted(await ws_manager.online_users(room_a["session_id"])) == [shared["user_id"]]
        assert sorted(await ws_manager.online_users(room_b["session_id"])) == [shared["user_id"]]

        await ws_a.disconnect()
        await asyncio.wait_for(task_a, timeout=1)

        assert await ws_manager.online_users(room_a["session_id"]) == []
        assert await ws_manager.online_users(room_b["session_id"]) == [shared["user_id"]]

        room_a_state = await client.get(
            f"/game/rooms/{room_a['session_id']}",
            headers=_h(shared["token"]),
        )
        room_b_state = await client.get(
            f"/game/rooms/{room_b['session_id']}",
            headers=_h(shared["token"]),
        )
        assert room_a_state.status_code == 200, room_a_state.text
        assert room_b_state.status_code == 200, room_b_state.text
        assert room_a_state.json()["members"][0]["is_online"] is False
        assert room_b_state.json()["members"][0]["is_online"] is True
    finally:
        await ws_a.disconnect()
        await ws_b.disconnect()
        await asyncio.gather(task_a, task_b, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()
