"""WebSocket 端点 — /ws/sessions/{session_id}

协议：JSON 消息，参见 doc/PRD_Multiplayer.md §4.3

鉴权：连接时通过 query string 传 token，服务端 decode_token 验证。
心跳：客户端每 15 秒发 {"type": "pong"}（以及任何活动），服务端更新 last_seen_at。
断线：连接关闭时广播 member_offline 事件。
"""
import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import AsyncSessionLocal
from models import SessionMember, Session
from api.auth import decode_token
from services.ws_manager import ws_manager
from services import room_service
from schemas.ws_events import MemberOnline, MemberOffline, Typing, DMSpeakTurn

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws"])


@router.websocket("/ws/sessions/{session_id}")
async def ws_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(..., description="JWT token"),
):
    # 1. 鉴权
    try:
        payload = decode_token(token)
        user_id = payload["user_id"]
    except Exception as e:
        await websocket.close(code=4401, reason=f"Auth failed: {e}")
        return

    # 2. 验证成员资格
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

    # 3. 接受连接 + 注册
    await websocket.accept()
    await ws_manager.connect(session_id, user_id, websocket)

    # 4. 广播在线
    await ws_manager.broadcast(
        session_id,
        MemberOnline(user_id=user_id),
        exclude_user_id=user_id,
    )

    # 5. 主循环
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "pong" or msg_type == "ping":
                # 心跳：更新数据库 last_seen_at
                async with AsyncSessionLocal() as db:
                    await room_service.update_heartbeat(db, session_id, user_id)
                # 服务端回 pong（让客户端确认连接活跃）
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong", "ts": datetime.utcnow().isoformat()})

            elif msg_type == "speak_done":
                # 轮流发言：当前发言者按"我说完了"，推进到下一人（A7 阶段实现完整逻辑）
                async with AsyncSessionLocal() as db:
                    next_user = await _advance_speaker(db, session_id, user_id)
                if next_user:
                    await ws_manager.broadcast(
                        session_id,
                        DMSpeakTurn(user_id=next_user, auto=False),
                    )

            elif msg_type == "typing":
                # 打字状态广播给其他人
                await ws_manager.broadcast(
                    session_id,
                    Typing(user_id=user_id, is_typing=bool(data.get("is_typing"))),
                    exclude_user_id=user_id,
                )

            else:
                logger.debug(f"Unknown WS message type from {user_id}: {msg_type}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WS error session={session_id} user={user_id}: {e}")
    finally:
        await ws_manager.disconnect(websocket)
        # 广播离线
        await ws_manager.broadcast(
            session_id,
            MemberOffline(user_id=user_id),
        )


async def _advance_speaker(db: AsyncSession, session_id: str, current_user_id: str) -> str | None:
    """A7 完整实现见 services/multiplayer_dm.py。这里给个最小可用版本。"""
    session = await db.get(Session, session_id)
    if not session:
        return None
    state = session.game_state or {}
    mp = state.setdefault("multiplayer", {})

    members = await room_service.list_members(db, session_id)
    online_user_ids = [m["user_id"] for m in members if m["is_online"]]
    if not online_user_ids:
        return None

    # 找当前发言者在 online list 中的位置，推到下一位
    if current_user_id in online_user_ids:
        idx = online_user_ids.index(current_user_id)
        next_idx = (idx + 1) % len(online_user_ids)
    else:
        next_idx = 0
    next_user = online_user_ids[next_idx]

    mp["current_speaker_user_id"] = next_user
    if next_idx == 0:
        mp["speak_round"] = (mp.get("speak_round", 0) or 0) + 1
    session.game_state = state
    await db.commit()
    return next_user
