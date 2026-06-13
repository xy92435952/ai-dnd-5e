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


async def _create_multiplayer_combat_room(client, db_session, sample_module, *, name_prefix: str):
    import uuid as _uuid
    from models import Character

    host = await _register(client, f"{name_prefix}_host", display_name="Host Player")
    guest = await _register(client, f"{name_prefix}_guest", display_name="Guest Player")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": f"{name_prefix} room",
        "max_players": 4,
    })).json()
    sid = created["session_id"]
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": created["room_code"],
    })

    host_char = Character(
        id=str(_uuid.uuid4()),
        name=f"{name_prefix} Hero",
        race="Human",
        char_class="Fighter",
        level=1,
        ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        derived={
            "hp_max": 12,
            "ac": 16,
            "initiative": 2,
            "attack_bonus": 5,
            "damage_dice": "1d8+3",
            "ability_modifiers": {"str": 3, "dex": 1, "con": 2, "int": 0, "wis": 0, "cha": 0},
        },
        hp_current=12,
        is_player=True,
        session_id=sid,
    )
    guest_char = Character(
        id=str(_uuid.uuid4()),
        name=f"{name_prefix} Ally",
        race="Elf",
        char_class="Wizard",
        level=1,
        ability_scores={"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 10},
        derived={
            "hp_max": 6,
            "ac": 12,
            "initiative": 1,
            "ability_modifiers": {"str": -1, "dex": 2, "con": 1, "int": 3, "wis": 0, "cha": 0},
        },
        hp_current=6,
        is_player=True,
        session_id=sid,
    )
    db_session.add_all([host_char, guest_char])
    await db_session.commit()

    await client.post(
        f"/game/rooms/{sid}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": host_char.id},
    )
    await client.post(
        f"/game/rooms/{sid}/claim-character",
        headers=_h(guest["token"]),
        json={"character_id": guest_char.id},
    )
    await client.post(
        f"/game/rooms/{sid}/start-ready",
        headers=_h(host["token"]),
        json={"ready": True},
    )
    await client.post(
        f"/game/rooms/{sid}/start-ready",
        headers=_h(guest["token"]),
        json={"ready": True},
    )
    started = await client.post(f"/game/rooms/{sid}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text

    return {
        "host": host,
        "guest": guest,
        "session_id": sid,
        "host_char": host_char,
        "guest_char": guest_char,
    }


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


class DisconnectOnInitialSnapshotWebSocket(QueueWebSocket):
    async def send_json(self, payload):
        if payload.get("type") == "room_state_updated":
            raise WebSocketDisconnect(code=1006)
        await super().send_json(payload)


async def _wait_for_event(
    ws: QueueWebSocket,
    event_type: str,
    timeout: float = 1.0,
    start_index: int = 0,
    predicate=None,
):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        for event in ws.sent[start_index:]:
            if event.get("type") == event_type and (predicate is None or predicate(event)):
                return event
        await asyncio.sleep(0.01)
    raise AssertionError(f"did not receive {event_type}; sent={ws.sent!r}")


def _room_member_online(event, user_id: str, expected: bool) -> bool:
    members = event.get("room", {}).get("members") or []
    return any(
        item.get("user_id") == user_id and item.get("is_online") is expected
        for item in members
    )


def _assert_no_event_types(ws: QueueWebSocket, start_index: int, event_types: set[str]) -> None:
    leaked = [
        event
        for event in ws.sent[start_index:]
        if event.get("type") in event_types
    ]
    assert leaked == []


def _assert_no_reaction_prompt_events(ws: QueueWebSocket, start_index: int) -> None:
    leaked = [
        event
        for event in ws.sent[start_index:]
        if event.get("reaction_prompt") is not None
    ]
    assert leaked == []


async def test_http_leave_closes_leaving_member_websocket_and_prunes_room_state(
    client,
    db_session,
    sample_module,
):
    from models import Session
    from services.ws_manager import ws_manager
    from sqlalchemy.orm.attributes import flag_modified

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()

    host = await _register(client, "ws_leave_host", display_name="Leave Host")
    guest = await _register(client, "ws_leave_guest", display_name="Leave Guest")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS leave cleanup room",
        "max_players": 4,
    })).json()
    sid = created["session_id"]
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": created["room_code"],
    })

    session = await db_session.get(Session, sid)
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    mp.update({
        "current_speaker_user_id": guest["user_id"],
        "online_user_ids": [host["user_id"], guest["user_id"]],
        "start_ready_user_ids": [host["user_id"], guest["user_id"]],
        "active_group_id": "scout",
        "party_groups": [
            {
                "id": "main",
                "name": "Main",
                "location": "Hall",
                "member_user_ids": [host["user_id"]],
            },
            {
                "id": "scout",
                "name": "Scout",
                "location": "Alley",
                "member_user_ids": [guest["user_id"]],
            },
        ],
        "pending_actions": [
            {"user_id": guest["user_id"], "text": "I scout ahead."},
        ],
        "pending_actions_by_group": {
            "main": [],
            "scout": [
                {"user_id": guest["user_id"], "text": "I scout ahead."},
            ],
        },
        "group_readiness": {
            "main": {host["user_id"]: "ready"},
            "scout": {guest["user_id"]: "ready"},
        },
    })
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    try:
        await ws_manager.connect(sid, host["user_id"], host_ws)
        await ws_manager.connect(sid, guest["user_id"], guest_ws)

        response = await client.post(f"/game/rooms/{sid}/leave", headers=_h(guest["token"]))

        assert response.status_code == 200, response.text
        assert response.json()["room_dissolved"] is False
        left = await _wait_for_event(host_ws, "member_left")
        assert left["user_id"] == guest["user_id"]
        assert guest_ws.closed == {"code": 4001, "reason": "Left room"}
        assert await ws_manager.online_users(sid) == [host["user_id"]]

        room = (await client.get(f"/game/rooms/{sid}", headers=_h(host["token"]))).json()
        assert room["current_speaker_user_id"] == host["user_id"]
        groups = {group["id"]: group for group in room["party_groups"]}
        assert set(groups) == {"main"}
        assert groups["main"]["member_user_ids"] == [host["user_id"]]
        assert room["pending_actions_by_group"] == {"main": []}
        assert room["group_readiness"] == {"main": {host["user_id"]: "ready"}}

        await db_session.refresh(session)
        session_mp = session.game_state["multiplayer"]
        assert session_mp["online_user_ids"] == [host["user_id"]]
        assert session_mp["start_ready_user_ids"] == [host["user_id"]]
        assert session_mp["pending_actions"] == []
    finally:
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_http_last_host_leave_dissolves_room_and_closes_room_websockets(
    client,
    db_session,
    sample_module,
):
    from models import Session
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()

    host = await _register(client, "ws_dissolve_host", display_name="Dissolve Host")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS dissolve room",
        "max_players": 4,
    })).json()
    sid = created["session_id"]

    host_ws = QueueWebSocket()
    try:
        await ws_manager.connect(sid, host["user_id"], host_ws)

        response = await client.post(f"/game/rooms/{sid}/leave", headers=_h(host["token"]))

        assert response.status_code == 200, response.text
        assert response.json()["room_dissolved"] is True
        dissolved = await _wait_for_event(host_ws, "room_dissolved")
        assert dissolved["by_user_id"] == host["user_id"]
        assert host_ws.closed == {"code": 4002, "reason": "Room dissolved"}
        assert await ws_manager.online_users(sid) == []
        assert sid not in ws_manager.rooms

        session = await db_session.get(Session, sid)
        await db_session.refresh(session)
        assert session.room_code is None
        assert session.host_user_id is None
        assert session.game_state["multiplayer"]["online_user_ids"] == []
        assert session.game_state["multiplayer"]["party_groups"][0]["member_user_ids"] == []
    finally:
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_ws_connect_sends_online_snapshot_to_connecting_member(
    client,
    engine,
    sample_module,
    monkeypatch,
):
    """Connecting clients need their own online snapshot so the UI can clear stale offline state."""
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

    host = await _register(client, "ws_self_host", display_name="Host Player")
    guest = await _register(client, "ws_self_guest", display_name="Guest Player")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS self online room",
        "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": created["room_code"],
    })

    host_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, created["session_id"], token=host["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        online = await _wait_for_event(host_ws, "member_online")
        assert online["user_id"] == host["user_id"]
        self_member = next(item for item in online["members"] if item["user_id"] == host["user_id"])
        assert self_member["is_online"] is True
        snapshot = await _wait_for_event(host_ws, "room_state_updated")
        assert snapshot["room"]["session_id"] == created["session_id"]
        assert snapshot["room"]["members"][0]["is_online"] is True
        assert set(snapshot["room"]["party_groups"][0]["member_user_ids"]) == {
            host["user_id"],
            guest["user_id"],
        }
    finally:
        await host_ws.disconnect()
        await asyncio.gather(host_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_ws_connect_broadcasts_room_state_snapshot_to_existing_members(
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

    host = await _register(client, "ws_online_snapshot_host", display_name="Host Player")
    guest = await _register(client, "ws_online_snapshot_guest", display_name="Guest Player")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS online room state room",
        "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": created["room_code"],
    })

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, created["session_id"], token=host["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")
        await _wait_for_event(host_ws, "room_state_updated")

        before_guest_connect = len(host_ws.sent)
        guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, created["session_id"], token=guest["token"]))
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)

        online = await _wait_for_event(host_ws, "member_online", start_index=before_guest_connect)
        assert online["user_id"] == guest["user_id"]
        update = await _wait_for_event(host_ws, "room_state_updated", start_index=before_guest_connect)
        assert update["room"]["session_id"] == created["session_id"]
        guest_member = next(item for item in update["room"]["members"] if item["user_id"] == guest["user_id"])
        assert guest_member["is_online"] is True
        assert set(update["room"]["party_groups"][0]["member_user_ids"]) == {
            host["user_id"],
            guest["user_id"],
        }
        guest_snapshot = await _wait_for_event(guest_ws, "room_state_updated")
        assert guest_snapshot["room"]["session_id"] == created["session_id"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        tasks = [host_task]
        if "guest_task" in locals():
            tasks.append(guest_task)
        await asyncio.gather(*tasks, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_ws_disconnect_during_initial_snapshot_cleans_manager(
    client,
    engine,
    sample_module,
    monkeypatch,
):
    """A browser refresh can close the socket while the initial room snapshot is being sent."""
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

    host = await _register(client, "ws_initial_drop_host", display_name="Host Player")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS initial drop room",
        "max_players": 4,
    })).json()

    ws = DisconnectOnInitialSnapshotWebSocket()

    await ws_api.ws_endpoint(ws, created["session_id"], token=host["token"])

    assert ws.accepted.is_set()
    assert [event["type"] for event in ws.sent] == ["member_online"]
    assert ws_manager.rooms == {}
    assert ws_manager.user_ws == {}
    assert ws_manager.ws_meta == {}


