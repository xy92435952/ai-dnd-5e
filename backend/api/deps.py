"""
共享依赖与辅助函数
game.py 和 combat.py 共同使用
"""
from typing import Optional
from fastapi import HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import Session, Character, GameLog, CombatState, Module, SessionMember
from services.dnd_rules import get_effective_derived, get_effective_hp_base
from services.session_access_service import assert_character_in_session


# ── JWT 鉴权依赖 ─────────────────────────────────────

async def get_current_user(request: Request) -> dict:
    """从 Authorization header 解析当前用户。所有需要鉴权的端点使用此依赖。"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "未登录，请先登录")
    token = auth_header[7:]
    from api.auth import decode_token
    return decode_token(token)


async def get_optional_user_id(request: Request) -> Optional[str]:
    """Return the authenticated user id when a bearer token is present."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    from api.auth import decode_token
    return decode_token(token)["user_id"]


def get_user_id(user: dict = Depends(get_current_user)) -> str:
    """快捷依赖：只返回 user_id 字符串。"""
    return user["user_id"]


async def get_session_or_404(session_id: str, db: AsyncSession) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "会话不存在")
    return session


async def assert_session_access(
    session: Session,
    user_id: str,
    db: AsyncSession,
) -> Optional[SessionMember]:
    """Ensure the current user may read or mutate this game session.

    Single-player sessions are owned by ``Session.user_id``. Multiplayer
    sessions are readable only by room members, so unrelated logged-in users
    cannot restore another room by guessing a session id.
    """
    if session.is_multiplayer:
        result = await db.execute(
            select(SessionMember).where(
                SessionMember.session_id == session.id,
                SessionMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(403, "你不在该房间中")
        return member

    if session.user_id and session.user_id != user_id:
        raise HTTPException(403, "无权访问该存档")
    return None


async def assert_optional_session_access(
    session: Session,
    user_id: Optional[str],
    db: AsyncSession,
) -> Optional[SessionMember]:
    """Permit legacy unauthenticated single-player calls, but guard multiplayer rooms."""
    if user_id is None:
        if session.is_multiplayer:
            raise HTTPException(401, "Login required for multiplayer session")
        return None
    return await assert_session_access(session, user_id, db)


async def assert_character_access(
    character: Character,
    user_id: str,
    db: AsyncSession,
    *,
    allow_room_ai: bool = True,
) -> None:
    """Ensure the current user may inspect or mutate a character."""
    if character.user_id:
        if character.user_id != user_id:
            raise HTTPException(403, "这不是你的角色")
        return

    if character.session_id:
        session = await get_session_or_404(character.session_id, db)
        if session.is_multiplayer and allow_room_ai:
            await assert_session_access(session, user_id, db)
            return
        if not session.is_multiplayer and session.user_id == user_id:
            return

    raise HTTPException(403, "无权访问该角色")


def assert_module_access(module: Module, user_id: str) -> None:
    """Ensure the current user may use a parsed module."""
    if module.user_id and module.user_id != user_id:
        raise HTTPException(403, "No access to this module")


def char_brief(char: Character) -> dict:
    """返回角色的简要信息（用于 DM 上下文构建 + 前端面板渲染）"""
    base_derived = char.derived or {}
    derived = get_effective_derived(char)
    base_hp_max = get_effective_hp_base(char, base_derived)
    return {
        "id":               char.id,
        "name":             char.name,
        "race":             char.race,
        "char_class":       char.char_class,
        "level":            char.level,
        "hp_current":       char.hp_current,
        "hp_max":           derived.get("hp_max", char.hp_current),
        "base_hp_max":      base_hp_max,
        "ac":               derived.get("ac", 10),
        "is_player":        char.is_player,
        "spell_slots":      char.spell_slots or {},
        "proficient_skills":char.proficient_skills or [],
        "proficient_saves": char.proficient_saves or [],
        "conditions":       char.conditions or [],
        "condition_durations": char.condition_durations or {},
        "derived":          derived,
        "concentration":    char.concentration,
        "known_spells":     char.known_spells or [],
        "cantrips":         char.cantrips or [],
        "equipment":        char.equipment or {},
        "fighting_style":   char.fighting_style,
        # 角色叙事（玩家被 AI 托管时供 DM 代演用，前端也可显示）
        "personality":       char.personality,
        "backstory":         char.backstory,
        "speech_style":      char.speech_style,
        "combat_preference": char.combat_preference,
        "catchphrase":       char.catchphrase,
    }


def entity_snapshot(char: Character, is_enemy: bool = False) -> dict:
    """战斗地图上的实体快照"""
    base_derived = char.derived or {}
    derived = get_effective_derived(char)
    base_hp_max = get_effective_hp_base(char, base_derived)
    return {
        "id":         char.id,
        "name":       char.name,
        "is_player":  char.is_player and not is_enemy,
        "is_enemy":   is_enemy,
        "hp_current": char.hp_current,
        "hp_max":     derived.get("hp_max", char.hp_current),
        "base_hp_max": base_hp_max,
        "ac":         derived.get("ac", 10),
        "conditions": char.conditions or [],
        "derived":    derived,
    }


def serialize_combat(combat: CombatState) -> dict:
    return {
        "session_id":        combat.session_id,
        "turn_order":        combat.turn_order or [],
        "current_turn_index":combat.current_turn_index,
        "round_number":      combat.round_number,
        "entity_positions":  combat.entity_positions or {},
        "grid_data":         combat.grid_data or {},
    }


def serialize_log(log: GameLog) -> dict:
    return {
        "id":          log.id,
        "role":        log.role,
        "content":     log.content,
        "log_type":    log.log_type,
        "dice_result": log.dice_result,
        "visibility":   log.visibility or {},
        "table_reason": log.table_reason or "",
        "table_decision": log.table_decision or {},
        "created_at":  log.created_at.isoformat() if log.created_at else None,
    }


def can_user_see_log(log: GameLog, user_id: Optional[str]) -> bool:
    """Return whether a multiplayer user can see this persisted log entry."""
    visibility = log.visibility or {}
    visible_to = visibility.get("visible_to_user_ids") or []
    if not visible_to:
        return True
    return bool(user_id and user_id in visible_to)


# ── 多人联机：权限校验 + 广播辅助 ───────────────────

async def assert_can_act(
    session: Session,
    user_id: str,
    entity_id: str,
    db: AsyncSession,
    *,
    require_current_turn: bool = True,
) -> None:
    """多人联机：校验当前 user 是否有权操作 entity_id 这个角色。

    单人模式（is_multiplayer=False）：跳过所有校验，保持向后兼容。
    多人模式：
      - AI 队友（is_player=False）：任何房间成员都可触发（通过 ai-turn）
      - 真人玩家角色：必须是 character.user_id == user_id
      - 战斗中且 require_current_turn=True：还要求是当前回合实体
    """
    await assert_session_access(session, user_id, db)

    if not session.is_multiplayer:
        return

    char = await db.get(Character, entity_id)
    if char is None:
        return  # 让上层端点自己处理 404

    if require_current_turn and session.combat_active:
        result = await db.execute(
            select(CombatState)
            .where(CombatState.session_id == session.id)
            .order_by(CombatState.created_at.desc())
        )
        cs = result.scalars().first()
        if cs and cs.turn_order:
            try:
                current = cs.turn_order[cs.current_turn_index or 0]
                current_id = current.get("character_id") if isinstance(current, dict) else None
                if current_id and current_id != entity_id:
                    raise HTTPException(403, "现在不是你的回合")
            except (IndexError, AttributeError):
                pass

    # AI 托管的角色（未被认领或已降级）→ 房间任意成员可在该角色回合触发
    if not char.is_player or char.user_id is None:
        return

    if char.user_id != user_id:
        raise HTTPException(403, "这不是你的角色")


async def broadcast_to_session(session: Session, event) -> None:
    """
    广播事件到房间所有 WS 连接。单人模式静默跳过。

    `event` 接受两种形式：
      - Pydantic 的 BaseModel 实例（推荐，schemas/ws_events.py 中定义）
      - 裸 dict（向后兼容，建议逐步替换为 Pydantic）
    """
    if not session.is_multiplayer:
        return

    # Pydantic → dict 统一成 JSON 兼容
    from pydantic import BaseModel as _PydBase
    if isinstance(event, _PydBase):
        payload = event.model_dump(mode="json")
    else:
        payload = event

    # 延迟 import，避免循环依赖
    from services.ws_manager import ws_manager
    try:
        await ws_manager.broadcast(session.id, payload)
    except Exception:
        # 广播失败不应阻塞 API 响应
        pass


def current_turn_user_id(session: Session, combat: Optional[CombatState], characters: dict[str, Character]) -> Optional[str]:
    """从战斗状态推导出当前回合归属的 user_id（None=AI 托管或单人模式）。"""
    if not session.is_multiplayer or combat is None or not combat.turn_order:
        return None
    try:
        current = combat.turn_order[combat.current_turn_index or 0]
        if isinstance(current, dict):
            cid = current.get("character_id")
            char = characters.get(cid) if cid else None
            return char.user_id if char and char.is_player else None
    except (IndexError, AttributeError):
        pass
    return None
