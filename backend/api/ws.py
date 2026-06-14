"""WebSocket endpoint for multiplayer room realtime events."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database import AsyncSessionLocal
from models import Session, SessionMember
from api.auth import decode_token
from services import room_service
from services.ws_manager import ws_manager
from schemas.ws_events import (
    DMSpeakTurn,
    MemberOffline,
    MemberOnline,
    RoomStateUpdated,
    Typing,
    WSError,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws"])
_CONNECT_LOCKS: dict[str, asyncio.Lock] = {}


def _ws_connect_lock(session_id: str) -> asyncio.Lock:
    lock = _CONNECT_LOCKS.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _CONNECT_LOCKS[session_id] = lock
    return lock


@router.websocket("/ws/sessions/{session_id}")
async def ws_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(..., description="JWT token"),
):
    try:
        payload = decode_token(token)
        user_id = payload["user_id"]
    except Exception as exc:
        await websocket.close(code=4401, reason=f"Auth failed: {exc}")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SessionMember).where(
                SessionMember.session_id == session_id,
                SessionMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            await websocket.close(code=4403, reason="Not a room member")
            return
        await room_service.update_heartbeat(db, session_id, user_id)
        online_members = await room_service.list_members(db, session_id)

    connected = False
    try:
        async with _ws_connect_lock(session_id):
            await websocket.accept()
            await ws_manager.connect(session_id, user_id, websocket)
            connected = True

            await ws_manager.broadcast(
                session_id,
                MemberOnline(user_id=user_id, members=online_members),
            )
            if not await ws_manager.is_current_connection(session_id, user_id, websocket):
                return

            async with AsyncSessionLocal() as db:
                room_info = await room_service.get_room_info(db, session_id)
            room_state_event = RoomStateUpdated(room=room_info)
            await ws_manager.broadcast(session_id, room_state_event, exclude_user_id=user_id)
            if not await ws_manager.is_current_connection(session_id, user_id, websocket):
                return
            await ws_manager.send_to_user(session_id, user_id, room_state_event)
            if not await ws_manager.is_current_connection(session_id, user_id, websocket):
                return

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type in {"pong", "ping"}:
                async with AsyncSessionLocal() as db:
                    await room_service.update_heartbeat(db, session_id, user_id)
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong", "ts": datetime.utcnow().isoformat()})

            elif msg_type == "speak_done":
                async with AsyncSessionLocal() as db:
                    next_user = await _advance_speaker(db, session_id, user_id)
                    room_info = await room_service.get_room_info(db, session_id) if next_user else None
                if next_user:
                    await ws_manager.broadcast(
                        session_id,
                        DMSpeakTurn(user_id=next_user, auto=False),
                    )
                    if room_info:
                        await ws_manager.broadcast(
                            session_id,
                            RoomStateUpdated(room=room_info),
                        )
                else:
                    await websocket.send_json(
                        WSError(
                            code="not_current_speaker",
                            message="Only the current speaker can end the speak turn.",
                        ).model_dump(mode="json")
                    )

            elif msg_type == "typing":
                await ws_manager.broadcast(
                    session_id,
                    Typing(user_id=user_id, is_typing=bool(data.get("is_typing"))),
                    exclude_user_id=user_id,
                )

            else:
                logger.debug("Unknown WS message type from %s: %s", user_id, msg_type)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WS error session=%s user=%s: %s", session_id, user_id, exc)
    finally:
        disconnected = await ws_manager.disconnect(websocket) if connected else None
        if disconnected:
            async with AsyncSessionLocal() as db:
                await room_service.mark_offline(db, session_id, user_id)
                offline_members = await room_service.list_members(db, session_id)
                room_info = await room_service.get_room_info(db, session_id)
            await ws_manager.broadcast(
                session_id,
                MemberOffline(user_id=user_id, members=offline_members),
            )
            await ws_manager.broadcast(session_id, RoomStateUpdated(room=room_info))


async def _advance_speaker(db: AsyncSession, session_id: str, current_user_id: str) -> str | None:
    session = await db.get(Session, session_id)
    if not session:
        return None
    state = session.game_state or {}
    mp = state.setdefault("multiplayer", {})
    current_speaker = mp.get("current_speaker_user_id")
    if current_speaker != current_user_id:
        return None

    members = await room_service.list_members(db, session_id)
    online_user_ids = [member["user_id"] for member in members if member["is_online"]]
    if not online_user_ids:
        return None

    if current_user_id in online_user_ids:
        index = online_user_ids.index(current_user_id)
        next_index = (index + 1) % len(online_user_ids)
    else:
        next_index = 0
    next_user = online_user_ids[next_index]

    mp["current_speaker_user_id"] = next_user
    if next_index == 0:
        mp["speak_round"] = (mp.get("speak_round", 0) or 0) + 1
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
    return next_user
