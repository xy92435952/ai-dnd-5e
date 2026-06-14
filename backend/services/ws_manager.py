"""WebSocket 房间广播管理器（v0.9 多人联机）

设计目标：
- 单实例部署，使用进程内字典维护房间→连接列表
- 不依赖 Redis（小规模 2-4 人房间足够）
- 心跳清理：异步任务每 30 秒检查 stale 连接
- 线程安全：所有操作通过 asyncio.Lock 串行化

未来若需要多实例水平扩展，可替换为 Redis Pub/Sub 实现，对外接口保持不变。
"""
import asyncio
import logging
from datetime import datetime
from typing import Iterable, Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WSManager:
    def __init__(self, *, send_timeout_seconds: float = 2.0):
        # session_id -> set[WebSocket]
        self.rooms: dict[str, set[WebSocket]] = {}
        # (session_id, user_id) -> WebSocket（一个用户在一个房间内仅一个连接，重连会替换）
        self.user_ws: dict[tuple[str, str], WebSocket] = {}
        # WebSocket -> (session_id, user_id)（反向索引，便于断开时清理）
        self.ws_meta: dict[WebSocket, tuple[str, str]] = {}
        self.send_timeout_seconds = send_timeout_seconds
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, user_id: str, ws: WebSocket) -> None:
        """注册一个新连接。如果同一 user 在同一房间已有旧连接，旧连接会被踢掉。"""
        old = None
        async with self._lock:
            old = self.user_ws.get((session_id, user_id))
            if old is not None and old is not ws:
                self.rooms.get(session_id, set()).discard(old)
                self.ws_meta.pop(old, None)

            self.rooms.setdefault(session_id, set()).add(ws)
            self.user_ws[(session_id, user_id)] = ws
            self.ws_meta[ws] = (session_id, user_id)
        if old is not None and old is not ws:
            try:
                await old.close(code=4000, reason="Replaced by new connection")
            except Exception:
                pass
        logger.info(f"WS connected: session={session_id} user={user_id}")

    async def disconnect(self, ws: WebSocket) -> Optional[tuple[str, str]]:
        """断开一个连接，返回 (session_id, user_id) 供调用方做后续处理（如广播离线）。"""
        async with self._lock:
            meta = self.ws_meta.pop(ws, None)
            if meta is None:
                return None
            session_id, user_id = meta
            self.rooms.get(session_id, set()).discard(ws)
            # 仅当 user_ws 指向的是这个 ws 时才清理（防止竞态）
            if self.user_ws.get((session_id, user_id)) is ws:
                self.user_ws.pop((session_id, user_id), None)
            if not self.rooms.get(session_id):
                self.rooms.pop(session_id, None)
        logger.info(f"WS disconnected: session={session_id} user={user_id}")
        return meta

    async def disconnect_user(
        self,
        session_id: str,
        user_id: str,
        *,
        code: int = 4001,
        reason: str = "Disconnected by room lifecycle",
    ) -> bool:
        """Remove and close one user's active socket in one room."""
        async with self._lock:
            ws = self.user_ws.pop((session_id, user_id), None)
            if ws is None:
                return False

            self.rooms.get(session_id, set()).discard(ws)
            self.ws_meta.pop(ws, None)
            if not self.rooms.get(session_id):
                self.rooms.pop(session_id, None)

        try:
            await ws.close(code=code, reason=reason)
        except Exception:
            pass
        logger.info(f"WS force-disconnected: session={session_id} user={user_id}")
        return True

    async def disconnect_room(
        self,
        session_id: str,
        *,
        code: int = 4002,
        reason: str = "Room closed",
    ) -> int:
        """Remove and close every active socket in a room."""
        async with self._lock:
            targets = set(self.rooms.pop(session_id, set()))
            targets.update(
                ws
                for (sid, _uid), ws in self.user_ws.items()
                if sid == session_id
            )

            for ws in targets:
                meta = self.ws_meta.pop(ws, None)
                if meta and self.user_ws.get(meta) is ws:
                    self.user_ws.pop(meta, None)

            for key in [
                key for key in self.user_ws.keys()
                if key[0] == session_id
            ]:
                self.user_ws.pop(key, None)

        for ws in targets:
            try:
                await ws.close(code=code, reason=reason)
            except Exception:
                pass
        if targets:
            logger.info(f"WS room force-disconnected: session={session_id} count={len(targets)}")
        return len(targets)

    async def broadcast(self, session_id: str, event, exclude_user_id: Optional[str] = None) -> int:
        """
        向房间内所有连接广播。返回成功发送的连接数。

        `event` 既可以是 dict 也可以是 Pydantic BaseModel 实例
        （推荐走 schemas.ws_events 里定义的事件类型）。
        """
        # Pydantic 实例自动序列化
        from pydantic import BaseModel as _PydBase
        if isinstance(event, _PydBase):
            event = event.model_dump(mode="json")

        # 拷贝快照避免广播过程中字典被改
        async with self._lock:
            room_sockets = set(self.rooms.get(session_id, set()))
            targets = [
                (ws, (sid, uid))
                for (sid, uid), ws in self.user_ws.items()
                if sid == session_id and ws in room_sockets
            ]
            seen = {ws for ws, _meta in targets}
            targets.extend(
                (ws, self.ws_meta.get(ws))
                for ws in room_sockets
                if ws not in seen
            )

        sent_count = 0
        for ws, meta in targets:
            if exclude_user_id:
                if meta and meta[1] == exclude_user_id:
                    continue
            event_for_user = self._event_for_user(event, meta[1]) if meta else event
            if await self._send_broadcast(ws, event_for_user):
                sent_count += 1
        return sent_count

    async def _send_broadcast(self, ws: WebSocket, event) -> bool:
        try:
            await asyncio.wait_for(
                ws.send_json(event),
                timeout=self.send_timeout_seconds,
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("WS broadcast timed out for one connection")
            asyncio.create_task(self._silent_disconnect(ws))
            return False
        except WebSocketDisconnect:
            logger.info("WS broadcast hit a disconnected socket")
            await self.disconnect(ws)
            return False
        except Exception as e:
            logger.warning(f"WS broadcast failed for one connection: {e}")
            asyncio.create_task(self._silent_disconnect(ws))
            return False

    async def send_to_user(self, session_id: str, user_id: str, event) -> bool:
        """点对点发送。event 同样接受 dict 或 Pydantic BaseModel。"""
        from pydantic import BaseModel as _PydBase
        if isinstance(event, _PydBase):
            event = event.model_dump(mode="json")

        async with self._lock:
            ws = self.user_ws.get((session_id, user_id))
        if ws is None:
            return False
        event = self._event_for_user(event, user_id)
        try:
            await ws.send_json(event)
            return True
        except WebSocketDisconnect:
            await self.disconnect(ws)
            return False
        except Exception:
            asyncio.create_task(self._silent_disconnect(ws))
            return False

    async def online_users(self, session_id: str) -> list[str]:
        async with self._lock:
            return [
                uid for (sid, uid) in self.user_ws.keys()
                if sid == session_id
            ]

    async def is_current_connection(self, session_id: str, user_id: str, ws: WebSocket) -> bool:
        async with self._lock:
            return self.user_ws.get((session_id, user_id)) is ws

    def _event_for_user(self, event, user_id: str):
        if not isinstance(event, dict):
            return event
        if event.get("type") != "room_state_updated":
            return event
        room = event.get("room")
        if not isinstance(room, dict):
            return event
        try:
            from services.room_info_service import project_room_info_for_viewer

            return {
                **event,
                "room": project_room_info_for_viewer(
                    room,
                    viewer_user_id=user_id,
                ),
            }
        except Exception:
            return event

    async def prune_stale_connections(
        self,
        stale_members: Iterable[tuple[str, str]],
        *,
        code: int = 4001,
        reason: str = "Stale websocket connection",
    ) -> int:
        """Close and remove a batch of known-stale member sockets."""
        removed = 0
        seen: set[tuple[str, str]] = set()
        for session_id, user_id in stale_members:
            key = (session_id, user_id)
            if key in seen:
                continue
            seen.add(key)
            if await self.disconnect_user(session_id, user_id, code=code, reason=reason):
                removed += 1
        return removed

    async def _silent_disconnect(self, ws: WebSocket) -> None:
        try:
            await ws.close()
        except Exception:
            pass
        await self.disconnect(ws)


# 全局单例
ws_manager = WSManager()
