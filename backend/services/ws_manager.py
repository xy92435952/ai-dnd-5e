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
from typing import Optional
from datetime import datetime

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSManager:
    def __init__(self):
        # session_id -> set[WebSocket]
        self.rooms: dict[str, set[WebSocket]] = {}
        # (session_id, user_id) -> WebSocket（一个用户在一个房间内仅一个连接，重连会替换）
        self.user_ws: dict[tuple[str, str], WebSocket] = {}
        # WebSocket -> (session_id, user_id)（反向索引，便于断开时清理）
        self.ws_meta: dict[WebSocket, tuple[str, str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, user_id: str, ws: WebSocket) -> None:
        """注册一个新连接。如果同一 user 在同一房间已有旧连接，旧连接会被踢掉。"""
        async with self._lock:
            old = self.user_ws.get((session_id, user_id))
            if old is not None and old is not ws:
                # 主动关闭旧连接（同一用户多端登录时只保留最新）
                self.rooms.get(session_id, set()).discard(old)
                self.ws_meta.pop(old, None)
                try:
                    await old.close(code=4000, reason="Replaced by new connection")
                except Exception:
                    pass

            self.rooms.setdefault(session_id, set()).add(ws)
            self.user_ws[(session_id, user_id)] = ws
            self.ws_meta[ws] = (session_id, user_id)
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

    async def broadcast(self, session_id: str, event: dict, exclude_user_id: Optional[str] = None) -> int:
        """向房间内所有连接广播。返回成功发送的连接数。"""
        # 拷贝快照避免广播过程中字典被改
        async with self._lock:
            targets = list(self.rooms.get(session_id, set()))
            user_map = {ws: meta for ws, meta in self.ws_meta.items() if meta[0] == session_id}

        ok = 0
        for ws in targets:
            if exclude_user_id:
                meta = user_map.get(ws)
                if meta and meta[1] == exclude_user_id:
                    continue
            try:
                await ws.send_json(event)
                ok += 1
            except Exception as e:
                logger.warning(f"WS broadcast failed for one connection: {e}")
                # 异步清理失败连接（不阻塞广播）
                asyncio.create_task(self._silent_disconnect(ws))
        return ok

    async def send_to_user(self, session_id: str, user_id: str, event: dict) -> bool:
        """点对点发送。"""
        async with self._lock:
            ws = self.user_ws.get((session_id, user_id))
        if ws is None:
            return False
        try:
            await ws.send_json(event)
            return True
        except Exception:
            asyncio.create_task(self._silent_disconnect(ws))
            return False

    async def online_users(self, session_id: str) -> list[str]:
        async with self._lock:
            return [
                uid for (sid, uid) in self.user_ws.keys()
                if sid == session_id
            ]

    async def _silent_disconnect(self, ws: WebSocket) -> None:
        try:
            await ws.close()
        except Exception:
            pass
        await self.disconnect(ws)


# 全局单例
ws_manager = WSManager()
