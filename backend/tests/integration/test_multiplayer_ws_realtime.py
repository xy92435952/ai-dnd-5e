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
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
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
    import uuid as _uuid
    from models import Character
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

    host = await _register(client, "ws_action_host", display_name="Host Player")
    guest = await _register(client, "ws_action_guest", display_name="Guest Player")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS action room",
        "max_players": 4,
    })).json()
    sid = created["session_id"]
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": created["room_code"],
    })

    host_char = Character(
        id=str(_uuid.uuid4()),
        name="Lorin",
        race="Human",
        char_class="Rogue",
        level=1,
        ability_scores={"str": 10, "dex": 16, "con": 12, "int": 12, "wis": 10, "cha": 10},
        hp_current=8,
        is_player=True,
        session_id=sid,
    )
    guest_char = Character(
        id=str(_uuid.uuid4()),
        name="Aela",
        race="Elf",
        char_class="Wizard",
        level=1,
        ability_scores={"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 10},
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
    started = await client.post(f"/game/rooms/{sid}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text

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


async def test_http_multiplayer_combat_trigger_notifies_room_websocket_clients(
    client,
    db_session,
    engine,
    sample_module,
    monkeypatch,
):
    """When exploration triggers combat, realtime clients should see the combat transition signal."""
    import json
    import uuid as _uuid
    from models import Character
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

    host = await _register(client, "ws_combat_host", display_name="Combat Host")
    guest = await _register(client, "ws_combat_guest", display_name="Combat Guest")
    created = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "WS combat room",
        "max_players": 4,
    })).json()
    sid = created["session_id"]
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": created["room_code"],
    })

    host_char = Character(
        id=str(_uuid.uuid4()),
        name="Mara",
        race="Human",
        char_class="Fighter",
        level=1,
        ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        hp_current=12,
        is_player=True,
        session_id=sid,
    )
    guest_char = Character(
        id=str(_uuid.uuid4()),
        name="Nim",
        race="Halfling",
        char_class="Rogue",
        level=1,
        ability_scores={"str": 8, "dex": 16, "con": 12, "int": 12, "wis": 10, "cha": 10},
        hp_current=8,
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
    started = await client.post(f"/game/rooms/{sid}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text

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
