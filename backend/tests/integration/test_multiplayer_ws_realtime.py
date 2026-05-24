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


async def _wait_for_event(
    ws: QueueWebSocket,
    event_type: str,
    timeout: float = 1.0,
    start_index: int = 0,
):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        for event in ws.sent[start_index:]:
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

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(narrator, "narrate_action", fake_narrate_action)

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

        before_ai_count = len(guest_ws.sent)
        ai_result = await client.post(f"/game/combat/{sid}/ai-turn", headers=_h(host["token"]))
        assert ai_result.status_code == 200, ai_result.text
        assert ai_result.json()["target_id"] == guest_char.id
        assert ai_result.json()["player_can_react"] is True
        assert ai_result.json()["reaction_prompt"]["reactor_character_id"] == guest_char.id
        assert ai_result.json()["reaction_prompt"]["options"][0]["type"] == "hellish_rebuke"
        assert ai_result.json()["reaction_prompt"]["options"][0]["character_id"] == guest_char.id

        await _wait_for_event(guest_ws, "combat_update", timeout=2, start_index=before_ai_count)

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

        await db_session.refresh(guest_char)
        assert guest_char.hp_current == 6
        assert guest_char.spell_slots["1st"] == 0

        reaction_update = await _wait_for_event(host_ws, "combat_update", timeout=2, start_index=before_reaction_count)
        assert reaction_update["actor_id"] == guest_char.id
        assert reaction_update["reaction_type"] == "shield"
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
        assert response.json()["outcome"] == "revive"

        update = await _wait_for_event(host_ws, "combat_update", timeout=2, start_index=before_count)
        assert update["actor_id"] == guest_char.id
        assert update["death_save"]["outcome"] == "revive"
        assert update["combat"]["entities"][guest_char.id]["hp_current"] == 1
    finally:
        await host_ws.disconnect()
        await guest_ws.disconnect()
        await asyncio.gather(host_task, guest_task, return_exceptions=True)
        ws_manager.rooms.clear()
        ws_manager.user_ws.clear()
        ws_manager.ws_meta.clear()


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
