"""
CharacterRoster — 统一"从 session 加载角色列表"的访问模式
============================================================
消除原先散落在 api/game.py 和 api/combat.py 中 9+ 处的重复代码：

    companion_ids = (session.game_state or {}).get("companion_ids", [])
    companions = []
    for cid in companion_ids:
        c = await db.get(Character, cid)
        if c:
            companions.append(c)

改为：
    roster = CharacterRoster(db, session)
    companions = await roster.companions()
    party     = await roster.party()                    # [player] + companions

涉及的"谁是 party"逻辑以后只在这一个地方修改。

NOTE: 不要把这个 service 变成通用 CharacterRepo。它专门服务于
"给定一个 session，取它关联的那批角色"的场景。
角色 CRUD 仍走 api/characters.py + models/character.py。
"""

from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.character import Character
from models.session import Session


class CharacterRoster:
    """
    包装 `session + db`，提供角色名单相关的只读查询
    以及"删除 AI 队友"这种 session 特有的写操作。

    每次请求创建一个实例即可，不要跨请求复用
    （内部缓存仅在本实例生命周期内有效）。
    """

    def __init__(self, db: AsyncSession, session: Session):
        self.db = db
        self.session = session
        self._player_cache: Optional[Character] = None
        self._companions_cache: Optional[list[Character]] = None

    # ─────────────────────────────────────────────
    # 基础访问器
    # ─────────────────────────────────────────────

    def companion_ids(self) -> list[str]:
        """从 session.game_state 里掏出 companion_ids。"""
        return list((self.session.game_state or {}).get("companion_ids", []))

    async def player(self) -> Optional[Character]:
        """加载玩家角色（session.player_character_id）。"""
        if self._player_cache is not None:
            return self._player_cache
        pid = self.session.player_character_id
        if not pid:
            return None
        self._player_cache = await self.db.get(Character, pid)
        return self._player_cache

    async def companions(self) -> list[Character]:
        """加载全部 AI 队友（按 game_state.companion_ids 顺序，跳过已删除）。"""
        if self._companions_cache is not None:
            return self._companions_cache
        result: list[Character] = []
        for cid in self.companion_ids():
            c = await self.db.get(Character, cid)
            if c is not None:
                result.append(c)
        self._companions_cache = result
        return result

    async def party(self) -> list[Character]:
        """返回 [player] + companions，player 缺失时跳过。"""
        player = await self.player()
        comps = await self.companions()
        return ([player] if player else []) + comps

    async def allies_alive(self) -> list[Character]:
        """战斗场景常用：整个队伍中 HP > 0 的成员。"""
        return [c for c in await self.party() if (c.hp_current or 0) > 0]

    async def companions_alive(self) -> list[Character]:
        """只看 AI 队友里还活着的。"""
        return [c for c in await self.companions() if (c.hp_current or 0) > 0]

    # ─────────────────────────────────────────────
    # 写操作
    # ─────────────────────────────────────────────

    async def bind_companions(self, companion_ids: Iterable[str]) -> None:
        """
        创建 session 时用：把一批角色的 session_id 绑到当前 session。
        调用方自己负责 commit。
        """
        for cid in companion_ids:
            c = await self.db.get(Character, cid)
            if c is not None:
                c.session_id = self.session.id
        # 缓存失效
        self._companions_cache = None

    async def delete_ai_companions(self) -> int:
        """
        删除 session 关联的全部 AI 队友（is_player=False）。
        返回被删除的数量。调用方自己负责 commit。

        玩家角色本身不会被删除——玩家控制的 Character 留给账号体系保管。
        """
        deleted = 0
        for cid in self.companion_ids():
            c = await self.db.get(Character, cid)
            if c and not c.is_player:
                await self.db.delete(c)
                deleted += 1
        self._companions_cache = None
        return deleted