async def test_kick_vote_reaches_room_websocket_clients(
    client,
    engine,
    sample_module,
    monkeypatch,
):
    """HTTP kick votes should update connected room clients in realtime."""
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

    host = await _register(client, "ws_vote_host", display_name="Vote Host")
    voter = await _register(client, "ws_vote_voter", display_name="Vote Voter")
    target = await _register(client, "ws_vote_target", display_name="Vote Target")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS vote room",
        "max_players": 4,
    })).json()
    for user in (voter, target):
        joined = await client.post("/game/rooms/join", headers=_h(user["token"]), json={
            "room_code": created["room_code"],
        })
        assert joined.status_code == 200, joined.text

    host_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, created["session_id"], token=host["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")
        await _wait_for_event(host_ws, "room_state_updated")

        before_pending = len(host_ws.sent)
        first_vote = await client.post(
            f"/game/rooms/{created['session_id']}/kick",
            headers=_h(voter["token"]),
            json={"user_id": target["user_id"]},
        )
        assert first_vote.status_code == 200, first_vote.text
        pending = await _wait_for_event(
            host_ws,
            "room_state_updated",
            start_index=before_pending,
        )
        assert pending["room"]["room_votes"][0]["target_user_id"] == target["user_id"]
        assert pending["room"]["room_votes"][0]["yes_user_ids"] == [voter["user_id"]]
        assert not any(
            event.get("type") == "member_kicked"
            for event in host_ws.sent[before_pending:]
        )

        before_pass = len(host_ws.sent)
        second_vote = await client.post(
            f"/game/rooms/{created['session_id']}/kick",
            headers=_h(host["token"]),
            json={"user_id": target["user_id"]},
        )
        assert second_vote.status_code == 200, second_vote.text
        kicked = await _wait_for_event(host_ws, "member_kicked", start_index=before_pass)
        assert kicked["user_id"] == target["user_id"]
        update = await _wait_for_event(
            host_ws,
            "room_state_updated",
            start_index=before_pass,
        )
        assert update["room"]["room_votes"] == []
        assert {member["user_id"] for member in update["room"]["members"]} == {
            host["user_id"],
            voter["user_id"],
        }
    finally:
        await host_ws.disconnect()
        await asyncio.gather(host_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_ws_speak_done_rejected_without_initialized_speaker(
    client,
    engine,
    sample_module,
    monkeypatch,
):
    """未初始化当前发言者时，任意客户端都不能用 speak_done 偷偷推进发言权。"""
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

    host = await _register(client, "ws_no_speaker_host", display_name="Host Player")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS no speaker room",
        "max_players": 4,
    })).json()

    host_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, created["session_id"], token=host["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")
        before = len(host_ws.sent)

        await host_ws.push({"type": "speak_done"})
        error = await _wait_for_event(host_ws, "error", start_index=before)

        assert error["code"] == "not_current_speaker"
        await asyncio.sleep(0.05)
        assert not any(event.get("type") == "dm_speak_turn" for event in host_ws.sent[before:])
    finally:
        await host_ws.disconnect()
        await asyncio.gather(host_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


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
        await _wait_for_event(host_ws, "room_state_updated")
        for _ in range(50):
            online_events = [
                event for event in host_ws.sent
                if event.get("type") == "member_online"
            ]
            if len(online_events) >= 2:
                break
            await asyncio.sleep(0.01)
        assert len([event for event in host_ws.sent if event.get("type") == "member_online"]) >= 2
        await _wait_for_event(
            host_ws,
            "room_state_updated",
            predicate=lambda event: _room_member_online(event, guest["user_id"], True),
        )

        before_disconnect = len(host_ws.sent)
        await guest_ws.disconnect()
        offline = await _wait_for_event(host_ws, "member_offline", start_index=before_disconnect)

        guest_member = next(item for item in offline["members"] if item["user_id"] == guest["user_id"])
        assert guest_member["is_online"] is False
        update = await _wait_for_event(
            host_ws,
            "room_state_updated",
            start_index=before_disconnect,
            predicate=lambda event: _room_member_online(event, guest["user_id"], False),
        )
        update_guest = next(item for item in update["room"]["members"] if item["user_id"] == guest["user_id"])
        assert update_guest["is_online"] is False
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_ws_stale_cleanup_disconnects_inactive_member_and_broadcasts_offline_snapshot(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Stale heartbeats should be cleaned up and reflected in the room snapshot."""
    import api.ws as ws_api
    from datetime import datetime, timedelta
    from models import SessionMember
    from services.ws_cleanup_service import cleanup_stale_ws_connections
    from services.ws_manager import ws_manager
    from sqlalchemy import select

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    host = await _register(client, "ws_stale_host", display_name="Host Player")
    guest = await _register(client, "ws_stale_guest", display_name="Guest Player")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS stale cleanup room",
        "max_players": 4,
    })).json()
    sid = created["session_id"]
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": created["room_code"],
    })

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")
        await _wait_for_event(
            host_ws,
            "room_state_updated",
            predicate=lambda event: _room_member_online(event, guest["user_id"], True),
        )

        guest_member = (
            await db_session.execute(
                select(SessionMember).where(
                    SessionMember.session_id == sid,
                    SessionMember.user_id == guest["user_id"],
                )
            )
        ).scalar_one()
        guest_member.last_seen_at = datetime.utcnow() - timedelta(seconds=120)
        await db_session.commit()

        before_cleanup = len(host_ws.sent)
        removed = await cleanup_stale_ws_connections(db_session, stale_after_seconds=30)
        assert removed == [(sid, guest["user_id"])]
        offline = await _wait_for_event(host_ws, "member_offline", timeout=2, start_index=before_cleanup)
        offline_guest = next(item for item in offline["members"] if item["user_id"] == guest["user_id"])
        assert offline_guest["is_online"] is False
        update = await _wait_for_event(
            host_ws,
            "room_state_updated",
            timeout=2,
            start_index=before_cleanup,
            predicate=lambda event: _room_member_online(event, guest["user_id"], False),
        )
        update_guest = next(item for item in update["room"]["members"] if item["user_id"] == guest["user_id"])
        assert update_guest["is_online"] is False
        assert guest_ws.closed == {"code": 4001, "reason": "Stale websocket connection"}
        assert await ws_manager.online_users(sid) == [host["user_id"]]

        await db_session.refresh(guest_member)
        assert guest_member.last_seen_at is None
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_ws_typing_and_speak_done_drive_table_realtime_events(
    client,
    db_session,
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
    from models import Session
    from sqlalchemy.orm.attributes import flag_modified

    session = await db_session.get(Session, created["session_id"])
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    mp["current_speaker_user_id"] = host["user_id"]
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db_session.commit()

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

        host_before_invalid = len(host_ws.sent)
        guest_before_invalid = len(guest_ws.sent)
        await guest_ws.push({"type": "speak_done"})
        error = await _wait_for_event(guest_ws, "error", start_index=guest_before_invalid)
        assert error["code"] == "not_current_speaker"
        await asyncio.sleep(0.05)
        assert not any(
            event.get("type") == "dm_speak_turn"
            for event in host_ws.sent[host_before_invalid:]
        )
        assert not any(
            event.get("type") == "dm_speak_turn"
            for event in guest_ws.sent[guest_before_invalid:]
        )

        host_before_valid = len(host_ws.sent)
        guest_before_valid = len(guest_ws.sent)
        await host_ws.push({"type": "speak_done"})
        host_turn = await _wait_for_event(host_ws, "dm_speak_turn", start_index=host_before_valid)
        guest_turn = await _wait_for_event(guest_ws, "dm_speak_turn", start_index=guest_before_valid)
        assert host_turn == guest_turn
        assert host_turn["user_id"] == guest["user_id"]
        assert host_turn["auto"] is False
        host_room = await _wait_for_event(host_ws, "room_state_updated", start_index=host_before_valid)
        guest_room = await _wait_for_event(guest_ws, "room_state_updated", start_index=guest_before_valid)
        assert host_room["room"]["current_speaker_user_id"] == guest["user_id"]
        assert guest_room["room"]["current_speaker_user_id"] == guest["user_id"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_room_state_updated_ws_redacts_split_group_pending_actions_per_viewer(
    client,
    engine,
    sample_module,
    monkeypatch,
):
    import json
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

    host = await _register(client, "ws_room_privacy_host", display_name="Room Privacy Host")
    scout = await _register(client, "ws_room_privacy_scout", display_name="Room Privacy Scout")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS room privacy",
        "max_players": 4,
    })).json()
    sid = created["session_id"]
    joined = await client.post("/game/rooms/join", headers=_h(scout["token"]), json={
        "room_code": created["room_code"],
    })
    assert joined.status_code == 200, joined.text
    split = await client.post(
        f"/game/rooms/{sid}/groups/join",
        headers=_h(scout["token"]),
        json={"group_id": "alley", "group_name": "Alley", "location": "Back alley"},
    )
    assert split.status_code == 200, split.text

    host_ws = QueueWebSocket()
    scout_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    scout_task = asyncio.create_task(ws_api.ws_endpoint(scout_ws, sid, token=scout["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(scout_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")
        await _wait_for_event(scout_ws, "member_online")
        await _wait_for_event(host_ws, "room_state_updated")
        await _wait_for_event(scout_ws, "room_state_updated")

        scout_secret = "Scout checks the cellar lock through the side alley."
        host_before_scout_action = len(host_ws.sent)
        scout_before_scout_action = len(scout_ws.sent)
        submitted = await client.post(
            f"/game/rooms/{sid}/groups/actions",
            headers=_h(scout["token"]),
            json={"group_id": "alley", "action_text": scout_secret},
        )
        assert submitted.status_code == 200, submitted.text
        host_update = await _wait_for_event(
            host_ws,
            "room_state_updated",
            start_index=host_before_scout_action,
        )
        scout_update = await _wait_for_event(
            scout_ws,
            "room_state_updated",
            start_index=scout_before_scout_action,
        )
        assert host_update["room"]["pending_actions_by_group"]["alley"][0]["redacted"] is True
        assert "text" not in host_update["room"]["pending_actions_by_group"]["alley"][0]
        assert scout_secret not in json.dumps(host_update["room"], ensure_ascii=False)
        assert scout_update["room"]["pending_actions_by_group"]["alley"][0]["text"] == scout_secret

        host_secret = "Host watches the front door and palms the silver key."
        host_before_host_action = len(host_ws.sent)
        scout_before_host_action = len(scout_ws.sent)
        submitted = await client.post(
            f"/game/rooms/{sid}/groups/actions",
            headers=_h(host["token"]),
            json={"group_id": "main", "action_text": host_secret},
        )
        assert submitted.status_code == 200, submitted.text
        host_update = await _wait_for_event(
            host_ws,
            "room_state_updated",
            start_index=host_before_host_action,
        )
        scout_update = await _wait_for_event(
            scout_ws,
            "room_state_updated",
            start_index=scout_before_host_action,
        )
        assert host_update["room"]["pending_actions_by_group"]["main"][0]["text"] == host_secret
        assert scout_update["room"]["pending_actions_by_group"]["main"][0]["redacted"] is True
        assert "text" not in scout_update["room"]["pending_actions_by_group"]["main"][0]
        assert host_secret not in json.dumps(scout_update["room"], ensure_ascii=False)
    finally:
        await host_ws.disconnect()
        await scout_ws.disconnect()
        await asyncio.gather(host_task, scout_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_http_multiplayer_action_reaches_room_websocket_clients(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """HTTP /game/action should drive the same realtime room events players see in the UI."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "exploration",
                "narrative": "The stuck gate gives way with a clean metallic click.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {},
                "needs_check": {"required": False},
                "combat_triggered": False,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_action",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I ease the gate open.",
        })

        assert response.status_code == 200, response.text
        assert response.json()["narrative"] == "The stuck gate gives way with a clean metallic click."

        thinking = await _wait_for_event(guest_ws, "dm_thinking_start", timeout=2)
        assert thinking["by_user_id"] == host["user_id"]
        assert thinking["action_text"] == "I ease the gate open."

        dm_response = await _wait_for_event(guest_ws, "dm_responded", timeout=2)
        assert dm_response["by_user_id"] == host["user_id"]
        assert dm_response["action_type"] == "exploration"
        assert dm_response["narrative"] == "The stuck gate gives way with a clean metallic click."
        assert dm_response["combat_triggered"] is False

        speaker = await _wait_for_event(guest_ws, "dm_speak_turn", timeout=2)
        assert speaker["user_id"] == guest["user_id"]
        assert speaker["auto"] is True

        room = (await client.get(f"/game/rooms/{sid}", headers=_h(host["token"]))).json()
        assert room["current_speaker_user_id"] == guest["user_id"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_dm_thinking_survives_refresh_and_reconnect_until_response(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Room snapshots should let refreshing/reconnecting players recover in-flight DM thinking."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    dm_call_started = asyncio.Event()
    release_dm_call = asyncio.Event()

    async def fake_call_dm_agent(**kwargs):
        dm_call_started.set()
        await asyncio.wait_for(release_dm_call.wait(), timeout=2)
        return {
            "result": json.dumps({
                "action_type": "exploration",
                "narrative": "The delayed answer arrives.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {},
                "needs_check": {"required": False},
                "combat_triggered": False,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_dm_thinking_reconnect",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]

    guest_ws = QueueWebSocket()
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    action_task = None
    reconnect_ws = None
    reconnect_task = None
    try:
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(guest_ws, "member_online")

        action_task = asyncio.create_task(client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I ask the DM a slow question.",
        }))

        await asyncio.wait_for(dm_call_started.wait(), timeout=2)
        thinking = await _wait_for_event(guest_ws, "dm_thinking_start", timeout=2)
        assert thinking["by_user_id"] == host["user_id"]
        assert thinking["action_text"] == "I ask the DM a slow question."

        refreshed = await client.get(f"/game/rooms/{sid}", headers=_h(guest["token"]))
        assert refreshed.status_code == 200, refreshed.text
        refreshed_thinking = refreshed.json()["dm_thinking"]
        assert refreshed_thinking["active"] is True
        assert refreshed_thinking["by_user_id"] == host["user_id"]
        assert refreshed_thinking["action_text"] == "I ask the DM a slow question."

        reconnect_ws = QueueWebSocket()
        reconnect_task = asyncio.create_task(ws_api.ws_endpoint(reconnect_ws, sid, token=guest["token"]))
        await asyncio.wait_for(reconnect_ws.accepted.wait(), timeout=1)
        reconnect_room = await _wait_for_event(reconnect_ws, "room_state_updated", timeout=2)
        reconnect_thinking = reconnect_room["room"]["dm_thinking"]
        assert reconnect_thinking["active"] is True
        assert reconnect_thinking["by_user_id"] == host["user_id"]
        after_reconnect_snapshot = len(reconnect_ws.sent)

        release_dm_call.set()
        response = await asyncio.wait_for(action_task, timeout=3)
        assert response.status_code == 200, response.text
        assert response.json()["narrative"] == "The delayed answer arrives."

        final_room = await client.get(f"/game/rooms/{sid}", headers=_h(guest["token"]))
        assert final_room.status_code == 200, final_room.text
        assert final_room.json()["dm_thinking"] is None

        room_update = await _wait_for_event(
            reconnect_ws,
            "room_state_updated",
            timeout=2,
            start_index=after_reconnect_snapshot,
        )
        assert room_update["room"]["dm_thinking"] is None
    finally:
        if action_task and not action_task.done():
            release_dm_call.set()
            await asyncio.gather(action_task, return_exceptions=True)
        await guest_ws.disconnect()
        if reconnect_ws:
            await reconnect_ws.disconnect()
        tasks = [guest_task]
        if reconnect_task:
            tasks.append(reconnect_task)
        await asyncio.gather(*tasks, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_dm_thinking_redacts_action_text_for_other_split_group(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Other split-party groups should see that DM is thinking without seeing the action text."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    dm_call_started = asyncio.Event()
    release_dm_call = asyncio.Event()

    async def fake_call_dm_agent(**kwargs):
        dm_call_started.set()
        await asyncio.wait_for(release_dm_call.wait(), timeout=2)
        return {
            "result": json.dumps({
                "action_type": "exploration",
                "narrative": "The front door creaks open.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {},
                "needs_check": {"required": False},
                "combat_triggered": False,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_dm_thinking_privacy",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    secret_action = "Host quietly checks the secret front-door passphrase."

    joined = await client.post(
        f"/game/rooms/{sid}/groups/join",
        headers=_h(guest["token"]),
        json={"group_id": "alley", "group_name": "Alley", "location": "Back street"},
    )
    assert joined.status_code == 200, joined.text
    focused = await client.post(
        f"/game/rooms/{sid}/groups/focus",
        headers=_h(host["token"]),
        json={"group_id": "main"},
    )
    assert focused.status_code == 200, focused.text

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))
    reconnect_ws = None
    reconnect_task = None
    action_task = None

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")
        await _wait_for_event(guest_ws, "member_online")
        await _wait_for_event(host_ws, "room_state_updated")
        await _wait_for_event(guest_ws, "room_state_updated")

        action_task = asyncio.create_task(client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": secret_action,
        }))

        await asyncio.wait_for(dm_call_started.wait(), timeout=2)
        host_thinking = await _wait_for_event(host_ws, "dm_thinking_start", timeout=2)
        guest_thinking = await _wait_for_event(guest_ws, "dm_thinking_start", timeout=2)

        assert host_thinking["by_user_id"] == host["user_id"]
        assert host_thinking["action_text"] == secret_action
        assert host_thinking["redacted"] is False
        assert host_thinking["group_id"] == "main"

        assert guest_thinking["by_user_id"] == host["user_id"]
        assert guest_thinking["redacted"] is True
        assert guest_thinking["visibility"] == "other_group"
        assert guest_thinking["group_id"] == "main"
        assert guest_thinking["action_text"] == "Action text hidden for another group."
        assert secret_action not in json.dumps(guest_thinking)

        host_room = await client.get(f"/game/rooms/{sid}", headers=_h(host["token"]))
        guest_room = await client.get(f"/game/rooms/{sid}", headers=_h(guest["token"]))
        assert host_room.status_code == 200, host_room.text
        assert guest_room.status_code == 200, guest_room.text
        assert host_room.json()["dm_thinking"]["action_text"] == secret_action
        assert guest_room.json()["dm_thinking"]["redacted"] is True
        assert secret_action not in json.dumps(guest_room.json())

        reconnect_ws = QueueWebSocket()
        reconnect_task = asyncio.create_task(ws_api.ws_endpoint(reconnect_ws, sid, token=guest["token"]))
        await asyncio.wait_for(reconnect_ws.accepted.wait(), timeout=1)
        reconnect_room = await _wait_for_event(reconnect_ws, "room_state_updated", timeout=2)
        reconnect_thinking = reconnect_room["room"]["dm_thinking"]
        assert reconnect_thinking["redacted"] is True
        assert reconnect_thinking["action_text"] == "Action text hidden for another group."
        assert secret_action not in json.dumps(reconnect_room)

        release_dm_call.set()
        response = await asyncio.wait_for(action_task, timeout=3)
        assert response.status_code == 200, response.text
        assert response.json()["narrative"] == "The front door creaks open."
    finally:
        if action_task and not action_task.done():
            release_dm_call.set()
            await asyncio.gather(action_task, return_exceptions=True)
        await host_ws.disconnect()
        await guest_ws.disconnect()
        if reconnect_ws:
            await reconnect_ws.disconnect()
        tasks = [host_task, guest_task]
        if reconnect_task:
            tasks.append(reconnect_task)
        await asyncio.gather(*tasks, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_dm_thinking_clears_after_failed_dm_call(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """A failed DM call should not leave teammates stuck in a thinking state."""
    import api.ws as ws_api
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    dm_call_started = asyncio.Event()
    release_dm_call = asyncio.Event()

    async def fake_call_dm_agent(**kwargs):
        dm_call_started.set()
        await asyncio.wait_for(release_dm_call.wait(), timeout=2)
        raise RuntimeError("simulated DM outage")

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_dm_thinking_failure",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]

    guest_ws = QueueWebSocket()
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    action_task = None
    try:
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(guest_ws, "member_online")
        await _wait_for_event(guest_ws, "room_state_updated")

        action_task = asyncio.create_task(client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I ask the DM a doomed question.",
        }))

        await asyncio.wait_for(dm_call_started.wait(), timeout=2)
        thinking = await _wait_for_event(guest_ws, "dm_thinking_start", timeout=2)
        assert thinking["by_user_id"] == host["user_id"]
        after_thinking = len(guest_ws.sent)

        refreshed = await client.get(f"/game/rooms/{sid}", headers=_h(guest["token"]))
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()["dm_thinking"]["by_user_id"] == host["user_id"]

        release_dm_call.set()
        response = await asyncio.wait_for(action_task, timeout=3)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["type"] == "llm_error"
        assert body["retryable"] is True

        final_room = await client.get(f"/game/rooms/{sid}", headers=_h(guest["token"]))
        assert final_room.status_code == 200, final_room.text
        assert final_room.json()["dm_thinking"] is None

        room_update = await _wait_for_event(
            guest_ws,
            "room_state_updated",
            timeout=2,
            start_index=after_thinking,
        )
        assert room_update["room"]["dm_thinking"] is None
    finally:
        if action_task and not action_task.done():
            release_dm_call.set()
            await asyncio.gather(action_task, return_exceptions=True)
        await guest_ws.disconnect()
        await asyncio.gather(guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_dm_thinking_clears_after_dm_timeout(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """A timed-out DM call should cancel work and clear recoverable thinking state."""
    import api.ws as ws_api
    import services.langgraph_client as lc
    import services.game_exploration_service as exploration_service
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )
    monkeypatch.setattr(exploration_service.settings, "dm_agent_timeout_seconds", 0.01)

    dm_call_started = asyncio.Event()
    dm_call_cancelled = asyncio.Event()

    async def fake_call_dm_agent(**kwargs):
        dm_call_started.set()
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            dm_call_cancelled.set()
            raise

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_dm_thinking_timeout",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]

    guest_ws = QueueWebSocket()
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(guest_ws, "member_online")
        await _wait_for_event(guest_ws, "room_state_updated")
        before_action_events = len(guest_ws.sent)

        response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I ask the DM a question that times out.",
        })
        assert dm_call_started.is_set()
        assert dm_call_cancelled.is_set()
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["type"] == "llm_error"
        assert body["retryable"] is True
        assert body["errors"][0]["code"] == "llm_timeout"

        final_room = await client.get(f"/game/rooms/{sid}", headers=_h(guest["token"]))
        assert final_room.status_code == 200, final_room.text
        assert final_room.json()["dm_thinking"] is None

        room_update = await _wait_for_event(
            guest_ws,
            "room_state_updated",
            timeout=2,
            start_index=before_action_events,
        )
        assert room_update["room"]["dm_thinking"] is None
    finally:
        await guest_ws.disconnect()
        await asyncio.gather(guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_dm_events_do_not_cross_room_boundaries(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """DM thinking/responded/speak-turn/room snapshots stay inside the acting room."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "exploration",
                "narrative": "Only one table hears the lock click.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {},
                "needs_check": {"required": False},
                "combat_triggered": False,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)

    room_a = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_dm_isolation_a",
    )
    room_b = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_dm_isolation_b",
    )

    a_host = room_a["host"]
    a_guest = room_a["guest"]
    b_host = room_b["host"]
    b_guest = room_b["guest"]
    a_sid = room_a["session_id"]
    b_sid = room_b["session_id"]

    a_guest_ws = QueueWebSocket()
    b_host_ws = QueueWebSocket()
    b_guest_ws = QueueWebSocket()
    a_guest_task = asyncio.create_task(ws_api.ws_endpoint(a_guest_ws, a_sid, token=a_guest["token"]))
    b_host_task = asyncio.create_task(ws_api.ws_endpoint(b_host_ws, b_sid, token=b_host["token"]))
    b_guest_task = asyncio.create_task(ws_api.ws_endpoint(b_guest_ws, b_sid, token=b_guest["token"]))

    try:
        await asyncio.wait_for(a_guest_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(b_host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(b_guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(a_guest_ws, "member_online")
        await _wait_for_event(b_host_ws, "member_online")
        await _wait_for_event(b_guest_ws, "member_online")
        await _wait_for_event(b_host_ws, "room_state_updated")
        await _wait_for_event(b_guest_ws, "room_state_updated")

        b_host_before = len(b_host_ws.sent)
        b_guest_before = len(b_guest_ws.sent)

        response = await client.post("/game/action", headers=_h(a_host["token"]), json={
            "session_id": a_sid,
            "action_text": "I quietly open the lock.",
        })
        assert response.status_code == 200, response.text

        thinking = await _wait_for_event(a_guest_ws, "dm_thinking_start", timeout=2)
        assert thinking["by_user_id"] == a_host["user_id"]
        dm_response = await _wait_for_event(a_guest_ws, "dm_responded", timeout=2)
        assert dm_response["narrative"] == "Only one table hears the lock click."
        speak_turn = await _wait_for_event(a_guest_ws, "dm_speak_turn", timeout=2)
        assert speak_turn["user_id"] == a_guest["user_id"]
        room_update = await _wait_for_event(a_guest_ws, "room_state_updated", timeout=2)
        assert room_update["room"]["session_id"] == a_sid

        await asyncio.sleep(0.05)
        forbidden = {"dm_thinking_start", "dm_responded", "dm_speak_turn", "room_state_updated"}
        _assert_no_event_types(b_host_ws, b_host_before, forbidden)
        _assert_no_event_types(b_guest_ws, b_guest_before, forbidden)
    finally:
        await a_guest_ws.disconnect()
        await b_host_ws.disconnect()
        await b_guest_ws.disconnect()
        await asyncio.gather(a_guest_task, b_host_task, b_guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_http_multiplayer_combat_trigger_notifies_room_websocket_clients(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """When exploration triggers combat, realtime clients should see the combat transition signal."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "Two clockwork sentries unfold from the gate and attack.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "combat_trigger_reason": "The sentries attack the party.",
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 9,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_combat",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I force the gate open.",
        })

        assert response.status_code == 200, response.text
        assert response.json()["combat_triggered"] is True

        dm_response = await _wait_for_event(guest_ws, "dm_responded", timeout=2)
        assert dm_response["by_user_id"] == host["user_id"]
        assert dm_response["action_type"] == "combat_start"
        assert dm_response["combat_triggered"] is True
        assert dm_response["narrative"] == "Two clockwork sentries unfold from the gate and attack."

        session_payload = (await client.get(f"/game/sessions/{sid}", headers=_h(host["token"]))).json()
        assert session_payload["combat_active"] is True
        assert session_payload["game_state"]["enemies"][0]["name"] == "Clockwork Sentry"

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        assert host_char.id in combat_payload["entities"]
        assert guest_char.id in combat_payload["entities"]
        assert any(turn["character_id"] == host_char.id for turn in combat_payload["turn_order"])
        assert any(turn["character_id"] == guest_char.id for turn in combat_payload["turn_order"])
        assert combat_payload["session_id"] == sid
        assert any(
            entity["name"] == "Clockwork Sentry" and entity["is_enemy"] is True
            for entity in combat_payload["entities"].values()
        )
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_damage_roll_broadcasts_combat_update(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Damage rolls should refresh other players' combat UI through WebSocket."""
    import json
    import api.ws as ws_api
    import api.combat.attacks as attacks_api
    import services.langgraph_client as lc
    import services.combat_narrator as narrator
    from services.combat_service import AttackResult
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A clockwork sentry blocks the gate.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 9,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    async def fake_narrate_action(**kwargs):
        return None

    def fake_resolve_melee_attack(**kwargs):
        return AttackResult(
            attack_roll={
                "d20": 18,
                "attack_bonus": 5,
                "attack_total": 23,
                "target_ac": 13,
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
            },
            damage=7,
            damage_roll={"notation": "1d8+3", "rolls": [4], "total": 7},
            narration="Host direct attack hits.",
        )

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(narrator, "narrate_action", fake_narrate_action)
    monkeypatch.setattr(attacks_api.svc, "resolve_melee_attack", fake_resolve_melee_attack)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_damage",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I draw the sentry into melee.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        host_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == host_char.id
        )
        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = host_turn_index
        positions = dict(combat_row.entity_positions or {})
        positions[host_char.id] = {"x": 5, "y": 5}
        positions[enemy["id"]] = {"x": 6, "y": 5}
        combat_row.entity_positions = positions
        await db_session.commit()

        before_count = len(guest_ws.sent)
        attack = await client.post(
            f"/game/combat/{sid}/attack-roll",
            headers=_h(host["token"]),
            json={
                "entity_id": host_char.id,
                "target_id": enemy["id"],
                "action_type": "melee",
                "d20_value": 18,
            },
        )
        assert attack.status_code == 200, attack.text
        assert attack.json()["hit"] is True

        damage = await client.post(
            f"/game/combat/{sid}/damage-roll",
            headers=_h(host["token"]),
            json={
                "pending_attack_id": attack.json()["pending_attack_id"],
                "damage_values": [4],
            },
        )
        assert damage.status_code == 200, damage.text

        update = await _wait_for_event(guest_ws, "combat_update", timeout=2, start_index=before_count)
        assert update["current_entity_id"] == host_char.id
        assert update["actor_id"] == host_char.id
        assert update["actor_name"] == host_char.name
        assert update["action"] == "attack"
        assert update["narration"] == damage.json()["narration"]
        assert update["target_id"] == enemy["id"]
        assert update["target_name"] == damage.json()["target_name"]
        assert update["target_new_hp"] == damage.json()["target_new_hp"]
        assert update["attack_result"]["d20"] == 18
        assert update["attack_result"]["hit"] is True
        assert update["attack_result"]["target_conditions"] == []
        assert update["damage"] == damage.json()["damage_total"]
        assert update["total_damage"] == damage.json()["total_damage"]
        assert update["damage_roll"]["notation"] == damage.json()["damage_dice"]
        assert update["damage_roll"]["rolls"] == [4]
        assert update["damage_roll"]["total"] == damage.json()["damage_total"]
        assert update["damage_type"] == damage.json()["damage_type"]
        assert update["target_state"] == damage.json()["target_state"]
        updated_enemy = update["combat"]["entities"][enemy["id"]]
        assert updated_enemy["hp_current"] == damage.json()["target_new_hp"]
        assert updated_enemy["hp_current"] < enemy["hp_current"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_direct_attack_broadcasts_action_details(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Legacy direct attacks should give observers the same public result detail as the actor."""
    import json
    import api.ws as ws_api
    import api.combat.attacks as attacks_api
    import services.langgraph_client as lc
    import services.combat_narrator as narrator
    from services.combat_service import AttackResult
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A clockwork sentry blocks the gate.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 9,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    async def fake_narrate_action(**kwargs):
        return None

    def fake_resolve_melee_attack(**kwargs):
        return AttackResult(
            attack_roll={
                "d20": 18,
                "attack_bonus": 5,
                "attack_total": 23,
                "target_ac": 13,
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
            },
            damage=7,
            damage_roll={"notation": "1d8+3", "rolls": [4], "total": 7},
            narration="Host direct attack hits.",
        )

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(narrator, "narrate_action", fake_narrate_action)
    monkeypatch.setattr(attacks_api.svc, "resolve_melee_attack", fake_resolve_melee_attack)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_direct_attack",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I draw the sentry into melee.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        host_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == host_char.id
        )
        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = host_turn_index
        positions = dict(combat_row.entity_positions or {})
        positions[host_char.id] = {"x": 5, "y": 5}
        positions[enemy["id"]] = {"x": 6, "y": 5}
        combat_row.entity_positions = positions
        await db_session.commit()

        before_count = len(guest_ws.sent)
        action = await client.post(
            f"/game/combat/{sid}/action",
            headers=_h(host["token"]),
            json={
                "action_text": "普通攻击",
                "target_id": enemy["id"],
                "is_ranged": False,
            },
        )
        assert action.status_code == 200, action.text
        body = action.json()
        assert body["attack_result"]["hit"] is True

        update = await _wait_for_event(guest_ws, "combat_update", timeout=2, start_index=before_count)
        assert update["current_entity_id"] == host_char.id
        assert update["actor_id"] == host_char.id
        assert update["actor_name"] == host_char.name
        assert update["action"] == "attack"
        assert update["narration"] == body["narration"]
        assert update["target_id"] == body["target_id"]
        assert update["target_name"] == enemy["name"]
        assert update["target_new_hp"] == body["target_new_hp"]
        assert update["target_state"] == body["target_state"]
        assert update["attack_result"] == body["attack_result"]
        assert update["damage"] == body["damage"]
        assert update["total_damage"] == body["damage"]
        assert update["damage_roll"] == body["damage_roll"]
        assert update["damage_type"]
        assert update["sneak_attack"] == body["sneak_attack"]
        assert update["sneak_attack_damage"] == body["sneak_attack_damage"]
        assert update["extra_damage_notes"] == body["extra_damage_notes"]
        assert update["weapon_resource"] == body["weapon_resource"]
        assert update["defender_interception"] == body["defender_interception"]
        assert update["concentration_check"] == body["concentration_check"]
        updated_enemy = update["combat"]["entities"][enemy["id"]]
        assert updated_enemy["hp_current"] == body["target_new_hp"]
        assert updated_enemy["hp_current"] < enemy["hp_current"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_spell_confirm_broadcasts_spell_result_details(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """/spell-confirm should give observers the resolved public spell payload once."""
    import json
    import api.ws as ws_api
    import api.combat.spell_rolls as spell_rolls_api
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A clockwork sentry blocks the gate.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 12,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    async def fake_narrate_action(**kwargs):
        return None

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(spell_rolls_api, "narrate_action", fake_narrate_action)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_spell_confirm",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]

    host_char.char_class = "Wizard"
    host_char.spell_slots = {"1st": 1}
    host_char.known_spells = ["魔法飞弹"]
    host_char.prepared_spells = ["魔法飞弹"]
    host_char.derived = {
        **(host_char.derived or {}),
        "spell_ability": "int",
        "spell_save_dc": 13,
        "spell_attack_bonus": 5,
        "ability_modifiers": {
            **(host_char.derived or {}).get("ability_modifiers", {}),
            "int": 3,
        },
    }
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I draw the sentry into spell range.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        host_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == host_char.id
        )
        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = host_turn_index
        positions = dict(combat_row.entity_positions or {})
        positions[host_char.id] = {"x": 5, "y": 5}
        positions[enemy["id"]] = {"x": 9, "y": 5}
        combat_row.entity_positions = positions
        await db_session.commit()

        prepare_start = len(guest_ws.sent)
        spell_roll = await client.post(
            f"/game/combat/{sid}/spell-roll",
            headers=_h(host["token"]),
            json={
                "caster_id": host_char.id,
                "spell_name": "魔法飞弹",
                "spell_level": 1,
                "target_id": enemy["id"],
            },
        )
        assert spell_roll.status_code == 200, spell_roll.text
        roll_body = spell_roll.json()
        assert roll_body["pending_spell_id"]
        assert roll_body["damage_dice"] == "3d4+3"
        assert roll_body["dice_result"]["type"] == "spell_prepare"
        assert roll_body["special_action"] == roll_body["dice_result"]

        prepare_update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=prepare_start,
            predicate=lambda event: (event.get("dice_result") or {}).get("type") == "spell_prepare",
        )
        assert prepare_update["current_entity_id"] == host_char.id
        assert prepare_update["actor_id"] == host_char.id
        assert prepare_update["actor_name"] == host_char.name
        assert prepare_update["action"] == "spell_roll"
        assert prepare_update["narration"] == roll_body["narration"]
        assert prepare_update["dice_result"] == roll_body["dice_result"]
        assert prepare_update["special_action"] == roll_body["dice_result"]
        assert prepare_update["dice_result"]["spell_name"] == "魔法飞弹"
        assert prepare_update["dice_result"]["damage_dice"] == "3d4+3"
        assert prepare_update["dice_result"]["target_count"] == 1
        assert "turn_state" not in prepare_update

        before_count = len(guest_ws.sent)
        confirm = await client.post(
            f"/game/combat/{sid}/spell-confirm",
            headers=_h(host["token"]),
            json={
                "pending_spell_id": roll_body["pending_spell_id"],
                "damage_values": [1, 2, 3],
            },
        )
        assert confirm.status_code == 200, confirm.text
        body = confirm.json()

        update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=before_count,
            predicate=lambda event: event.get("spell_result") is not None,
        )
        assert update["current_entity_id"] == host_char.id
        assert update["actor_id"] == host_char.id
        assert update["actor_name"] == host_char.name
        assert update["action"] == "spell"
        assert update["narration"] == body["narration"]
        assert update["target_id"] == enemy["id"]
        assert update["target_new_hp"] == body["target_new_hp"]
        assert update["target_state"] == body["target_state"]
        assert update["damage"] == body["damage"]
        assert update["heal"] == body["heal"]
        assert update["dice_result"] == body["dice_result"]
        assert update["spell_result"] == body["dice_result"]
        assert update["aoe_results"] == body["aoe_results"]
        assert update["remaining_slots"] == body["remaining_slots"]
        assert update["concentration_check"] == body["concentration_check"]
        assert update["concentration_checks"] == body["concentration_checks"]
        assert update["wild_magic_surge"] == body["wild_magic_surge"]
        assert update["wild_magic_check"] == body["wild_magic_check"]
        assert "turn_state" not in update
        matching_updates = [
            event
            for event in guest_ws.sent[before_count:]
            if event.get("type") == "combat_update" and event.get("action") == "spell"
        ]
        assert len(matching_updates) == 1
        updated_enemy = update["combat"]["entities"][enemy["id"]]
        assert updated_enemy["hp_current"] == body["target_new_hp"]
        assert updated_enemy["hp_current"] < enemy["hp_current"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_direct_spell_broadcasts_spell_result_details(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Legacy direct /spell should give observers the same public spell result detail as the actor."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A clockwork sentry blocks the gate.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 30,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_direct_spell",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    magic_missile = "\u9b54\u6cd5\u98de\u5f39"

    host_char.char_class = "Wizard"
    host_char.spell_slots = {"1st": 1}
    host_char.known_spells = [magic_missile]
    host_char.prepared_spells = [magic_missile]
    host_char.derived = {
        **(host_char.derived or {}),
        "spell_ability": "int",
        "spell_save_dc": 13,
        "spell_attack_bonus": 5,
        "ability_modifiers": {
            **(host_char.derived or {}).get("ability_modifiers", {}),
            "int": 3,
        },
    }
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I draw the sentry into spell range.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        host_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == host_char.id
        )
        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = host_turn_index
        positions = dict(combat_row.entity_positions or {})
        positions[host_char.id] = {"x": 5, "y": 5}
        positions[enemy["id"]] = {"x": 9, "y": 5}
        combat_row.entity_positions = positions
        await db_session.commit()

        before_count = len(guest_ws.sent)
        direct_spell = await client.post(
            f"/game/combat/{sid}/spell",
            headers=_h(host["token"]),
            json={
                "caster_id": host_char.id,
                "spell_name": magic_missile,
                "spell_level": 1,
                "target_id": enemy["id"],
            },
        )
        assert direct_spell.status_code == 200, direct_spell.text
        body = direct_spell.json()

        update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=before_count,
            predicate=lambda event: event.get("spell_result") is not None,
        )
        assert update["current_entity_id"] == host_char.id
        assert update["actor_id"] == host_char.id
        assert update["actor_name"] == host_char.name
        assert update["action"] == "spell"
        assert update["narration"] == body["narration"]
        assert update["target_id"] == body["target_id"]
        assert update["target_new_hp"] == body["target_new_hp"]
        assert update["target_state"] == body["target_state"]
        assert update["damage"] == body["damage"]
        assert update["heal"] == body["heal"]
        assert update["dice_result"] == body["dice_result"]
        assert update["spell_result"] == body["spell_result"]
        assert update["aoe_results"] == body["aoe_results"]
        assert update["resurrection_results"] == body["resurrection_results"]
        assert update["remaining_slots"] == body["remaining_slots"]
        assert update["concentration_check"] == body["concentration_check"]
        assert update["concentration_checks"] == body["concentration_checks"]
        assert "turn_state" not in update
        matching_updates = [
            event
            for event in guest_ws.sent[before_count:]
            if event.get("type") == "combat_update" and event.get("action") == "spell"
        ]
        assert len(matching_updates) == 1
        updated_enemy = update["combat"]["entities"][enemy["id"]]
        assert updated_enemy["hp_current"] == body["target_new_hp"]
        assert updated_enemy["hp_current"] < enemy["hp_current"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_class_feature_broadcasts_feature_result_details(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Class features should give observers the same public result detail as the actor."""
    import json
    import api.ws as ws_api
    import api.combat.class_features as class_features_api
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A clockwork sentry blocks the gate.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 12,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    async def fake_narrate_action(**kwargs):
        return None

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(class_features_api, "narrate_action", fake_narrate_action)
    monkeypatch.setattr(
        class_features_api,
        "roll_dice",
        lambda notation: {"notation": notation, "rolls": [4], "total": 5},
    )

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_class_feature",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]

    host_char.char_class = "Fighter"
    host_char.level = 1
    host_char.hp_current = 5
    host_char.class_resources = {}
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I brace and recover before the sentry closes.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        host_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == host_char.id
        )
        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = host_turn_index
        await db_session.commit()

        before_count = len(guest_ws.sent)
        feature = await client.post(
            f"/game/combat/{sid}/class-feature",
            headers=_h(host["token"]),
            json={"feature_name": "second_wind"},
        )
        assert feature.status_code == 200, feature.text
        body = feature.json()
        assert body["feature"] == "second_wind"
        assert body["target_state"]["hp_current"] == 10
        assert body["dice_result"]["type"] == "class_feature"
        assert body["dice_result"]["target_state"] == body["target_state"]
        assert body["dice_result"]["turn_state"] == body["turn_state"]

        update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=before_count,
            predicate=lambda event: event.get("action") == "class_feature",
        )
        assert update["current_entity_id"] == host_char.id
        assert update["actor_id"] == host_char.id
        assert update["actor_name"] == host_char.name
        assert update["action"] == "class_feature"
        assert update["feature"] == "second_wind"
        assert update["narration"] == body["narration"]
        assert update["target_id"] == host_char.id
        assert update["target_name"] == host_char.name
        assert update["target_state"] == body["target_state"]
        assert update["actor_state"] == body["actor_state"]
        assert update["dice_result"] == body["dice_result"]
        assert update["special_action"] == body["special_action"]
        assert "turn_state" not in update
        updated_host = update["combat"]["entities"][host_char.id]
        assert updated_host["hp_current"] == body["hp_current"]
        assert update["combat"]["turn_states"][host_char.id]["bonus_action_used"] is True
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_maneuver_broadcasts_maneuver_result_details(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Battle Master maneuvers should give observers the same public result detail as the actor."""
    import json
    import api.ws as ws_api
    import services.combat_maneuver_service as maneuver_service
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A clockwork sentry blocks the gate.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 12,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                            "ability_scores": {"str": 8, "wis": 8},
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(maneuver_service, "roll_dice", lambda expr: {"formula": expr, "total": 5})
    monkeypatch.setattr(maneuver_service.random, "randint", lambda *_args: 1)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_maneuver",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]

    host_char.char_class = "Fighter"
    host_char.level = 3
    host_char.derived = {
        **(host_char.derived or {}),
        "proficiency_bonus": 2,
        "ability_modifiers": {
            "str": 4,
            "dex": 2,
            "con": 2,
            "int": 0,
            "wis": 0,
            "cha": 0,
        },
        "subclass_effects": {
            "battle_master": True,
            "maneuvers": ["trip"],
            "superiority_die": "d8",
        },
    }
    host_char.class_resources = {
        "superiority_dice_remaining": 1,
        "maneuvers_known": ["trip"],
    }
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I sweep low at the sentry's legs.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        host_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == host_char.id
        )
        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = host_turn_index
        await db_session.commit()

        before_count = len(guest_ws.sent)
        maneuver = await client.post(
            f"/game/combat/{sid}/maneuver",
            headers=_h(host["token"]),
            json={"maneuver_name": "trip", "target_id": enemy["id"]},
        )
        assert maneuver.status_code == 200, maneuver.text
        body = maneuver.json()
        assert body["action"] == "maneuver"
        assert body["type"] == "maneuver"
        assert body["maneuver"] == "trip"
        assert body["dice_result"]["type"] == "maneuver"
        assert body["dice_result"]["target_state"] == body["target_state"]
        assert body["special_action"] == body["dice_result"]
        assert body["class_resources"]["superiority_dice_remaining"] == 0
        assert body["target_state"]["conditions"] == ["prone"]

        update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=before_count,
            predicate=lambda event: event.get("action") == "maneuver",
        )
        assert update["current_entity_id"] == host_char.id
        assert update["actor_id"] == host_char.id
        assert update["actor_name"] == host_char.name
        assert update["action"] == "maneuver"
        assert update["maneuver"] == "trip"
        assert update["narration"] == body["narration"]
        assert update["target_id"] == body["target_id"]
        assert update["target_name"] == body["target_name"]
        assert update["target_state"] == body["target_state"]
        assert update["dice_result"] == body["dice_result"]
        assert update["special_action"] == body["special_action"]
        assert update["class_resources"] == body["class_resources"]
        assert "turn_state" not in update
        updated_enemy = update["combat"]["entities"][enemy["id"]]
        assert "prone" in updated_enemy["conditions"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_grapple_shove_broadcasts_contested_result_details(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Grapple/shove actions should give observers the same contested-check detail as the actor."""
    import json
    import api.ws as ws_api
    import services.combat_grapple_service as grapple_service
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A clockwork sentry blocks the gate.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 12,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                            "derived": {
                                "ability_modifiers": {"str": 0, "dex": 1},
                                "proficiency_bonus": 2,
                            },
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    async def fake_narrate_action(**kwargs):
        return None

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(grapple_service, "narrate_action", fake_narrate_action)
    monkeypatch.setattr(
        grapple_service.svc,
        "resolve_grapple",
        lambda *_args, **_kwargs: {
            "success": True,
            "attacker_roll": {"skill": "Athletics", "total": 18},
            "target_roll": {"skill": "Athletics", "total": 10},
        },
    )

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_grapple",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]

    host_char.derived = {
        **(host_char.derived or {}),
        "proficiency_bonus": 2,
        "ability_modifiers": {
            "str": 4,
            "dex": 1,
            "con": 2,
            "int": 0,
            "wis": 0,
            "cha": 0,
        },
    }
    host_char.proficient_skills = ["Athletics"]
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I close and seize the sentry.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        host_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == host_char.id
        )
        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = host_turn_index
        await db_session.commit()

        before_count = len(guest_ws.sent)
        grapple = await client.post(
            f"/game/combat/{sid}/grapple-shove",
            headers=_h(host["token"]),
            json={"action_type": "grapple", "target_id": enemy["id"]},
        )
        assert grapple.status_code == 200, grapple.text
        body = grapple.json()
        assert body["action"] == "grapple"
        assert body["dice_result"]["type"] == "grapple"
        assert body["special_action"] == body["dice_result"]
        assert body["dice_result"]["target_state"] == body["target_state"]
        assert body["target_state"]["conditions"] == ["grappled"]

        update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=before_count,
            predicate=lambda event: event.get("action") == "grapple",
        )
        assert update["current_entity_id"] == host_char.id
        assert update["actor_name"] == host_char.name
        assert update["action"] == "grapple"
        assert update["narration"] == body["narration"]
        assert update["target_id"] == body["target_id"]
        assert update["target_name"] == body["target_name"]
        assert update["target_state"] == body["target_state"]
        assert update["condition_result"] == body["condition_result"]
        assert update["dice_result"] == body["dice_result"]
        assert update["special_action"] == body["special_action"]
        assert "turn_state" not in update
        updated_enemy = update["combat"]["entities"][enemy["id"]]
        assert "grappled" in updated_enemy["conditions"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_grapple_escape_broadcasts_escape_result_details(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Grapple escape should give observers the same contested-check detail as the actor."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A clockwork sentry blocks the gate.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 12,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                            "derived": {
                                "ability_modifiers": {"str": 0, "dex": 1},
                                "proficiency_bonus": 2,
                            },
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_grapple_escape",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]

    host_char.derived = {
        **(host_char.derived or {}),
        "proficiency_bonus": 10,
        "ability_modifiers": {
            "str": 50,
            "dex": 1,
            "con": 2,
            "int": 0,
            "wis": 0,
            "cha": 0,
        },
    }
    host_char.proficient_skills = ["Athletics"]
    host_char.conditions = ["grappled"]
    host_char.condition_durations = {"grappled": {"source_id": "enemy-1"}}
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I strain against the sentry's grip.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        host_char.condition_durations = {"grappled": {"source_id": enemy["id"]}}
        host_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == host_char.id
        )
        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = host_turn_index
        await db_session.commit()

        before_count = len(guest_ws.sent)
        escape = await client.post(
            f"/game/combat/{sid}/grapple-escape",
            headers=_h(host["token"]),
            json={"source_id": enemy["id"], "skill": "athletics"},
        )
        assert escape.status_code == 200, escape.text
        body = escape.json()
        assert body["action"] == "grapple_escape"
        assert body["dice_result"]["type"] == "grapple_escape"
        assert body["special_action"] == body["dice_result"]
        assert body["condition_result"]["removed"] is True
        assert body["target_state"]["conditions"] == []

        update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=before_count,
            predicate=lambda event: event.get("action") == "grapple_escape",
        )
        assert update["current_entity_id"] == host_char.id
        assert update["actor_name"] == host_char.name
        assert update["action"] == "grapple_escape"
        assert update["narration"] == body["narration"]
        assert update["target_id"] == body["target_id"]
        assert update["target_name"] == body["target_name"]
        assert update["target_state"] == body["target_state"]
        assert update["condition_result"] == body["condition_result"]
        assert update["source_id"] == body["source_id"]
        assert update["source_name"] == body["source_name"]
        assert update["dice_result"] == body["dice_result"]
        assert update["special_action"] == body["special_action"]
        assert "turn_state" not in update
        updated_host = update["combat"]["entities"][host_char.id]
        assert "grappled" not in updated_host["conditions"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_combat_updates_do_not_cross_room_boundaries(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Combat updates from one table must not refresh another table's clients."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    import services.combat_narrator as narrator
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A sentry blocks only this table's gate.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [{
                        "name": "Clockwork Sentry",
                        "hp": 9,
                        "ac": 13,
                        "attack_bonus": 3,
                        "damage_dice": "1d6+1",
                    }],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    async def fake_narrate_action(**kwargs):
        return None

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(narrator, "narrate_action", fake_narrate_action)

    room_a = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_combat_isolation_a",
    )
    room_b = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_combat_isolation_b",
    )

    a_host = room_a["host"]
    a_guest = room_a["guest"]
    b_host = room_b["host"]
    a_sid = room_a["session_id"]
    b_sid = room_b["session_id"]
    a_host_char = room_a["host_char"]

    a_guest_ws = QueueWebSocket()
    b_host_ws = QueueWebSocket()
    a_guest_task = asyncio.create_task(ws_api.ws_endpoint(a_guest_ws, a_sid, token=a_guest["token"]))
    b_host_task = asyncio.create_task(ws_api.ws_endpoint(b_host_ws, b_sid, token=b_host["token"]))

    try:
        await asyncio.wait_for(a_guest_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(b_host_ws.accepted.wait(), timeout=1)
        await _wait_for_event(a_guest_ws, "member_online")
        await _wait_for_event(b_host_ws, "member_online")
        await _wait_for_event(b_host_ws, "room_state_updated")

        start_response = await client.post("/game/action", headers=_h(a_host["token"]), json={
            "session_id": a_sid,
            "action_text": "I draw the sentry into melee.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(a_guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{a_sid}", headers=_h(a_host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        host_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == a_host_char.id
        )

        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == a_sid))
        ).scalars().first()
        combat_row.current_turn_index = host_turn_index
        positions = dict(combat_row.entity_positions or {})
        positions[a_host_char.id] = {"x": 5, "y": 5}
        positions[enemy["id"]] = {"x": 6, "y": 5}
        combat_row.entity_positions = positions
        await db_session.commit()

        b_before = len(b_host_ws.sent)
        a_before = len(a_guest_ws.sent)
        attack = await client.post(
            f"/game/combat/{a_sid}/attack-roll",
            headers=_h(a_host["token"]),
            json={
                "entity_id": a_host_char.id,
                "target_id": enemy["id"],
                "action_type": "melee",
                "d20_value": 18,
            },
        )
        assert attack.status_code == 200, attack.text

        damage = await client.post(
            f"/game/combat/{a_sid}/damage-roll",
            headers=_h(a_host["token"]),
            json={
                "pending_attack_id": attack.json()["pending_attack_id"],
                "damage_values": [4],
            },
        )
        assert damage.status_code == 200, damage.text

        update = await _wait_for_event(a_guest_ws, "combat_update", timeout=2, start_index=a_before)
        assert update["combat"]["session_id"] == a_sid

        await asyncio.sleep(0.05)
        _assert_no_event_types(b_host_ws, b_before, {"combat_update"})
    finally:
        await a_guest_ws.disconnect()
        await b_host_ws.disconnect()
        await asyncio.gather(a_guest_task, b_host_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_ai_turn_targets_guest_and_broadcasts_combat_update(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Enemy AI turns should consider all player characters and broadcast the result."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack
    import services.combat_narrator as narrator
    from services.combat_service import AttackResult
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A sentry picks the weakest target.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 9,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    async def fake_get_ai_decision(**kwargs):
        assert any(character["id"] == guest_char.id for character in kwargs["all_characters"])
        return {"action_type": "attack", "target_id": None, "reason": "test weakest target"}

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 20,
                "target_ac": 12,
            },
            damage=3,
            damage_roll={"formula": "1d6+1", "rolls": [2], "total": 3},
            narration="hit",
        )

    async def fake_narrate_batch(actions):
        return ["" for _ in actions]

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(narrator, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_ai_turn",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    guest_char = room_data["guest_char"]

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I provoke the sentry.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        enemy_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == enemy["id"]
        )
        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = enemy_turn_index
        positions = dict(combat_row.entity_positions or {})
        positions[enemy["id"]] = {"x": 5, "y": 5}
        positions[guest_char.id] = {"x": 6, "y": 5}
        combat_row.entity_positions = positions
        guest_char.hp_current = 6
        await db_session.commit()

        before_count = len(guest_ws.sent)
        ai_result = await client.post(f"/game/combat/{sid}/ai-turn", headers=_h(host["token"]))
        assert ai_result.status_code == 200, ai_result.text
        assert ai_result.json()["target_id"] == guest_char.id
        assert ai_result.json()["target_new_hp"] == 3

        update = await _wait_for_event(guest_ws, "combat_update", timeout=2, start_index=before_count)
        assert update["actor_id"] == enemy["id"]
        assert update["target_id"] == guest_char.id
        assert update["target_new_hp"] == 3
        assert update["combat"]["entities"][guest_char.id]["hp_current"] == 3
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_guest_reaction_uses_guest_character_and_broadcasts_update(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Guest-owned reactions should mutate the guest character and refresh the room."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack
    import services.combat_narrator as narrator
    from services.combat_service import AttackResult
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A sentry draws a blade.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 12,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    async def fake_get_ai_decision(**kwargs):
        return {"action_type": "attack", "target_id": guest_char.id, "reason": "test guest reaction"}

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 18,
                "target_ac": 12,
            },
            damage=3,
            damage_roll={"formula": "1d6+1", "rolls": [2], "total": 3},
            narration="hit",
        )

    async def fake_narrate_batch(actions):
        return ["" for _ in actions]

    async def fake_narrate_action(**kwargs):
        return None

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(narrator, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(narrator, "narrate_action", fake_narrate_action)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_guest_reaction",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    guest_char = room_data["guest_char"]

    guest_char.known_spells = ["Hellish Rebuke"]
    guest_char.spell_slots = {"1st": 1}
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I start the fight.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        enemy_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == enemy["id"]
        )

        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = enemy_turn_index
        positions = dict(combat_row.entity_positions or {})
        positions[enemy["id"]] = {"x": 5, "y": 5}
        positions[guest_char.id] = {"x": 6, "y": 5}
        combat_row.entity_positions = positions
        await db_session.commit()

        before_host_ai_count = len(host_ws.sent)
        before_ai_count = len(guest_ws.sent)
        ai_result = await client.post(f"/game/combat/{sid}/ai-turn", headers=_h(host["token"]))
        assert ai_result.status_code == 200, ai_result.text
        assert ai_result.json()["target_id"] == guest_char.id
        assert ai_result.json()["player_can_react"] is True
        assert ai_result.json()["reaction_prompt"]["reactor_character_id"] == guest_char.id
        assert ai_result.json()["reaction_prompt"]["options"][0]["type"] == "hellish_rebuke"
        assert ai_result.json()["reaction_prompt"]["options"][0]["character_id"] == guest_char.id

        host_ai_update = await _wait_for_event(host_ws, "combat_update", timeout=2, start_index=before_host_ai_count)
        guest_ai_update = await _wait_for_event(guest_ws, "combat_update", timeout=2, start_index=before_ai_count)
        assert host_ai_update.get("player_can_react") is False
        assert host_ai_update.get("reaction_prompt") is None
        assert "pending_attack_reaction" not in host_ai_update["combat"]["turn_states"][guest_char.id]
        assert guest_ai_update["player_can_react"] is True
        assert guest_ai_update["reaction_prompt"]["reactor_character_id"] == guest_char.id
        assert guest_ai_update["reaction_prompt"]["options"][0]["type"] == "hellish_rebuke"
        assert guest_ai_update["combat"]["turn_states"][guest_char.id]["pending_attack_reaction"]["trigger"] == "incoming_attack"

        before_reaction_count = len(host_ws.sent)
        reaction = await client.post(
            f"/game/combat/{sid}/reaction",
            headers=_h(guest["token"]),
            json={
                "reaction_type": "hellish_rebuke",
                "target_id": enemy["id"],
                "character_id": guest_char.id,
            },
        )
        assert reaction.status_code == 200, reaction.text

        await db_session.refresh(guest_char)
        assert guest_char.spell_slots["1st"] == 0

        reaction_update = await _wait_for_event(host_ws, "combat_update", timeout=2, start_index=before_reaction_count)
        assert reaction_update["actor_id"] == guest_char.id
        assert reaction_update["reaction_type"] == "hellish_rebuke"
        assert reaction_update["combat"]["turn_states"][guest_char.id]["reaction_used"] is True
        assert reaction_update["combat"]["entities"][enemy["id"]]["hp_current"] < enemy["hp_current"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_reaction_prompt_does_not_cross_room_boundaries(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Reaction prompts from one table must not appear in another table's combat feed."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack
    import services.combat_narrator as narrator
    from services.combat_service import AttackResult
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A sentry raises a blade at only one table.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 12,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    async def fake_get_ai_decision(**kwargs):
        return {"action_type": "attack", "target_id": a_guest_char.id, "reason": "test reaction prompt isolation"}

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 18,
                "target_ac": 12,
            },
            damage=3,
            damage_roll={"formula": "1d6+1", "rolls": [2], "total": 3},
            narration="hit",
        )

    async def fake_narrate_batch(actions):
        return ["" for _ in actions]

    async def fake_narrate_action(**kwargs):
        return None

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(narrator, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(narrator, "narrate_action", fake_narrate_action)

    room_a = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_reaction_isolation_a",
    )
    room_b = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_reaction_isolation_b",
    )

    a_host = room_a["host"]
    a_guest = room_a["guest"]
    b_host = room_b["host"]
    b_guest = room_b["guest"]
    a_sid = room_a["session_id"]
    b_sid = room_b["session_id"]
    a_guest_char = room_a["guest_char"]

    a_guest_char.known_spells = ["Hellish Rebuke"]
    a_guest_char.spell_slots = {"1st": 1}
    await db_session.commit()

    a_guest_ws = QueueWebSocket()
    b_host_ws = QueueWebSocket()
    b_guest_ws = QueueWebSocket()
    a_guest_task = asyncio.create_task(ws_api.ws_endpoint(a_guest_ws, a_sid, token=a_guest["token"]))
    b_host_task = asyncio.create_task(ws_api.ws_endpoint(b_host_ws, b_sid, token=b_host["token"]))
    b_guest_task = asyncio.create_task(ws_api.ws_endpoint(b_guest_ws, b_sid, token=b_guest["token"]))

    try:
        await asyncio.wait_for(a_guest_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(b_host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(b_guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(a_guest_ws, "member_online")
        await _wait_for_event(b_host_ws, "member_online")
        await _wait_for_event(b_guest_ws, "member_online")
        await _wait_for_event(b_host_ws, "room_state_updated")
        await _wait_for_event(b_guest_ws, "room_state_updated")

        start_response = await client.post("/game/action", headers=_h(a_host["token"]), json={
            "session_id": a_sid,
            "action_text": "I start the isolated fight.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(a_guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{a_sid}", headers=_h(a_host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        enemy_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == enemy["id"]
        )

        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == a_sid))
        ).scalars().first()
        combat_row.current_turn_index = enemy_turn_index
        positions = dict(combat_row.entity_positions or {})
        positions[enemy["id"]] = {"x": 5, "y": 5}
        positions[a_guest_char.id] = {"x": 6, "y": 5}
        combat_row.entity_positions = positions
        await db_session.commit()

        a_before = len(a_guest_ws.sent)
        b_host_before = len(b_host_ws.sent)
        b_guest_before = len(b_guest_ws.sent)
        ai_result = await client.post(f"/game/combat/{a_sid}/ai-turn", headers=_h(a_host["token"]))
        assert ai_result.status_code == 200, ai_result.text
        ai_body = ai_result.json()
        assert ai_body["target_id"] == a_guest_char.id
        assert ai_body["player_can_react"] is True
        assert ai_body["reaction_prompt"]["reactor_character_id"] == a_guest_char.id
        assert ai_body["reaction_prompt"]["options"][0]["type"] == "hellish_rebuke"

        update = await _wait_for_event(a_guest_ws, "combat_update", timeout=2, start_index=a_before)
        assert update["combat"]["session_id"] == a_sid
        assert update["reaction_prompt"]["reactor_character_id"] == a_guest_char.id

        await asyncio.sleep(0.05)
        _assert_no_event_types(b_host_ws, b_host_before, {"combat_update"})
        _assert_no_event_types(b_guest_ws, b_guest_before, {"combat_update"})
        _assert_no_reaction_prompt_events(b_host_ws, b_host_before)
        _assert_no_reaction_prompt_events(b_guest_ws, b_guest_before)
    finally:
        await a_guest_ws.disconnect()
        await b_host_ws.disconnect()
        await b_guest_ws.disconnect()
        await asyncio.gather(a_guest_task, b_host_task, b_guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_guest_shield_retroactively_blocks_ai_hit(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Shield should restore already-applied damage when +5 AC turns the AI hit into a miss."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack
    import api.combat.reactions as reactions
    from services.combat_service import AttackResult
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A sentry levels a spear.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Clockwork Sentry",
                            "hp": 12,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    async def fake_get_ai_decision(**kwargs):
        return {"action_type": "attack", "target_id": guest_char.id, "reason": "test shield reaction"}

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 16,
                "target_ac": 12,
            },
            damage=4,
            damage_roll={"formula": "1d6+1", "rolls": [3], "total": 4},
            narration="hit",
        )

    async def fake_narrate_batch(actions):
        return ["" for _ in actions]

    async def fake_narrate_action(**kwargs):
        return ""

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(reactions, "narrate_action", fake_narrate_action)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_guest_shield",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    guest_char = room_data["guest_char"]

    guest_char.known_spells = ["Shield"]
    guest_char.spell_slots = {"1st": 1}
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I start the fight.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        enemy_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == enemy["id"]
        )

        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = enemy_turn_index
        positions = dict(combat_row.entity_positions or {})
        positions[enemy["id"]] = {"x": 5, "y": 5}
        positions[guest_char.id] = {"x": 6, "y": 5}
        combat_row.entity_positions = positions
        await db_session.commit()

        before_ai_count = len(guest_ws.sent)
        ai_result = await client.post(f"/game/combat/{sid}/ai-turn", headers=_h(host["token"]))
        assert ai_result.status_code == 200, ai_result.text
        ai_body = ai_result.json()
        assert ai_body["target_id"] == guest_char.id
        assert ai_body["target_new_hp"] == 2
        assert ai_body["reaction_prompt"]["available_reactions"][0]["type"] == "shield"
        assert ai_body["reaction_prompt"]["available_reactions"][0]["damage_prevented"] == 4

        ai_update = await _wait_for_event(guest_ws, "combat_update", timeout=2, start_index=before_ai_count)
        assert ai_update["combat"]["entities"][guest_char.id]["hp_current"] == 2

        before_reaction_count = len(host_ws.sent)
        reaction = await client.post(
            f"/game/combat/{sid}/reaction",
            headers=_h(guest["token"]),
            json={
                "reaction_type": "shield",
                "target_id": enemy["id"],
                "character_id": guest_char.id,
            },
        )
        assert reaction.status_code == 200, reaction.text
        reaction_body = reaction.json()
        assert reaction_body["reaction_effect"]["damage_prevented"] == 4
        assert reaction_body["reaction_effect"]["hp_restored"] == 4
        assert reaction_body["dice_result"]["type"] == "reaction"
        assert reaction_body["dice_result"]["reaction_type"] == "shield"
        assert reaction_body["dice_result"]["damage_prevented"] == 4
        assert reaction_body["dice_result"]["hp_restored"] == 4
        assert reaction_body["special_action"] == reaction_body["dice_result"]

        await db_session.refresh(guest_char)
        assert guest_char.hp_current == 6
        assert guest_char.spell_slots["1st"] == 0

        reaction_update = await _wait_for_event(host_ws, "combat_update", timeout=2, start_index=before_reaction_count)
        assert reaction_update["actor_id"] == guest_char.id
        assert reaction_update["action"] == "reaction"
        assert reaction_update["reaction_type"] == "shield"
        assert reaction_update["reaction_effect"] == reaction_body["reaction_effect"]
        assert reaction_update["target_state"] == reaction_body["target_state"]
        assert reaction_update["actor_state"] == reaction_body["target_state"]
        assert reaction_update["remaining_slots"] == reaction_body["remaining_slots"]
        assert reaction_update["dice_result"] == reaction_body["dice_result"]
        assert reaction_update["special_action"] == reaction_body["special_action"]
        assert "turn_state" not in reaction_update
        assert reaction_update["combat"]["entities"][guest_char.id]["hp_current"] == 6
        assert reaction_update["combat"]["turn_states"][guest_char.id]["reaction_used"] is True
        assert "pending_attack_reaction" not in reaction_update["combat"]["turn_states"][guest_char.id]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_guest_absorb_elements_restores_damage_and_broadcasts_state(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack
    import api.combat.reactions as reactions
    from services.combat_service import AttackResult
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A burning ward flares to life.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Flame Sentry",
                            "hp": 12,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "2d6",
                            "damage_type": "fire",
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    async def fake_get_ai_decision(**kwargs):
        return {"action_type": "attack", "target_id": guest_char.id, "reason": "test absorb elements reaction"}

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 20,
                "target_ac": 12,
            },
            damage=9,
            damage_roll={"formula": "2d6", "rolls": [4, 5], "total": 9},
            narration="hit",
        )

    async def fake_narrate_batch(actions):
        return ["" for _ in actions]

    async def fake_narrate_action(**kwargs):
        return ""

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(reactions, "narrate_action", fake_narrate_action)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_guest_absorb",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    guest_char = room_data["guest_char"]

    guest_char.char_class = "Wizard"
    guest_char.known_spells = ["吸收元素"]
    guest_char.spell_slots = {"1st": 1}
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I start the fight.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        enemy_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == enemy["id"]
        )

        from models import CombatState, Session
        from sqlalchemy import select
        from sqlalchemy.orm.attributes import flag_modified

        session_row = await db_session.get(Session, sid)
        state = dict(session_row.game_state or {})
        enemy_state = state["enemies"][0]
        enemy_state["derived"] = {
            **(enemy_state.get("derived") or {}),
            "damage_type": "fire",
        }
        state["enemies"] = [enemy_state]
        session_row.game_state = state
        flag_modified(session_row, "game_state")

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = enemy_turn_index
        positions = dict(combat_row.entity_positions or {})
        positions[enemy["id"]] = {"x": 5, "y": 5}
        positions[guest_char.id] = {"x": 6, "y": 5}
        combat_row.entity_positions = positions
        await db_session.commit()

        before_ai_count = len(guest_ws.sent)
        ai_result = await client.post(f"/game/combat/{sid}/ai-turn", headers=_h(host["token"]))
        assert ai_result.status_code == 200, ai_result.text
        ai_body = ai_result.json()
        assert ai_body["target_id"] == guest_char.id
        assert ai_body["target_new_hp"] == 0
        assert ai_body["reaction_prompt"]["reactor_character_id"] == guest_char.id
        absorb = next(
            reaction
            for reaction in ai_body["reaction_prompt"]["available_reactions"]
            if reaction["type"] == "absorb_elements"
        )
        assert absorb["damage_type"] == "fire"
        assert absorb["damage_prevented"] == 5

        ai_update = await _wait_for_event(guest_ws, "combat_update", timeout=2, start_index=before_ai_count)
        assert ai_update["reaction_prompt"]["reactor_character_id"] == guest_char.id

        before_reaction_count = len(host_ws.sent)
        reaction = await client.post(
            f"/game/combat/{sid}/reaction",
            headers=_h(guest["token"]),
            json={
                "reaction_type": "absorb_elements",
                "target_id": enemy["id"],
                "character_id": guest_char.id,
            },
        )
        assert reaction.status_code == 200, reaction.text
        reaction_body = reaction.json()
        assert reaction_body["reaction_effect"]["damage_prevented"] == 5
        assert reaction_body["reaction_effect"]["hp_restored"] == 5
        assert reaction_body["dice_result"]["type"] == "reaction"
        assert reaction_body["dice_result"]["reaction_type"] == "absorb_elements"
        assert reaction_body["dice_result"]["damage_prevented"] == 5
        assert reaction_body["dice_result"]["hp_restored"] == 5
        assert reaction_body["special_action"] == reaction_body["dice_result"]

        await db_session.refresh(guest_char)
        assert guest_char.hp_current == 5
        assert guest_char.spell_slots["1st"] == 0
        assert guest_char.class_resources["absorb_elements"]["damage_type"] == "fire"

        reaction_update = await _wait_for_event(host_ws, "combat_update", timeout=2, start_index=before_reaction_count)
        assert reaction_update["actor_id"] == guest_char.id
        assert reaction_update["action"] == "reaction"
        assert reaction_update["reaction_type"] == "absorb_elements"
        assert reaction_update["reaction_effect"] == reaction_body["reaction_effect"]
        assert reaction_update["target_state"] == reaction_body["target_state"]
        assert reaction_update["actor_state"] == reaction_body["target_state"]
        assert reaction_update["remaining_slots"] == reaction_body["remaining_slots"]
        assert reaction_update["dice_result"] == reaction_body["dice_result"]
        assert reaction_update["special_action"] == reaction_body["special_action"]
        assert "turn_state" not in reaction_update
        assert reaction_update["combat"]["entities"][guest_char.id]["hp_current"] == 5
        assert reaction_update["combat"]["entities"][guest_char.id]["conditions"] == ["fire_resistance"]
        assert reaction_update["combat"]["turn_states"][guest_char.id]["reaction_used"] is True
        assert "pending_attack_reaction" not in reaction_update["combat"]["turn_states"][guest_char.id]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_counterspell_prompt_broadcasts_to_guest_reactor_and_cancels_spell(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Counterspell prompts should identify the reacting character, not just the spell target."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    import services.ai_combat_agent as ai_agent
    import api.combat.reactions as reactions
    from models import CombatState, Session
    from services.ws_manager import ws_manager
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A robed sentry begins the fight.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [
                        {
                            "name": "Enemy Mage",
                            "hp": 12,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage_dice": "1d6+1",
                        }
                    ],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "spell",
            "target_id": host_char.id,
            "action_name": "魔法飞弹",
            "reason": "test multiplayer counterspell",
        }

    async def fake_narrate_action(**kwargs):
        return ""

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(reactions, "narrate_action", fake_narrate_action)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_counterspell",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]

    guest_char.char_class = "Wizard"
    guest_char.level = 5
    guest_char.known_spells = ["Counterspell"]
    guest_char.spell_slots = {"3rd": 1}
    guest_char.derived = {
        **(guest_char.derived or {}),
        "spell_ability": "int",
        "ability_modifiers": {
            **(guest_char.derived or {}).get("ability_modifiers", {}),
            "int": 3,
        },
    }
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I start the fight.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
        enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])
        enemy_turn_index = next(
            index
            for index, turn in enumerate(combat_payload["turn_order"])
            if turn["character_id"] == enemy["id"]
        )

        session_row = await db_session.get(Session, sid)
        state = dict(session_row.game_state or {})
        enemy_state = state["enemies"][0]
        enemy_state["known_spells"] = ["魔法飞弹"]
        enemy_state["spell_slots"] = {"1st": 1}
        enemy_state["derived"] = {
            **(enemy_state.get("derived") or {}),
            "spell_ability": "int",
            "ability_modifiers": {"int": 3, "dex": 1},
            "spell_save_dc": 13,
        }
        session_row.game_state = state
        flag_modified(session_row, "game_state")

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        combat_row.current_turn_index = enemy_turn_index
        positions = dict(combat_row.entity_positions or {})
        positions[enemy["id"]] = {"x": 5, "y": 5}
        positions[host_char.id] = {"x": 6, "y": 5}
        positions[guest_char.id] = {"x": 4, "y": 5}
        combat_row.entity_positions = positions
        await db_session.commit()

        before_guest_ai_count = len(guest_ws.sent)
        before_host_ai_count = len(host_ws.sent)
        ai_result = await client.post(f"/game/combat/{sid}/ai-turn", headers=_h(host["token"]))
        assert ai_result.status_code == 200, ai_result.text
        ai_body = ai_result.json()
        assert ai_body["target_id"] == host_char.id
        assert ai_body["player_can_react"] is True
        assert ai_body["reaction_prompt"]["trigger"] == "spell_cast"
        assert ai_body["reaction_prompt"]["reactor_character_id"] == guest_char.id
        assert ai_body["reaction_prompt"]["spell_target_id"] == host_char.id
        assert ai_body["reaction_prompt"]["range"]["distance_ft"] == 5
        assert ai_body["reaction_prompt"]["range"]["range_ft"] == 60
        assert ai_body["reaction_prompt"]["options"][0]["type"] == "counterspell"

        guest_ai_update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=before_guest_ai_count,
        )
        host_ai_update = await _wait_for_event(
            host_ws,
            "combat_update",
            timeout=2,
            start_index=before_host_ai_count,
        )
        assert guest_ai_update["player_can_react"] is True
        assert guest_ai_update["reaction_prompt"]["reactor_character_id"] == guest_char.id
        assert guest_ai_update["reaction_prompt"]["spell_target_id"] == host_char.id
        assert guest_ai_update["reaction_prompt"]["range"]["distance_ft"] == 5
        assert guest_ai_update["reaction_prompt"]["range"]["range_ft"] == 60
        assert guest_ai_update["current_entity_id"] == enemy["id"]

        assert host_ai_update["player_can_react"] is False
        assert host_ai_update["reaction_prompt"] is None
        assert host_ai_update["current_entity_id"] == enemy["id"]
        assert "pending_spell_reaction" not in host_ai_update["combat"]["turn_states"][guest_char.id]
        assert guest_ai_update["combat"]["turn_states"][guest_char.id]["pending_spell_reaction"]["trigger"] == "spell_cast"

        await db_session.refresh(combat_row)
        assert combat_row.turn_states[guest_char.id]["pending_spell_reaction"]["spell_name"] == "魔法飞弹"

        before_reaction_count = len(host_ws.sent)
        reaction = await client.post(
            f"/game/combat/{sid}/reaction",
            headers=_h(guest["token"]),
            json={
                "reaction_type": "counterspell",
                "target_id": enemy["id"],
                "character_id": guest_char.id,
            },
        )
        assert reaction.status_code == 200, reaction.text
        reaction_body = reaction.json()
        assert reaction_body["reaction_effect"]["spell_cancelled"] is True
        assert reaction_body["reaction_effect"]["countered_spell"] == "魔法飞弹"
        assert reaction_body["reaction_effect"]["slot_used"] == "3rd"
        assert reaction_body["dice_result"]["type"] == "reaction"
        assert reaction_body["dice_result"]["reaction_type"] == "counterspell"
        assert reaction_body["dice_result"]["spell_cancelled"] is True
        assert reaction_body["dice_result"]["slot_used"] == "3rd"
        assert reaction_body["special_action"] == reaction_body["dice_result"]
        assert reaction_body["turn_state"]["reaction_used"] is True

        await db_session.refresh(guest_char)
        await db_session.refresh(session_row)
        await db_session.refresh(combat_row)
        assert guest_char.spell_slots["3rd"] == 0
        assert session_row.game_state["enemies"][0]["spell_slots"]["1st"] == 0
        assert combat_row.current_turn_index != enemy_turn_index
        assert "pending_spell_reaction" not in combat_row.turn_states[guest_char.id]

        reaction_update = await _wait_for_event(host_ws, "combat_update", timeout=2, start_index=before_reaction_count)
        assert reaction_update["actor_id"] == guest_char.id
        assert reaction_update["action"] == "reaction"
        assert reaction_update["reaction_type"] == "counterspell"
        assert reaction_update["reaction_effect"] == reaction_body["reaction_effect"]
        assert reaction_update["target_state"] == reaction_body["target_state"]
        assert reaction_update["actor_state"] == reaction_body["target_state"]
        assert reaction_update["remaining_slots"] == reaction_body["remaining_slots"]
        assert reaction_update["dice_result"] == reaction_body["dice_result"]
        assert reaction_update["special_action"] == reaction_body["special_action"]
        assert "turn_state" not in reaction_update
        assert "pending_spell_reaction" not in reaction_update["combat"]["turn_states"][guest_char.id]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_death_save_broadcasts_character_state(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Death saves should refresh every combat client in the room."""
    import json
    import api.ws as ws_api
    import services.langgraph_client as lc
    from services.ws_manager import ws_manager

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A sentry presses the attack.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [{"name": "Clockwork Sentry", "hp": 9, "ac": 13}],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="ws_death_save",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    guest_char = room_data["guest_char"]

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I start the fight.",
        })
        assert start_response.status_code == 200, start_response.text
        await _wait_for_event(guest_ws, "dm_responded", timeout=2)

        from models import CombatState
        from sqlalchemy import select

        combat_row = (
            await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
        ).scalars().first()
        guest_turn_index = next(
            index
            for index, turn in enumerate(combat_row.turn_order)
            if turn["character_id"] == guest_char.id
        )
        combat_row.current_turn_index = guest_turn_index
        guest_char.hp_current = 0
        guest_char.death_saves = {"successes": 0, "failures": 0, "stable": False}
        await db_session.commit()

        before_count = len(host_ws.sent)
        response = await client.post(
            f"/game/combat/{sid}/death-save",
            headers=_h(guest["token"]),
            json={"character_id": guest_char.id, "d20_value": 20},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["type"] == "death_save"
        assert body["outcome"] == "revive"
        assert body["target_id"] == guest_char.id
        assert body["target_name"] == guest_char.name
        assert body["target_state"]["target_id"] == guest_char.id
        assert body["target_state"]["target_name"] == guest_char.name
        assert body["target_state"]["hp_current"] == 1
        assert body["target_state"]["life_state"] == "alive"
        assert body["dice_result"]["type"] == "death_save"
        assert body["dice_result"]["target_state"] == body["target_state"]
        assert body["special_action"] == body["dice_result"]

        update = await _wait_for_event(
            host_ws,
            "combat_update",
            timeout=2,
            start_index=before_count,
            predicate=lambda event: event.get("action") == "death_save",
        )
        assert update["actor_id"] == guest_char.id
        assert update["actor_name"] == guest_char.name
        assert update["action"] == "death_save"
        assert update["target_id"] == guest_char.id
        assert update["target_name"] == guest_char.name
        assert update["target_state"] == body["target_state"]
        assert update["death_save"] == body["dice_result"]
        assert update["dice_result"] == body["dice_result"]
        assert update["special_action"] == body["special_action"]
        assert "turn_state" not in update
        assert update["combat"]["entities"][guest_char.id]["hp_current"] == 1
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_end_turn_rejects_ai_controlled_current_turn(
    client,
    db_session,
    sample_module,
):
    """Players must not skip an enemy or AI companion turn through /end-turn."""
    import uuid as _uuid
    from models import CombatState, Session
    from sqlalchemy.orm.attributes import flag_modified

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_end_turn_ai_guard",
    )
    host = room_data["host"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]
    enemy_id = "ai-guard"

    session = await db_session.get(Session, sid)
    session.combat_active = True
    state = dict(session.game_state or {})
    state["enemies"] = [{
        "id": enemy_id,
        "name": "AI Guard",
        "hp_current": 9,
        "max_hp": 9,
        "ac": 13,
        "conditions": [],
        "derived": {"hp_max": 9, "ac": 13, "ability_modifiers": {"dex": 1}},
    }]
    session.game_state = state
    flag_modified(session, "game_state")

    combat = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={
            enemy_id: {"x": 6, "y": 5},
            host_char.id: {"x": 5, "y": 5},
            guest_char.id: {"x": 4, "y": 5},
        },
        turn_order=[
            {"character_id": enemy_id, "name": "AI Guard", "initiative": 18, "is_player": False, "is_enemy": True},
            {"character_id": host_char.id, "name": host_char.name, "initiative": 14, "is_player": True, "is_enemy": False},
            {"character_id": guest_char.id, "name": guest_char.name, "initiative": 12, "is_player": True, "is_enemy": False},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={},
    )
    db_session.add(combat)
    await db_session.commit()
    await db_session.refresh(combat)

    response = await client.post(f"/game/combat/{sid}/end-turn", headers=_h(host["token"]))

    assert response.status_code == 400, response.text
    assert "AI-controlled" in response.text
    await db_session.refresh(combat)
    assert combat.current_turn_index == 0
    assert combat.round_number == 1


async def test_multiplayer_manual_end_combat_is_ai_driver_only_and_broadcasts(
    client,
    db_session,
    sample_module,
):
    """The legacy manual combat-end switch is restricted to the AI combat driver."""
    import uuid as _uuid
    from models import CombatState, Session
    from services.combat_turn_state_service import DEFAULT_TURN_STATE
    from services.ws_manager import ws_manager
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_manual_end_guard",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]
    enemy_id = "manual-end-guard"

    session = await db_session.get(Session, sid)
    session.combat_active = True
    state = dict(session.game_state or {})
    state["enemies"] = [{
        "id": enemy_id,
        "name": "Manual End Guard",
        "hp_current": 12,
        "hp_max": 12,
        "ac": 13,
        "conditions": [],
        "condition_durations": {},
        "derived": {"hp_max": 12, "ac": 13, "ability_modifiers": {"dex": 1}},
    }]
    session.game_state = state
    flag_modified(session, "game_state")

    combat = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={
            host_char.id: {"x": 5, "y": 5},
            guest_char.id: {"x": 7, "y": 5},
            enemy_id: {"x": 6, "y": 5},
        },
        turn_order=[
            {"character_id": host_char.id, "name": host_char.name, "initiative": 18, "is_player": True, "is_enemy": False},
            {"character_id": guest_char.id, "name": guest_char.name, "initiative": 14, "is_player": True, "is_enemy": False},
            {"character_id": enemy_id, "name": "Manual End Guard", "initiative": 10, "is_player": False, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={
            host_char.id: dict(DEFAULT_TURN_STATE),
            guest_char.id: dict(DEFAULT_TURN_STATE),
            enemy_id: dict(DEFAULT_TURN_STATE),
        },
    )
    db_session.add(combat)
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    await ws_manager.connect(sid, host["user_id"], host_ws)
    await ws_manager.connect(sid, guest["user_id"], guest_ws)

    try:
        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        guest_response = await client.post(
            f"/game/combat/{sid}/end",
            headers=_h(guest["token"]),
        )
        assert guest_response.status_code == 403, guest_response.text
        await db_session.refresh(session)
        await db_session.refresh(combat)
        assert session.combat_active is True
        still_exists = await db_session.execute(
            select(CombatState).where(CombatState.id == combat.id)
        )
        assert still_exists.scalar_one_or_none() is not None
        _assert_no_event_types(host_ws, host_before, {"combat_update"})
        _assert_no_event_types(guest_ws, guest_before, {"combat_update"})

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        host_response = await client.post(
            f"/game/combat/{sid}/end",
            headers=_h(host["token"]),
        )
        assert host_response.status_code == 200, host_response.text

        host_update = await _wait_for_event(host_ws, "combat_update", timeout=2, start_index=host_before)
        guest_update = await _wait_for_event(guest_ws, "combat_update", timeout=2, start_index=guest_before)
        for update in (host_update, guest_update):
            assert update["combat"] is None
            assert update["combat_over"] is True
            assert update["outcome"] == "ended"

        await db_session.refresh(session)
        assert session.combat_active is False
        deleted = await db_session.execute(
            select(CombatState).where(CombatState.id == combat.id)
        )
        assert deleted.scalar_one_or_none() is None
    finally:
        await ws_manager.disconnect(host_ws)
        await ws_manager.disconnect(guest_ws)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_ready_action_declaration_is_private_to_actor_view(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Readied-action trigger details are private until the action actually fires."""
    import uuid as _uuid
    import api.ws as ws_api
    from models import CombatState, Session
    from services.combat_turn_state_service import DEFAULT_TURN_STATE
    from services.ws_manager import ws_manager
    from sqlalchemy.orm.attributes import flag_modified

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_ready_privacy",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]
    secret_condition = "When the guest crosses the hidden sigil, strike."

    session = await db_session.get(Session, sid)
    session.combat_active = True
    state = dict(session.game_state or {})
    state["enemies"] = [{
        "id": "ready-privacy-decoy",
        "name": "Ready Privacy Decoy",
        "hp_current": 9,
        "hp_max": 9,
        "ac": 13,
        "conditions": [],
        "derived": {"hp_max": 9, "ac": 13, "ability_modifiers": {"dex": 1}},
    }]
    session.game_state = state
    flag_modified(session, "game_state")

    combat = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={
            host_char.id: {"x": 5, "y": 5},
            guest_char.id: {"x": 8, "y": 5},
            "ready-privacy-decoy": {"x": 10, "y": 5},
        },
        turn_order=[
            {"character_id": host_char.id, "name": host_char.name, "initiative": 14, "is_player": True, "is_enemy": False},
            {"character_id": guest_char.id, "name": guest_char.name, "initiative": 12, "is_player": True, "is_enemy": False},
            {"character_id": "ready-privacy-decoy", "name": "Ready Privacy Decoy", "initiative": 8, "is_player": False, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={
            host_char.id: dict(DEFAULT_TURN_STATE),
            guest_char.id: dict(DEFAULT_TURN_STATE),
        },
    )
    db_session.add(combat)
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")
        await _wait_for_event(guest_ws, "member_online")
        await _wait_for_event(host_ws, "room_state_updated")
        await _wait_for_event(guest_ws, "room_state_updated")

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        response = await client.post(
            f"/game/combat/{sid}/ready-action",
            headers=_h(host["token"]),
            json={
                "entity_id": host_char.id,
                "action_type": "attack",
                "trigger": "target_moves",
                "trigger_match": "leaves_reach",
                "target_id": guest_char.id,
                "condition_text": secret_condition,
                "expected_turn_token": f"1:0:{host_char.id}",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ready_action"]["condition_text"] == secret_condition
        assert body["dice_result"]["type"] == "ready_action_declared"
        assert body["dice_result"]["ready_action"] == body["ready_action"]
        assert body["special_action"] == body["dice_result"]

        host_update = await _wait_for_event(host_ws, "combat_update", timeout=2, start_index=host_before)
        guest_update = await _wait_for_event(guest_ws, "combat_update", timeout=2, start_index=guest_before)

        assert host_update["action"] == "ready_action"
        assert host_update["ready_action"] == body["ready_action"]
        assert host_update["dice_result"] == body["dice_result"]
        assert host_update["special_action"] == body["special_action"]
        assert "turn_state" not in host_update
        host_ready = host_update["combat"]["turn_states"][host_char.id]["ready_action"]
        guest_ready = guest_update["combat"]["turn_states"][host_char.id]["ready_action"]
        assert host_ready["condition_text"] == secret_condition
        assert host_ready["target_id"] == guest_char.id
        assert host_ready["trigger_match"] == "leaves_reach"

        assert guest_update["action"] == "ready_action"
        assert guest_update["ready_action"] == {
            "type": "ready_action",
            "redacted": True,
            "visibility": "other_character",
            "actor_id": host_char.id,
            "actor_name": host_char.name,
        }
        assert guest_update["dice_result"] == {
            "type": "ready_action_declared",
            "ready_action": guest_update["ready_action"],
        }
        assert guest_update["special_action"] == guest_update["dice_result"]
        assert guest_update["remaining_slots"] is None
        assert guest_update["actor_state"] is None
        assert guest_update["caster_state"] is None
        assert guest_update["concentration_started"] is False
        assert guest_update["concentration_spell_name"] is None
        assert guest_update["concentration_effect_updates"] == []
        assert "turn_state" not in guest_update
        assert guest_ready == {
            "type": "ready_action",
            "redacted": True,
            "visibility": "other_character",
            "actor_id": host_char.id,
            "actor_name": host_char.name,
        }
        assert secret_condition not in str(guest_update)
        assert guest_update["narration"] == f"{host_char.name} readies an action."

        guest_refresh = await client.get(f"/game/combat/{sid}", headers=_h(guest["token"]))
        assert guest_refresh.status_code == 200, guest_refresh.text
        refreshed_ready = guest_refresh.json()["turn_states"][host_char.id]["ready_action"]
        assert refreshed_ready["redacted"] is True
        assert "condition_text" not in refreshed_ready
        assert "target_id" not in refreshed_ready
        assert secret_condition not in str(guest_refresh.json())

        guest_session = await client.get(f"/game/sessions/{sid}", headers=_h(guest["token"]))
        assert guest_session.status_code == 200, guest_session.text
        guest_session_body = guest_session.json()
        assert secret_condition not in str(guest_session_body)
        ready_logs = [
            log for log in guest_session_body["logs"]
            if (log.get("dice_result") or {}).get("type") == "ready_action_declared"
        ]
        assert ready_logs
        assert ready_logs[-1]["content"] == f"{host_char.name} readies an action."
        assert ready_logs[-1]["dice_result"]["ready_action"]["redacted"] is True
        assert "condition_text" not in ready_logs[-1]["dice_result"]["ready_action"]
        assert "target_id" not in ready_logs[-1]["dice_result"]["ready_action"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_end_concentration_broadcasts_structured_payload_and_redacts_ready_failure(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Ending a readied spell concentration should broadcast structured details without leaking them."""
    import uuid as _uuid
    import api.ws as ws_api
    from models import CombatState, Session
    from services.combat_ready_action_service import build_ready_spell_payload
    from services.combat_ready_spell_concentration_service import build_ready_spell_concentration_name
    from services.combat_turn_state_service import DEFAULT_TURN_STATE
    from services.ws_manager import ws_manager
    from sqlalchemy.orm.attributes import flag_modified

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_end_concentration",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]
    spell_name = "Magic Missile"
    hold_name = build_ready_spell_concentration_name(spell_name)

    session = await db_session.get(Session, sid)
    session.combat_active = True
    host_char.concentration = hold_name
    state = dict(session.game_state or {})
    state["enemies"] = [{
        "id": "concentration-decoy",
        "name": "Concentration Decoy",
        "hp_current": 9,
        "hp_max": 9,
        "ac": 13,
        "conditions": [],
        "derived": {"hp_max": 9, "ac": 13, "ability_modifiers": {"dex": 1}},
    }]
    session.game_state = state
    flag_modified(session, "game_state")

    combat = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={
            host_char.id: {"x": 5, "y": 5},
            guest_char.id: {"x": 8, "y": 5},
            "concentration-decoy": {"x": 10, "y": 5},
        },
        turn_order=[
            {"character_id": host_char.id, "name": host_char.name, "initiative": 14, "is_player": True, "is_enemy": False},
            {"character_id": guest_char.id, "name": guest_char.name, "initiative": 12, "is_player": True, "is_enemy": False},
            {"character_id": "concentration-decoy", "name": "Concentration Decoy", "initiative": 8, "is_player": False, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={
            host_char.id: {
                **dict(DEFAULT_TURN_STATE),
                "action_used": True,
                "ready_action": build_ready_spell_payload(
                    actor_id=host_char.id,
                    actor_name=host_char.name,
                    target_id="concentration-decoy",
                    target_name="Concentration Decoy",
                    spell_name=spell_name,
                    spell_level=1,
                    condition_text="When the decoy crosses the hidden glyph, fire.",
                    slot_already_consumed=True,
                    slot_key="1st",
                    slots_remaining=0,
                    concentration_spell_name=hold_name,
                ),
            },
            guest_char.id: dict(DEFAULT_TURN_STATE),
        },
    )
    db_session.add(combat)
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")
        await _wait_for_event(guest_ws, "member_online")
        await _wait_for_event(host_ws, "room_state_updated")
        await _wait_for_event(guest_ws, "room_state_updated")

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        response = await client.post(
            f"/game/combat/{sid}/concentration/end",
            headers=_h(host["token"]),
            json={"character_id": host_char.id},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["action"] == "concentration_end"
        assert body["concentration_ended"] is True
        assert body["concentration_spell_name"] == hold_name
        assert body["ready_action_failed"]["spell_name"] == spell_name
        assert body["dice_result"]["type"] == "concentration_end"
        assert body["dice_result"]["ready_action_failed"] == body["ready_action_failed"]
        assert body["special_action"] == body["dice_result"]

        host_update = await _wait_for_event(
            host_ws,
            "combat_update",
            timeout=2,
            start_index=host_before,
            predicate=lambda event: event.get("action") == "concentration_end",
        )
        assert host_update["actor_id"] == host_char.id
        assert host_update["actor_name"] == host_char.name
        assert host_update["narration"] == body["narration"]
        assert host_update["dice_result"] == body["dice_result"]
        assert host_update["special_action"] == body["special_action"]
        assert host_update["ready_action_failed"] == body["ready_action_failed"]
        assert "turn_state" not in host_update

        guest_update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=guest_before,
            predicate=lambda event: event.get("action") == "concentration_end",
        )
        expected_redacted = {
            "type": "ready_action_failed",
            "redacted": True,
            "visibility": "other_character",
            "actor_id": host_char.id,
            "actor_name": host_char.name,
        }
        assert guest_update["narration"] == f"{host_char.name} ends concentration."
        assert guest_update["ready_action_failed"] == expected_redacted
        assert guest_update["dice_result"]["type"] == "concentration_end"
        assert guest_update["dice_result"]["ready_action_failed"] == expected_redacted
        assert guest_update["dice_result"]["concentration_spell_name"] is None
        assert guest_update["special_action"] == guest_update["dice_result"]
        assert guest_update["concentration_spell_name"] is None
        guest_failed_state = guest_update["combat"]["turn_states"][host_char.id]["ready_action_failed"]
        assert guest_failed_state == expected_redacted
        assert spell_name not in str(guest_update)
        assert hold_name not in str(guest_update)

        guest_session = await client.get(f"/game/sessions/{sid}", headers=_h(guest["token"]))
        assert guest_session.status_code == 200, guest_session.text
        concentration_logs = [
            log for log in guest_session.json()["logs"]
            if (log.get("dice_result") or {}).get("type") == "concentration_end"
        ]
        assert concentration_logs
        public_log = concentration_logs[-1]
        assert public_log["content"] == f"{host_char.name} ends concentration."
        assert public_log["dice_result"]["ready_action_failed"] == expected_redacted
        assert spell_name not in str(public_log)
        assert hold_name not in str(public_log)
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_smite_window_is_owner_bound_and_private(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """A pending smite window belongs to one actor and is hidden from other players."""
    import uuid as _uuid
    import api.ws as ws_api
    from api.combat import smites
    from models import CombatState, Session
    from services.combat_turn_state_service import DEFAULT_TURN_STATE
    from services.ws_manager import ws_manager
    from sqlalchemy.orm.attributes import flag_modified

    async def fake_narrate_action(**_kwargs):
        return ""

    monkeypatch.setattr(smites, "narrate_action", fake_narrate_action)
    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_smite_privacy",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]
    enemy_id = "smite-window-ogre"

    host_char.char_class = "Paladin"
    host_char.spell_slots = {"1st": 1}
    guest_char.char_class = "Wizard"
    guest_char.spell_slots = {"1st": 1}

    session = await db_session.get(Session, sid)
    session.combat_active = True
    state = dict(session.game_state or {})
    state["enemies"] = [{
        "id": enemy_id,
        "name": "Smite Window Ogre",
        "hp_current": 20,
        "hp_max": 20,
        "ac": 12,
        "conditions": [],
        "condition_durations": {},
        "derived": {
            "hp_max": 20,
            "ac": 12,
            "ability_modifiers": {"str": 3, "dex": 0, "con": 2},
        },
    }]
    session.game_state = state
    flag_modified(session, "game_state")

    host_state = {
        **dict(DEFAULT_TURN_STATE),
        "pending_smite": {
            "target_id": enemy_id,
            "target_name": "Smite Window Ogre",
            "is_crit": False,
            "source": "test",
            "used": False,
        },
    }
    combat = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={
            host_char.id: {"x": 5, "y": 5},
            guest_char.id: {"x": 8, "y": 5},
            enemy_id: {"x": 6, "y": 5},
        },
        turn_order=[
            {"character_id": host_char.id, "name": host_char.name, "initiative": 18, "is_player": True, "is_enemy": False},
            {"character_id": guest_char.id, "name": guest_char.name, "initiative": 14, "is_player": True, "is_enemy": False},
            {"character_id": enemy_id, "name": "Smite Window Ogre", "initiative": 10, "is_player": False, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={
            host_char.id: host_state,
            guest_char.id: dict(DEFAULT_TURN_STATE),
            enemy_id: dict(DEFAULT_TURN_STATE),
        },
    )
    db_session.add(combat)
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")
        await _wait_for_event(guest_ws, "member_online")
        await _wait_for_event(host_ws, "room_state_updated")
        await _wait_for_event(guest_ws, "room_state_updated")

        host_refresh = await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))
        guest_refresh = await client.get(f"/game/combat/{sid}", headers=_h(guest["token"]))
        assert host_refresh.status_code == 200, host_refresh.text
        assert guest_refresh.status_code == 200, guest_refresh.text
        assert host_refresh.json()["turn_states"][host_char.id]["pending_smite"]["target_id"] == enemy_id
        assert "pending_smite" not in guest_refresh.json()["turn_states"][host_char.id]

        guest_attempt = await client.post(
            f"/game/combat/{sid}/smite",
            headers=_h(guest["token"]),
            json={"slot_level": 1, "target_id": enemy_id, "is_crit": False, "damage_values": [8, 8]},
        )
        assert guest_attempt.status_code == 400, guest_attempt.text
        await db_session.refresh(host_char)
        await db_session.refresh(guest_char)
        await db_session.refresh(session)
        await db_session.refresh(combat)
        assert host_char.spell_slots["1st"] == 1
        assert guest_char.spell_slots["1st"] == 1
        assert session.game_state["enemies"][0]["hp_current"] == 20
        assert "pending_smite" in combat.turn_states[host_char.id]

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        host_smite = await client.post(
            f"/game/combat/{sid}/smite",
            headers=_h(host["token"]),
            json={"slot_level": 1, "target_id": enemy_id, "is_crit": False, "damage_values": [2, 2]},
        )
        assert host_smite.status_code == 200, host_smite.text
        body = host_smite.json()
        assert body["target_new_hp"] == 16
        assert body["damage"] == 4
        assert body["dice_result"]["type"] == "divine_smite"
        assert body["dice_result"]["target_state"] == body["target_state"]
        assert body["dice_result"]["remaining_slots"] == body["remaining_slots"]

        host_update = await _wait_for_event(host_ws, "combat_update", timeout=2, start_index=host_before)
        guest_update = await _wait_for_event(guest_ws, "combat_update", timeout=2, start_index=guest_before)
        assert guest_update["actor_id"] == host_char.id
        assert guest_update["actor_name"] == host_char.name
        assert guest_update["action"] == "divine_smite"
        assert guest_update["narration"] == body["narration"]
        assert guest_update["target_id"] == body["target_id"]
        assert guest_update["target_name"] == body["target_name"]
        assert guest_update["target_new_hp"] == body["target_new_hp"]
        assert guest_update["target_state"] == body["target_state"]
        assert guest_update["damage"] == body["damage"]
        assert guest_update["total_damage"] == body["total_damage"]
        assert guest_update["damage_roll"] == body["damage_roll"]
        assert guest_update["damage_type"] == body["damage_type"]
        assert guest_update["dice_result"] == body["dice_result"]
        assert guest_update["special_action"] == body["special_action"]
        assert guest_update["remaining_slots"] == body["remaining_slots"]
        assert "turn_state" not in guest_update
        assert "pending_smite" not in host_update["combat"]["turn_states"][host_char.id]
        assert "pending_smite" not in guest_update["combat"]["turn_states"][host_char.id]
        assert guest_update["combat"]["entities"][enemy_id]["hp_current"] == 16

        await db_session.refresh(host_char)
        await db_session.refresh(combat)
        assert host_char.spell_slots["1st"] == 0
        assert "pending_smite" not in combat.turn_states[host_char.id]

        second_smite = await client.post(
            f"/game/combat/{sid}/smite",
            headers=_h(host["token"]),
            json={"slot_level": 1, "target_id": enemy_id, "is_crit": False, "damage_values": [1, 1]},
        )
        assert second_smite.status_code == 400, second_smite.text
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_manual_condition_edits_are_owner_or_ai_driver_only(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Manual condition endpoints cannot be used to mutate another player or enemy control."""
    import uuid as _uuid
    import api.ws as ws_api
    from models import CombatState, Session
    from services.combat_turn_state_service import DEFAULT_TURN_STATE
    from services.ws_manager import ws_manager
    from sqlalchemy.orm.attributes import flag_modified

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_condition_guard",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]
    enemy_id = "condition-guard-ogre"

    session = await db_session.get(Session, sid)
    session.combat_active = True
    state = dict(session.game_state or {})
    state["enemies"] = [{
        "id": enemy_id,
        "name": "Condition Guard Ogre",
        "hp_current": 22,
        "hp_max": 22,
        "ac": 12,
        "conditions": [],
        "condition_durations": {},
        "derived": {
            "hp_max": 22,
            "ac": 12,
            "attack_bonus": 5,
            "damage_dice": "1d8+3",
            "ability_modifiers": {"str": 3, "dex": 0, "con": 2},
        },
    }]
    session.game_state = state
    flag_modified(session, "game_state")

    combat = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={
            host_char.id: {"x": 5, "y": 5},
            guest_char.id: {"x": 8, "y": 5},
            enemy_id: {"x": 6, "y": 5},
        },
        turn_order=[
            {"character_id": host_char.id, "name": host_char.name, "initiative": 18, "is_player": True, "is_enemy": False},
            {"character_id": guest_char.id, "name": guest_char.name, "initiative": 14, "is_player": True, "is_enemy": False},
            {"character_id": enemy_id, "name": "Condition Guard Ogre", "initiative": 10, "is_player": False, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={
            host_char.id: dict(DEFAULT_TURN_STATE),
            guest_char.id: dict(DEFAULT_TURN_STATE),
            enemy_id: dict(DEFAULT_TURN_STATE),
        },
    )
    db_session.add(combat)
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")
        await _wait_for_event(guest_ws, "member_online")
        await _wait_for_event(host_ws, "room_state_updated")
        await _wait_for_event(guest_ws, "room_state_updated")

        guest_edits_host = await client.post(
            f"/game/combat/{sid}/condition/add",
            headers=_h(guest["token"]),
            json={"entity_id": host_char.id, "condition": "poisoned", "is_enemy": False},
        )
        assert guest_edits_host.status_code == 403, guest_edits_host.text

        host_edits_guest = await client.post(
            f"/game/combat/{sid}/condition/add",
            headers=_h(host["token"]),
            json={"entity_id": guest_char.id, "condition": "poisoned", "is_enemy": False},
        )
        assert host_edits_guest.status_code == 403, host_edits_guest.text

        guest_edits_enemy = await client.post(
            f"/game/combat/{sid}/condition/add",
            headers=_h(guest["token"]),
            json={"entity_id": enemy_id, "condition": "frightened", "is_enemy": True},
        )
        assert guest_edits_enemy.status_code == 403, guest_edits_enemy.text

        await db_session.refresh(host_char)
        await db_session.refresh(guest_char)
        await db_session.refresh(session)
        assert host_char.conditions in (None, [])
        assert guest_char.conditions in (None, [])
        assert session.game_state["enemies"][0]["conditions"] == []

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        guest_self = await client.post(
            f"/game/combat/{sid}/condition/add",
            headers=_h(guest["token"]),
            json={"entity_id": guest_char.id, "condition": "blessed", "is_enemy": False, "rounds": 2},
        )
        assert guest_self.status_code == 200, guest_self.text
        guest_self_body = guest_self.json()
        assert guest_self_body["conditions"] == ["blessed"]
        assert guest_self_body["action"] == "condition_add"
        assert guest_self_body["target_id"] == guest_char.id
        assert guest_self_body["target_name"] == guest_char.name
        assert guest_self_body["condition_action"] == "add"
        assert guest_self_body["condition_result"]["applied"] is True
        assert guest_self_body["condition_result"]["removed"] is False
        assert guest_self_body["target_state"]["conditions"] == ["blessed"]
        assert guest_self_body["dice_result"]["type"] == "condition_update"
        assert guest_self_body["special_action"] == guest_self_body["dice_result"]
        host_self_update = await _wait_for_event(
            host_ws,
            "combat_update",
            timeout=2,
            start_index=host_before,
            predicate=lambda event: event.get("action") == "condition_add" and event.get("target_id") == guest_char.id,
        )
        guest_self_update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=guest_before,
            predicate=lambda event: event.get("action") == "condition_add" and event.get("target_id") == guest_char.id,
        )
        assert host_self_update["actor_id"] == guest_char.id
        assert host_self_update["actor_name"] == guest_char.name
        assert host_self_update["narration"] == f"{guest_char.name} gains condition: blessed for 2 round(s)."
        assert host_self_update["target_id"] == guest_self_body["target_id"]
        assert host_self_update["target_name"] == guest_self_body["target_name"]
        assert host_self_update["target_state"] == guest_self_body["target_state"]
        assert host_self_update["condition"] == "blessed"
        assert host_self_update["condition_action"] == "add"
        assert host_self_update["condition_result"] == guest_self_body["condition_result"]
        assert host_self_update["dice_result"] == guest_self_body["dice_result"]
        assert host_self_update["special_action"] == guest_self_body["special_action"]
        assert "turn_state" not in host_self_update
        assert "blessed" in host_self_update["combat"]["entities"][guest_char.id]["conditions"]
        assert guest_self_update["condition_result"] == guest_self_body["condition_result"]
        assert guest_self_update["dice_result"] == guest_self_body["dice_result"]
        assert "turn_state" not in guest_self_update
        assert "blessed" in guest_self_update["combat"]["entities"][guest_char.id]["conditions"]

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        host_enemy = await client.post(
            f"/game/combat/{sid}/condition/add",
            headers=_h(host["token"]),
            json={"entity_id": enemy_id, "condition": "frightened", "is_enemy": True, "rounds": 1},
        )
        assert host_enemy.status_code == 200, host_enemy.text
        host_enemy_body = host_enemy.json()
        assert host_enemy_body["conditions"] == ["frightened"]
        assert host_enemy_body["action"] == "condition_add"
        assert host_enemy_body["target_id"] == enemy_id
        assert host_enemy_body["target_name"] == "Condition Guard Ogre"
        assert host_enemy_body["condition_result"]["applied"] is True
        assert host_enemy_body["target_state"]["is_enemy"] is True
        assert host_enemy_body["dice_result"]["type"] == "condition_update"
        assert host_enemy_body["special_action"] == host_enemy_body["dice_result"]
        host_enemy_update = await _wait_for_event(
            host_ws,
            "combat_update",
            timeout=2,
            start_index=host_before,
            predicate=lambda event: event.get("action") == "condition_add" and event.get("target_id") == enemy_id,
        )
        guest_enemy_update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=guest_before,
            predicate=lambda event: event.get("action") == "condition_add" and event.get("target_id") == enemy_id,
        )
        assert host_enemy_update["actor_id"] == enemy_id
        assert host_enemy_update["actor_name"] == "Condition Guard Ogre"
        assert host_enemy_update["narration"] == "Condition Guard Ogre gains condition: frightened for 1 round(s)."
        assert host_enemy_update["target_state"] == host_enemy_body["target_state"]
        assert host_enemy_update["condition_result"] == host_enemy_body["condition_result"]
        assert host_enemy_update["dice_result"] == host_enemy_body["dice_result"]
        assert host_enemy_update["special_action"] == host_enemy_body["special_action"]
        assert "turn_state" not in host_enemy_update
        assert "frightened" in host_enemy_update["combat"]["entities"][enemy_id]["conditions"]
        assert guest_enemy_update["condition_result"] == host_enemy_body["condition_result"]
        assert guest_enemy_update["dice_result"] == host_enemy_body["dice_result"]
        assert "turn_state" not in guest_enemy_update
        assert "frightened" in guest_enemy_update["combat"]["entities"][enemy_id]["conditions"]

        host_remove_guest = await client.post(
            f"/game/combat/{sid}/condition/remove",
            headers=_h(host["token"]),
            json={"entity_id": guest_char.id, "condition": "blessed", "is_enemy": False},
        )
        assert host_remove_guest.status_code == 403, host_remove_guest.text

        guest_remove_enemy = await client.post(
            f"/game/combat/{sid}/condition/remove",
            headers=_h(guest["token"]),
            json={"entity_id": enemy_id, "condition": "frightened", "is_enemy": True},
        )
        assert guest_remove_enemy.status_code == 403, guest_remove_enemy.text

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        host_remove_enemy = await client.post(
            f"/game/combat/{sid}/condition/remove",
            headers=_h(host["token"]),
            json={"entity_id": enemy_id, "condition": "frightened", "is_enemy": True},
        )
        assert host_remove_enemy.status_code == 200, host_remove_enemy.text
        host_remove_enemy_body = host_remove_enemy.json()
        assert host_remove_enemy_body["conditions"] == []
        assert host_remove_enemy_body["action"] == "condition_remove"
        assert host_remove_enemy_body["condition_action"] == "remove"
        assert host_remove_enemy_body["condition_result"]["removed"] is True
        assert host_remove_enemy_body["dice_result"]["type"] == "condition_update"
        host_remove_enemy_update = await _wait_for_event(
            host_ws,
            "combat_update",
            timeout=2,
            start_index=host_before,
            predicate=lambda event: event.get("action") == "condition_remove" and event.get("target_id") == enemy_id,
        )
        guest_remove_enemy_update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=guest_before,
            predicate=lambda event: event.get("action") == "condition_remove" and event.get("target_id") == enemy_id,
        )
        assert host_remove_enemy_update["target_state"] == host_remove_enemy_body["target_state"]
        assert host_remove_enemy_update["condition_result"] == host_remove_enemy_body["condition_result"]
        assert host_remove_enemy_update["dice_result"] == host_remove_enemy_body["dice_result"]
        assert host_remove_enemy_update["special_action"] == host_remove_enemy_body["special_action"]
        assert "turn_state" not in host_remove_enemy_update
        assert guest_remove_enemy_update["dice_result"] == host_remove_enemy_body["dice_result"]

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        guest_remove_self = await client.post(
            f"/game/combat/{sid}/condition/remove",
            headers=_h(guest["token"]),
            json={"entity_id": guest_char.id, "condition": "blessed", "is_enemy": False},
        )
        assert guest_remove_self.status_code == 200, guest_remove_self.text
        guest_remove_self_body = guest_remove_self.json()
        assert guest_remove_self_body["conditions"] == []
        assert guest_remove_self_body["action"] == "condition_remove"
        assert guest_remove_self_body["condition_action"] == "remove"
        assert guest_remove_self_body["condition_result"]["removed"] is True
        assert guest_remove_self_body["dice_result"]["type"] == "condition_update"
        host_remove_self_update = await _wait_for_event(
            host_ws,
            "combat_update",
            timeout=2,
            start_index=host_before,
            predicate=lambda event: event.get("action") == "condition_remove" and event.get("target_id") == guest_char.id,
        )
        guest_remove_self_update = await _wait_for_event(
            guest_ws,
            "combat_update",
            timeout=2,
            start_index=guest_before,
            predicate=lambda event: event.get("action") == "condition_remove" and event.get("target_id") == guest_char.id,
        )
        assert host_remove_self_update["target_state"] == guest_remove_self_body["target_state"]
        assert host_remove_self_update["condition_result"] == guest_remove_self_body["condition_result"]
        assert host_remove_self_update["dice_result"] == guest_remove_self_body["dice_result"]
        assert host_remove_self_update["special_action"] == guest_remove_self_body["special_action"]
        assert "turn_state" not in host_remove_self_update
        assert guest_remove_self_update["dice_result"] == guest_remove_self_body["dice_result"]
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_ai_control_prompts_are_private_to_driver(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Monster/lair control prompts are visible and executable only by the AI driver."""
    import json
    import uuid as _uuid
    import api.ws as ws_api
    from models import CombatState, Session
    from services.combat_turn_state_service import DEFAULT_TURN_STATE
    from services.ws_manager import ws_manager
    from sqlalchemy.orm.attributes import flag_modified

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_ai_control_privacy",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]
    boss_id = "stage6-ai-control-boss"
    legendary_secret = "Private Detect"
    lair_secret = "Private Seismic Pulse"

    session = await db_session.get(Session, sid)
    session.combat_active = True
    state = dict(session.game_state or {})
    state["enemies"] = [{
        "id": boss_id,
        "name": "Stage 6 Privacy Boss",
        "hp_current": 30,
        "hp_max": 30,
        "ac": 15,
        "conditions": [],
        "condition_durations": {},
        "derived": {
            "hp_max": 30,
            "ac": 15,
            "attack_bonus": 6,
            "damage_dice": "1d8+3",
            "ability_modifiers": {"str": 3, "dex": 2, "con": 2},
        },
        "legendary_actions": [{
            "id": "private-detect",
            "name": legendary_secret,
            "cost": 1,
            "description": "Secret monster-side option text.",
        }],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 2,
        "lair_actions": [{
            "id": "private-pulse",
            "name": lair_secret,
            "save": "dex",
            "save_dc": 12,
            "damage_dice": "1d4",
            "damage_type": "force",
            "half_on_save": True,
        }],
        "identified": False,
    }]
    session.game_state = state
    flag_modified(session, "game_state")

    combat = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={
            guest_char.id: {"x": 5, "y": 5},
            host_char.id: {"x": 8, "y": 5},
            boss_id: {"x": 6, "y": 5},
        },
        turn_order=[
            {"character_id": guest_char.id, "name": guest_char.name, "initiative": 18, "is_player": True, "is_enemy": False},
            {"character_id": host_char.id, "name": host_char.name, "initiative": 14, "is_player": True, "is_enemy": False},
            {"character_id": boss_id, "name": "Stage 6 Privacy Boss", "initiative": 10, "is_player": False, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={
            guest_char.id: dict(DEFAULT_TURN_STATE),
            host_char.id: dict(DEFAULT_TURN_STATE),
            boss_id: dict(DEFAULT_TURN_STATE),
        },
    )
    db_session.add(combat)
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")
        await _wait_for_event(guest_ws, "member_online")
        await _wait_for_event(host_ws, "room_state_updated")
        await _wait_for_event(guest_ws, "room_state_updated")

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        legendary_response = await client.post(
            f"/game/combat/{sid}/end-turn",
            headers=_h(guest["token"]),
            json={"expected_turn_token": f"1:0:{guest_char.id}"},
        )

        assert legendary_response.status_code == 200, legendary_response.text
        legendary_body = legendary_response.json()
        assert legendary_body["legendary_action_prompt"] is None
        assert legendary_secret not in json.dumps(legendary_body)

        host_legendary = await _wait_for_event(host_ws, "turn_changed", start_index=host_before)
        guest_legendary = await _wait_for_event(guest_ws, "turn_changed", start_index=guest_before)
        assert host_legendary["legendary_action_prompt"]["actor_id"] == boss_id
        assert host_legendary["legendary_action_prompt"]["actions"][0]["name"] == legendary_secret
        assert guest_legendary["legendary_action_prompt"] is None
        assert legendary_secret not in json.dumps(guest_legendary)

        guest_use_legendary = await client.post(
            f"/game/combat/{sid}/legendary-action",
            headers=_h(guest["token"]),
            json={"actor_id": boss_id, "action_id": "private-detect"},
        )
        assert guest_use_legendary.status_code == 403, guest_use_legendary.text

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        host_use_legendary = await client.post(
            f"/game/combat/{sid}/legendary-action",
            headers=_h(host["token"]),
            json={"actor_id": boss_id, "action_id": "private-detect"},
        )
        assert host_use_legendary.status_code == 200, host_use_legendary.text
        legendary_result = host_use_legendary.json()
        assert legendary_result["action"] == "legendary_action"
        assert legendary_result["dice_result"]["action_name"] == legendary_secret
        assert legendary_result["special_action"] == legendary_result["dice_result"]

        host_legendary_update = await _wait_for_event(
            host_ws,
            "combat_update",
            start_index=host_before,
            predicate=lambda event: event.get("action") == "legendary_action",
        )
        guest_legendary_update = await _wait_for_event(
            guest_ws,
            "combat_update",
            start_index=guest_before,
            predicate=lambda event: event.get("action") == "legendary_action",
        )
        assert host_legendary_update["actor_id"] == boss_id
        assert host_legendary_update["actor_name"] == "Stage 6 Privacy Boss"
        assert host_legendary_update["action"] == "legendary_action"
        assert host_legendary_update["legendary_action"] == legendary_result["dice_result"]
        assert host_legendary_update["dice_result"] == legendary_result["dice_result"]
        assert host_legendary_update["special_action"] == legendary_result["special_action"]
        assert host_legendary_update["actor_state"] == legendary_result["actor_state"]
        assert "turn_state" not in host_legendary_update
        assert guest_legendary_update["dice_result"] == legendary_result["dice_result"]
        assert guest_legendary_update["special_action"] == legendary_result["special_action"]
        assert "turn_state" not in guest_legendary_update

        await db_session.refresh(session)
        await db_session.refresh(combat)
        state = dict(session.game_state or {})
        enemies = list(state.get("enemies") or [])
        enemies[0]["legendary_action_uses_remaining"] = 1
        state["enemies"] = enemies
        state.pop("lair_action_prompted_round", None)
        state.pop("lair_action_used_round", None)
        session.game_state = state
        combat.turn_order = [
            {"character_id": guest_char.id, "name": guest_char.name, "initiative": 24, "is_player": True, "is_enemy": False},
            {"character_id": host_char.id, "name": host_char.name, "initiative": 18, "is_player": True, "is_enemy": False},
            {"character_id": boss_id, "name": "Stage 6 Privacy Boss", "initiative": 10, "is_player": False, "is_enemy": True},
        ]
        combat.current_turn_index = 0
        combat.round_number = 2
        flag_modified(session, "game_state")
        flag_modified(combat, "turn_order")
        await db_session.commit()

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        lair_response = await client.post(
            f"/game/combat/{sid}/end-turn",
            headers=_h(guest["token"]),
            json={"expected_turn_token": f"2:0:{guest_char.id}"},
        )

        assert lair_response.status_code == 200, lair_response.text
        lair_body = lair_response.json()
        assert lair_body["lair_action_prompt"] is None
        assert lair_secret not in json.dumps(lair_body)

        host_lair = await _wait_for_event(host_ws, "turn_changed", start_index=host_before)
        guest_lair = await _wait_for_event(guest_ws, "turn_changed", start_index=guest_before)
        host_lair_prompt = host_lair["lair_action_prompt"]
        assert host_lair_prompt["source_id"] == boss_id
        assert host_lair_prompt["actions"][0]["name"] == lair_secret
        assert guest_lair["lair_action_prompt"] is None
        assert lair_secret not in json.dumps(guest_lair)

        guest_use_lair = await client.post(
            f"/game/combat/{sid}/lair-action",
            headers=_h(guest["token"]),
            json={"source_id": boss_id, "action_id": "private-pulse", "target_id": guest_char.id},
        )
        assert guest_use_lair.status_code == 403, guest_use_lair.text

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        host_use_lair = await client.post(
            f"/game/combat/{sid}/lair-action",
            headers=_h(host["token"]),
            json={"source_id": boss_id, "action_id": "private-pulse", "target_id": guest_char.id},
        )
        assert host_use_lair.status_code == 200, host_use_lair.text
        lair_result = host_use_lair.json()
        assert lair_result["action"] == "lair_action"
        assert lair_result["dice_result"]["action_name"] == lair_secret
        assert lair_result["special_action"] == lair_result["dice_result"]

        host_lair_update = await _wait_for_event(
            host_ws,
            "combat_update",
            start_index=host_before,
            predicate=lambda event: event.get("action") == "lair_action",
        )
        guest_lair_update = await _wait_for_event(
            guest_ws,
            "combat_update",
            start_index=guest_before,
            predicate=lambda event: event.get("action") == "lair_action",
        )
        assert host_lair_update["actor_id"] == boss_id
        assert host_lair_update["actor_name"] == "Stage 6 Privacy Boss"
        assert host_lair_update["action"] == "lair_action"
        assert host_lair_update["lair_action"] == lair_result["dice_result"]
        assert host_lair_update["target_id"] == lair_result["target_id"]
        assert host_lair_update["target_name"] == lair_result["target_name"]
        assert host_lair_update["target_state"] == lair_result["target_state"]
        assert host_lair_update["save"] == lair_result["save"]
        assert host_lair_update["damage"] == lair_result["damage"]
        assert host_lair_update["total_damage"] == lair_result["total_damage"]
        assert host_lair_update["damage_roll"] == lair_result["damage_roll"]
        assert host_lair_update["damage_type"] == lair_result["damage_type"]
        assert host_lair_update["dice_result"] == lair_result["dice_result"]
        assert host_lair_update["special_action"] == lair_result["special_action"]
        assert "turn_state" not in host_lair_update
        assert guest_lair_update["dice_result"] == lair_result["dice_result"]
        assert guest_lair_update["special_action"] == lair_result["special_action"]
        assert "turn_state" not in guest_lair_update
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_enemy_inspect_combat_update_is_private_to_viewer(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """Enemy inspect details must be projected per viewer in combat_update events."""
    import uuid as _uuid
    import api.ws as ws_api
    from models import CombatState, Session
    from services.combat_turn_state_service import DEFAULT_TURN_STATE
    from services.ws_manager import ws_manager
    from sqlalchemy.orm.attributes import flag_modified

    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        async_sessionmaker(engine, expire_on_commit=False),
    )

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_inspect_privacy",
    )
    host = room_data["host"]
    guest = room_data["guest"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]
    enemy_id = "private-stalker"

    session = await db_session.get(Session, sid)
    session.combat_active = True
    state = dict(session.game_state or {})
    state["enemies"] = [{
        "id": enemy_id,
        "name": "Private Stalker",
        "hp_current": 18,
        "hp_max": 18,
        "ac": 14,
        "cr": "2",
        "speed": 40,
        "resistances": ["necrotic"],
        "immunities": ["poison"],
        "actions": [{"name": "Shadow Strike"}],
        "special_abilities": [{"name": "Shadow Blend"}],
        "tactics": "Flank isolated casters.",
        "conditions": [],
        "derived": {"hp_max": 18, "ac": 14, "ability_modifiers": {"dex": 2}},
    }]
    session.game_state = state
    flag_modified(session, "game_state")

    combat = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={
            enemy_id: {"x": 6, "y": 5},
            host_char.id: {"x": 5, "y": 5},
            guest_char.id: {"x": 4, "y": 5},
        },
        turn_order=[
            {"character_id": host_char.id, "name": host_char.name, "initiative": 14, "is_player": True, "is_enemy": False},
            {"character_id": guest_char.id, "name": guest_char.name, "initiative": 12, "is_player": True, "is_enemy": False},
            {"character_id": enemy_id, "name": "Private Stalker", "initiative": 8, "is_player": False, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={host_char.id: dict(DEFAULT_TURN_STATE), guest_char.id: dict(DEFAULT_TURN_STATE)},
    )
    db_session.add(combat)
    await db_session.commit()

    host_ws = QueueWebSocket()
    guest_ws = QueueWebSocket()
    host_task = asyncio.create_task(ws_api.ws_endpoint(host_ws, sid, token=host["token"]))
    guest_task = asyncio.create_task(ws_api.ws_endpoint(guest_ws, sid, token=guest["token"]))

    try:
        await asyncio.wait_for(host_ws.accepted.wait(), timeout=1)
        await asyncio.wait_for(guest_ws.accepted.wait(), timeout=1)
        await _wait_for_event(host_ws, "member_online")

        host_before = len(host_ws.sent)
        guest_before = len(guest_ws.sent)
        response = await client.post(
            f"/game/combat/{sid}/inspect",
            headers=_h(host["token"]),
            json={
                "character_id": host_char.id,
                "target_id": enemy_id,
                "skill": "investigation",
                "d20_value": 18,
            },
        )
        assert response.status_code == 200, response.text
        inspect_body = response.json()
        assert inspect_body["success"] is True
        assert inspect_body["combat"]["entities"][enemy_id]["actions"] == [{"name": "Shadow Strike"}]
        assert inspect_body["inspect_result"]["type"] == "enemy_inspect"
        assert inspect_body["inspect_result"]["actor_id"] == host_char.id
        assert inspect_body["inspect_result"]["target_id"] == enemy_id
        assert inspect_body["inspect_result"]["enemy"]["actions"] == [{"name": "Shadow Strike"}]
        assert inspect_body["dice_result"] == inspect_body["inspect_result"]
        assert inspect_body["special_action"] == inspect_body["inspect_result"]

        host_update = await _wait_for_event(host_ws, "combat_update", timeout=2, start_index=host_before)
        guest_update = await _wait_for_event(guest_ws, "combat_update", timeout=2, start_index=guest_before)
        assert host_update["action"] == "enemy_inspect"
        assert host_update["actor_id"] == host_char.id
        assert host_update["target_id"] == enemy_id
        assert host_update["inspect_result"] == inspect_body["inspect_result"]
        assert host_update["dice_result"] == inspect_body["dice_result"]
        assert host_update["special_action"] == inspect_body["special_action"]
        assert "turn_state" not in host_update

        assert guest_update["action"] == "enemy_inspect"
        assert guest_update["actor_id"] == host_char.id
        assert guest_update["target_id"] == enemy_id
        assert guest_update["inspect_result"]["type"] == "enemy_inspect"
        assert guest_update["inspect_result"]["redacted"] is True
        assert guest_update["inspect_result"]["visibility"] == "other_character"
        assert guest_update["inspect_result"]["skill"] == "investigation"
        assert guest_update["inspect_result"]["dc"] == inspect_body["dc"]
        assert guest_update["inspect_result"]["check"]["total"] == inspect_body["check"]["total"]
        assert "revealed_stats" not in guest_update["inspect_result"]
        assert "enemy" not in guest_update["inspect_result"]
        assert guest_update["dice_result"] == guest_update["inspect_result"]
        assert guest_update["special_action"] == guest_update["inspect_result"]
        assert "turn_state" not in guest_update

        host_enemy = host_update["combat"]["entities"][enemy_id]
        guest_enemy = guest_update["combat"]["entities"][enemy_id]

        assert host_enemy["actions"] == [{"name": "Shadow Strike"}]
        assert host_enemy["resistances"] == ["necrotic"]
        assert host_enemy["knowledge_state"]["viewer_character_id"] == host_char.id

        assert "actions" not in guest_enemy
        assert "resistances" not in guest_enemy
        assert "special_abilities" not in guest_enemy
        assert "knowledge_state" not in guest_enemy
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


async def test_multiplayer_combat_rejects_non_owner_player_character_actions(
    client,
    db_session,
    sample_module,
):
    """A room member must not act for another member's claimed player character."""
    import uuid as _uuid
    from models import CombatState, Session
    from sqlalchemy.orm.attributes import flag_modified

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_owner_guard",
    )
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    guest = room_data["guest"]
    guest_char = room_data["guest_char"]
    enemy_id = "owner-guard"

    session = await db_session.get(Session, sid)
    session.combat_active = True
    state = dict(session.game_state or {})
    state["enemies"] = [{
        "id": enemy_id,
        "name": "Owner Guard",
        "hp_current": 9,
        "max_hp": 9,
        "ac": 13,
        "conditions": [],
        "derived": {"hp_max": 9, "ac": 13, "ability_modifiers": {"dex": 1}},
    }]
    session.game_state = state
    flag_modified(session, "game_state")

    combat = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={
            enemy_id: {"x": 6, "y": 5},
            host_char.id: {"x": 5, "y": 5},
            guest_char.id: {"x": 4, "y": 5},
        },
        turn_order=[
            {"character_id": host_char.id, "name": host_char.name, "initiative": 14, "is_player": True, "is_enemy": False},
            {"character_id": guest_char.id, "name": guest_char.name, "initiative": 12, "is_player": True, "is_enemy": False},
            {"character_id": enemy_id, "name": "Owner Guard", "initiative": 8, "is_player": False, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={},
    )
    db_session.add(combat)
    await db_session.commit()
    await db_session.refresh(combat)

    attack = await client.post(
        f"/game/combat/{sid}/attack-roll",
        headers=_h(guest["token"]),
        json={"entity_id": host_char.id, "target_id": enemy_id, "d20_value": 12},
    )
    assert attack.status_code == 403, attack.text

    end_turn = await client.post(f"/game/combat/{sid}/end-turn", headers=_h(guest["token"]))
    assert end_turn.status_code == 403, end_turn.text
    await db_session.refresh(combat)
    assert combat.current_turn_index == 0


async def test_multiplayer_ai_controlled_actor_actions_are_driver_only(
    client,
    db_session,
    sample_module,
):
    """AI companions and enemy ids cannot be directly controlled by ordinary members."""
    import uuid as _uuid
    from models import Character, CombatState, Session

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_ai_actor_guard",
    )
    sid = room_data["session_id"]
    host = room_data["host"]
    guest = room_data["guest"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]
    enemy_id = "ai-actor-guard"

    ai_companion = Character(
        id=str(_uuid.uuid4()),
        name="Driver Only Companion",
        race="Human",
        char_class="Cleric",
        level=1,
        ability_scores={"str": 10, "dex": 12, "con": 12, "int": 10, "wis": 14, "cha": 10},
        derived={"hp_max": 8, "ac": 13, "initiative": 2},
        hp_current=8,
        is_player=False,
        session_id=sid,
    )
    db_session.add(ai_companion)

    session = await db_session.get(Session, sid)
    session.combat_active = True
    session.game_state = {
        **(session.game_state or {}),
        "enemies": [{
            "id": enemy_id,
            "name": "AI Actor Guard",
            "hp_current": 9,
            "hp_max": 9,
            "ac": 13,
            "conditions": [],
            "condition_durations": {},
            "derived": {"hp_max": 9, "ac": 13, "ability_modifiers": {"dex": 1}},
        }],
    }

    combat = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={
            host_char.id: {"x": 4, "y": 5},
            guest_char.id: {"x": 8, "y": 5},
            ai_companion.id: {"x": 5, "y": 5},
            enemy_id: {"x": 6, "y": 5},
        },
        turn_order=[
            {"character_id": ai_companion.id, "name": ai_companion.name, "initiative": 18, "is_player": False, "is_enemy": False},
            {"character_id": enemy_id, "name": "AI Actor Guard", "initiative": 14, "is_player": False, "is_enemy": True},
            {"character_id": host_char.id, "name": host_char.name, "initiative": 10, "is_player": True, "is_enemy": False},
            {"character_id": guest_char.id, "name": guest_char.name, "initiative": 8, "is_player": True, "is_enemy": False},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={},
    )
    db_session.add(combat)
    await db_session.commit()

    guest_ai_move = await client.post(
        f"/game/combat/{sid}/move",
        headers=_h(guest["token"]),
        json={"entity_id": ai_companion.id, "to_x": 5, "to_y": 6},
    )
    assert guest_ai_move.status_code == 403, guest_ai_move.text

    await db_session.refresh(combat)
    assert combat.entity_positions[ai_companion.id] == {"x": 5, "y": 5}

    guest_enemy_move = await client.post(
        f"/game/combat/{sid}/move",
        headers=_h(guest["token"]),
        json={"entity_id": enemy_id, "to_x": 6, "to_y": 6},
    )
    assert guest_enemy_move.status_code == 403, guest_enemy_move.text

    await db_session.refresh(combat)
    assert combat.entity_positions[enemy_id] == {"x": 6, "y": 5}

    host_ai_move = await client.post(
        f"/game/combat/{sid}/move",
        headers=_h(host["token"]),
        json={"entity_id": ai_companion.id, "to_x": 5, "to_y": 6},
    )
    assert host_ai_move.status_code == 200, host_ai_move.text

    await db_session.refresh(combat)
    assert combat.entity_positions[ai_companion.id] == {"x": 5, "y": 6}


async def test_multiplayer_thrown_recovery_is_owner_or_ai_driver_only(
    client,
    db_session,
    sample_module,
):
    """Post-combat thrown recovery mutates inventory, so it must not use room-wide AI access."""
    import uuid as _uuid
    from models import Character, Session
    from sqlalchemy.orm.attributes import flag_modified

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_thrown_recovery_guard",
    )
    sid = room_data["session_id"]
    host = room_data["host"]
    guest = room_data["guest"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]

    def javelin(quantity=1):
        return {
            "name": "Javelin",
            "type": "simple_melee",
            "damage": "1d6",
            "properties": ["thrown(30/120)"],
            "quantity": quantity,
            "equipped": False,
        }

    ai_companion = Character(
        id=str(_uuid.uuid4()),
        name="Thrown Recovery Companion",
        race="Human",
        char_class="Cleric",
        level=1,
        ability_scores={"str": 10, "dex": 12, "con": 12, "int": 10, "wis": 14, "cha": 10},
        derived={"hp_max": 8, "ac": 13, "initiative": 2},
        hp_current=8,
        is_player=False,
        session_id=sid,
        equipment={"weapons": [javelin()]},
    )
    unclaimed_char = Character(
        id=str(_uuid.uuid4()),
        name="Unclaimed Thrown Recovery Hero",
        race="Human",
        char_class="Fighter",
        level=1,
        ability_scores={"str": 14, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
        derived={"hp_max": 10, "ac": 14, "initiative": 1},
        hp_current=10,
        is_player=True,
        user_id=None,
        session_id=sid,
        equipment={"weapons": [javelin()]},
    )
    host_char.equipment = {"weapons": [javelin()]}
    guest_char.equipment = {"weapons": [javelin()]}
    db_session.add_all([ai_companion, unclaimed_char])

    session = await db_session.get(Session, sid)
    session.combat_active = False

    def pool_item(item_id, character):
        return {
            "id": item_id,
            "status": "available",
            "character_id": character.id,
            "character_name": character.name,
            "weapon": "Javelin",
            "quantity": 1,
            "item": javelin(),
            "public": True,
        }

    session.game_state = {
        **(session.game_state or {}),
        "thrown_weapon_recovery_pool": {
            "version": 1,
            "items": [
                pool_item("thrown-host", host_char),
                pool_item("thrown-guest", guest_char),
                pool_item("thrown-ai", ai_companion),
                pool_item("thrown-unclaimed", unclaimed_char),
            ],
        },
    }
    flag_modified(host_char, "equipment")
    flag_modified(guest_char, "equipment")
    flag_modified(session, "game_state")
    await db_session.commit()

    guest_host_recovery = await client.post(
        f"/game/combat/{sid}/recover-thrown-weapons",
        headers=_h(guest["token"]),
        json={"character_id": host_char.id},
    )
    assert guest_host_recovery.status_code == 403, guest_host_recovery.text

    guest_ai_recovery = await client.post(
        f"/game/combat/{sid}/recover-thrown-weapons",
        headers=_h(guest["token"]),
        json={"character_id": ai_companion.id},
    )
    assert guest_ai_recovery.status_code == 403, guest_ai_recovery.text

    guest_unclaimed_recovery = await client.post(
        f"/game/combat/{sid}/recover-thrown-weapons",
        headers=_h(guest["token"]),
        json={"character_id": unclaimed_char.id},
    )
    assert guest_unclaimed_recovery.status_code == 403, guest_unclaimed_recovery.text

    host_guest_recovery = await client.post(
        f"/game/combat/{sid}/recover-thrown-weapons",
        headers=_h(host["token"]),
        json={"character_id": guest_char.id},
    )
    assert host_guest_recovery.status_code == 403, host_guest_recovery.text

    await db_session.refresh(session)
    assert {
        item["id"]: item["status"]
        for item in session.game_state["thrown_weapon_recovery_pool"]["items"]
    } == {
        "thrown-host": "available",
        "thrown-guest": "available",
        "thrown-ai": "available",
        "thrown-unclaimed": "available",
    }

    guest_own_recovery = await client.post(
        f"/game/combat/{sid}/recover-thrown-weapons",
        headers=_h(guest["token"]),
        json={"character_id": guest_char.id},
    )
    assert guest_own_recovery.status_code == 200, guest_own_recovery.text
    assert guest_own_recovery.json()["recovered"][0]["id"] == "thrown-guest"

    host_ai_recovery = await client.post(
        f"/game/combat/{sid}/recover-thrown-weapons",
        headers=_h(host["token"]),
        json={"character_id": ai_companion.id},
    )
    assert host_ai_recovery.status_code == 200, host_ai_recovery.text
    assert host_ai_recovery.json()["recovered"][0]["id"] == "thrown-ai"

    host_unclaimed_recovery = await client.post(
        f"/game/combat/{sid}/recover-thrown-weapons",
        headers=_h(host["token"]),
        json={"character_id": unclaimed_char.id},
    )
    assert host_unclaimed_recovery.status_code == 200, host_unclaimed_recovery.text
    assert host_unclaimed_recovery.json()["recovered"][0]["id"] == "thrown-unclaimed"

    await db_session.refresh(host_char)
    await db_session.refresh(guest_char)
    await db_session.refresh(ai_companion)
    await db_session.refresh(unclaimed_char)
    await db_session.refresh(session)
    assert host_char.equipment["weapons"][0]["quantity"] == 1
    assert guest_char.equipment["weapons"][0]["quantity"] == 2
    assert ai_companion.equipment["weapons"][0]["quantity"] == 2
    assert unclaimed_char.equipment["weapons"][0]["quantity"] == 2
    assert {
        item["id"]: item["status"]
        for item in session.game_state["thrown_weapon_recovery_pool"]["items"]
    } == {
        "thrown-host": "available",
        "thrown-guest": "recovered",
        "thrown-ai": "recovered",
        "thrown-unclaimed": "recovered",
    }


async def test_multiplayer_end_turn_rejects_ai_companion_current_turn(
    client,
    db_session,
    sample_module,
):
    """AI companion turns must be advanced through AI handling, not player /end-turn."""
    import uuid as _uuid
    from models import Character, CombatState, Session

    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_ai_comp_guard",
    )
    host = room_data["host"]
    sid = room_data["session_id"]

    ai_companion = Character(
        id=str(_uuid.uuid4()),
        name="AI Companion",
        race="Human",
        char_class="Cleric",
        level=1,
        ability_scores={"str": 10, "dex": 12, "con": 12, "int": 10, "wis": 14, "cha": 10},
        derived={"hp_max": 8, "ac": 13, "initiative": 2},
        hp_current=8,
        is_player=False,
        session_id=sid,
    )
    db_session.add(ai_companion)

    session = await db_session.get(Session, sid)
    session.combat_active = True
    combat = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={ai_companion.id: {"x": 5, "y": 5}},
        turn_order=[
            {"character_id": ai_companion.id, "name": ai_companion.name, "initiative": 14, "is_player": False, "is_enemy": False},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={},
    )
    db_session.add(combat)
    await db_session.commit()
    await db_session.refresh(combat)

    response = await client.post(f"/game/combat/{sid}/end-turn", headers=_h(host["token"]))

    assert response.status_code == 400, response.text
    assert "AI-controlled" in response.text
    await db_session.refresh(combat)
    assert combat.current_turn_index == 0


async def test_multiplayer_end_turn_ticks_current_player_conditions(
    client,
    db_session,
    sample_module,
):
    """Ending a guest player's turn should tick that guest, not the host character."""
    room_data = await _create_multiplayer_combat_room(
        client,
        db_session,
        sample_module,
        name_prefix="mp_end_turn_tick",
    )
    host = room_data["host"]
    sid = room_data["session_id"]
    host_char = room_data["host_char"]
    guest_char = room_data["guest_char"]

    import json
    import services.langgraph_client as lc

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "A sentry tests the party.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "initial_enemies": [{"name": "Clockwork Sentry", "hp": 9, "ac": 13}],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }),
            "success": True,
        }

    from models import CombatState
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    original_call = lc.langgraph_client.call_dm_agent
    lc.langgraph_client.call_dm_agent = fake_call_dm_agent
    try:
        start_response = await client.post("/game/action", headers=_h(host["token"]), json={
            "session_id": sid,
            "action_text": "I start the fight.",
        })
    finally:
        lc.langgraph_client.call_dm_agent = original_call
    assert start_response.status_code == 200, start_response.text

    combat_payload = (await client.get(f"/game/combat/{sid}", headers=_h(host["token"]))).json()
    guest_turn_index = next(
        index
        for index, turn in enumerate(combat_payload["turn_order"])
        if turn["character_id"] == guest_char.id
    )
    combat_row = (
        await db_session.execute(select(CombatState).where(CombatState.session_id == sid))
    ).scalars().first()
    combat_row.current_turn_index = guest_turn_index
    host_char.conditions = ["host_marker"]
    host_char.condition_durations = {"host_marker": 1}
    guest_char.conditions = ["guest_marker"]
    guest_char.condition_durations = {"guest_marker": 1}
    flag_modified(host_char, "conditions")
    flag_modified(host_char, "condition_durations")
    flag_modified(guest_char, "conditions")
    flag_modified(guest_char, "condition_durations")
    await db_session.commit()

    end_response = await client.post(f"/game/combat/{sid}/end-turn", headers=_h(room_data["guest"]["token"]))
    assert end_response.status_code == 200, end_response.text

    await db_session.refresh(host_char)
    await db_session.refresh(guest_char)
    assert "host_marker" in (host_char.conditions or [])
    assert "guest_marker" not in (guest_char.conditions or [])


async def test_fifty_websocket_users_stay_isolated_across_four_player_rooms(
    client,
    engine,
    sample_module,
    monkeypatch,
):
    """50 个在线 WS 连接分布在多房间时，心跳与广播都只作用于各自房间。"""
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

    users = [
        await _register(client, f"ws_capacity_user_{idx:02d}")
        for idx in range(50)
    ]

    rooms = []
    cursor = 0
    for room_idx, size in enumerate([4] * 12 + [2]):
        host = users[cursor]
        created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
            "module_id": sample_module.id,
            "save_name": f"WS 容量房 {room_idx}",
            "max_players": 4,
        })).json()
        room_users = [host]
        cursor += 1

        for _ in range(size - 1):
            guest = users[cursor]
            joined = await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
                "room_code": created["room_code"],
            })
            assert joined.status_code == 200, joined.text
            room_users.append(guest)
            cursor += 1

        rooms.append({
            "session_id": created["session_id"],
            "users": room_users,
        })

    assert cursor == 50

    sockets = []
    tasks = []
    try:
        for room in rooms:
            for user in room["users"]:
                ws = QueueWebSocket()
                task = asyncio.create_task(
                    ws_api.ws_endpoint(ws, room["session_id"], token=user["token"])
                )
                sockets.append({
                    "ws": ws,
                    "task": task,
                    "session_id": room["session_id"],
                    "user_id": user["user_id"],
                })
                tasks.append(task)

        await asyncio.wait_for(
            asyncio.gather(*(item["ws"].accepted.wait() for item in sockets)),
            timeout=3,
        )

        for item in sockets:
            await item["ws"].push({"type": "ping"})

        await asyncio.wait_for(
            asyncio.gather(*(
                _wait_for_event(item["ws"], "pong", timeout=2)
                for item in sockets
            )),
            timeout=5,
        )

        expected_by_room = {
            room["session_id"]: [user["user_id"] for user in room["users"]]
            for room in rooms
        }
        for session_id, expected_user_ids in expected_by_room.items():
            assert sorted(await ws_manager.online_users(session_id)) == sorted(expected_user_ids)

        first_room_id = rooms[0]["session_id"]
        sender = next(item for item in sockets if item["session_id"] == first_room_id)
        same_room_receivers = [
            item for item in sockets
            if item["session_id"] == first_room_id and item["user_id"] != sender["user_id"]
        ]
        other_room_sockets = [
            item for item in sockets
            if item["session_id"] != first_room_id
        ]

        before_counts = {id(item["ws"]): len(item["ws"].sent) for item in sockets}
        await sender["ws"].push({"type": "typing", "is_typing": True})
        typing_events = await asyncio.gather(*(
            _wait_for_event(item["ws"], "typing", timeout=2)
            for item in same_room_receivers
        ))

        assert len(typing_events) == 3
        assert all(event["user_id"] == sender["user_id"] for event in typing_events)
        assert not any(event.get("type") == "typing" for event in sender["ws"].sent)

        await asyncio.sleep(0.05)
        for item in other_room_sockets:
            new_events = item["ws"].sent[before_counts[id(item["ws"])]:]
            assert not any(event.get("type") == "typing" for event in new_events)
    finally:
        for item in sockets:
            await item["ws"].disconnect()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()
