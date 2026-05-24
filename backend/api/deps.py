"""
共享依赖与辅助函数
game.py 和 combat.py 共同使用
"""
from typing import Optional
from fastapi import HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import Session, Character, GameLog, CombatState, Module, SessionMember


# ── JWT 鉴权依赖 ─────────────────────────────────────

async def get_current_user(request: Request) -> dict:
    """从 Authorization header 解析当前用户。所有需要鉴权的端点使用此依赖。"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "未登录，请先登录")
    token = auth_header[7:]
    from api.auth import decode_token
    return decode_token(token)


def get_user_id(user: dict = Depends(get_current_user)) -> str:
    """快捷依赖：只返回 user_id 字符串。"""
    return user["user_id"]


async def get_session_or_404(session_id: str, db: AsyncSession) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "会话不存在")
    return session


async def assert_session_access(session: Session, user_id: str, db: AsyncSession) -> None:
    if session.is_multiplayer:
        member_result = await db.execute(
            select(SessionMember.id).where(
                SessionMember.session_id == session.id,
                SessionMember.user_id == user_id,
            )
        )
        if member_result.scalar_one_or_none() is None:
            raise HTTPException(403, "user is not a member of this room")
        return
    if not session.user_id:
        raise HTTPException(403, "not authorized for this session")
    if session.user_id != user_id:
        raise HTTPException(403, "not authorized for this session")


async def get_authorized_session(session_id: str, db: AsyncSession, user_id: str) -> Session:
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    return session


async def assert_module_access(
    module: Module,
    user_id: str,
    *,
    require_owner: bool = False,
    allow_shared: bool = True,
) -> None:
    if require_owner:
        if not module.user_id or module.user_id != user_id:
            raise HTTPException(403, "not authorized for this module")
        return
    if module.user_id is None:
        if allow_shared:
            return
        raise HTTPException(403, "not authorized for this module")
    if module.user_id != user_id:
        raise HTTPException(403, "not authorized for this module")


async def get_authorized_module(
    module_id: str,
    db: AsyncSession,
    user_id: str,
    *,
    require_owner: bool = False,
    allow_shared: bool = True,
) -> Module:
    module = await db.get(Module, module_id)
    if not module:
        raise HTTPException(404, "module not found")
    await assert_module_access(
        module,
        user_id,
        require_owner=require_owner,
        allow_shared=allow_shared,
    )
    return module


async def _get_session_member(
    session: Session,
    user_id: str,
    db: AsyncSession,
) -> Optional[SessionMember]:
    result = await db.execute(
        select(SessionMember).where(
            SessionMember.session_id == session.id,
            SessionMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _character_is_bound_to_session(
    character: Character,
    session: Session,
    db: AsyncSession,
) -> bool:
    if character.session_id == session.id:
        return True
    if session.player_character_id and character.id == session.player_character_id:
        return True
    if character.id in ((session.game_state or {}).get("companion_ids") or []):
        return True
    if session.is_multiplayer:
        result = await db.execute(
            select(SessionMember.id).where(
                SessionMember.session_id == session.id,
                SessionMember.character_id == character.id,
            )
        )
        return result.scalar_one_or_none() is not None
    return False


async def assert_character_control(
    character: Character,
    session: Session,
    user_id: str,
    db: AsyncSession,
) -> None:
    if session.is_multiplayer:
        member = await _get_session_member(session, user_id, db)
        if member is None:
            raise HTTPException(403, "user is not a member of this room")
        if not character.is_player or character.user_id is None:
            return
        if character.user_id != user_id:
            raise HTTPException(403, "not authorized for this character")
        if member.character_id != character.id or character.user_id != user_id:
            raise HTTPException(403, "not authorized for this character")
        return

    if not character.is_player:
        return
    if character.user_id and character.user_id != user_id:
        raise HTTPException(403, "not authorized for this character")
    if character.user_id is None and session.player_character_id != character.id:
        raise HTTPException(403, "not authorized for this character")


async def assert_character_access(
    character: Character,
    user_id: str,
    db: AsyncSession,
    *,
    require_control: bool = False,
    session_id: Optional[str] = None,
) -> None:
    if session_id:
        session = await get_authorized_session(session_id, db, user_id)
        if not await _character_is_bound_to_session(character, session, db):
            raise HTTPException(403, "character does not belong to this session")
        if require_control:
            await assert_character_control(character, session, user_id, db)
        return

    if character.session_id:
        session = await get_authorized_session(character.session_id, db, user_id)
        if require_control:
            await assert_character_control(character, session, user_id, db)
        return

    if character.user_id and character.user_id == user_id:
        return

    raise HTTPException(403, "not authorized for this character")


async def get_authorized_character(
    character_id: str,
    db: AsyncSession,
    user_id: str,
    *,
    require_control: bool = False,
    session_id: Optional[str] = None,
) -> Character:
    character = await db.get(Character, character_id)
    if not character:
        raise HTTPException(404, "character not found")
    await assert_character_access(
        character,
        user_id,
        db,
        require_control=require_control,
        session_id=session_id,
    )
    return character


def char_brief(char: Character) -> dict:
    """返回角色的简要信息（用于 DM 上下文构建 + 前端面板渲染）"""
    derived = char.derived or {}
    return {
        "id":               char.id,
        "name":             char.name,
        "race":             char.race,
        "char_class":       char.char_class,
        "level":            char.level,
        "hp_current":       char.hp_current,
        "hp_max":           derived.get("hp_max", char.hp_current),
        "ac":               derived.get("ac", 10),
        "is_player":        char.is_player,
        "spell_slots":      char.spell_slots or {},
        "proficient_skills":char.proficient_skills or [],
        "proficient_saves": char.proficient_saves or [],
        "conditions":       char.conditions or [],
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
    derived = char.derived or {}
    return {
        "id":         char.id,
        "name":       char.name,
        "is_player":  char.is_player and not is_enemy,
        "is_enemy":   is_enemy,
        "hp_current": char.hp_current,
        "hp_max":     derived.get("hp_max", char.hp_current),
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
        char = await db.get(Character, entity_id)
        if char is not None and not await _character_is_bound_to_session(char, session, db):
            raise HTTPException(403, "character does not belong to this session")
        return

    member_result = await db.execute(
        select(SessionMember).where(
            SessionMember.session_id == session.id,
            SessionMember.user_id == user_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if member is None:
        raise HTTPException(403, "你不在该房间")

    char = await db.get(Character, entity_id)
    if char is None:
        raise HTTPException(403, "该实体不能由玩家操作")

    # AI 托管的角色（未被认领或已降级）→ 房间任意成员可触发
    if not char.is_player or char.user_id is None:
        return

    if char.user_id != user_id:
        raise HTTPException(403, "这不是你的角色")

    if require_current_turn and session.combat_active:
        result = await db.execute(
            select(CombatState).where(CombatState.session_id == session.id)
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


async def resolve_controlled_player_character(
    session: Session,
    user_id: str,
    db: AsyncSession,
) -> Character:
    """Resolve the player character controlled by this user in the session."""
    if not session.is_multiplayer:
        if not session.player_character_id:
            raise HTTPException(404, "玩家角色不存在")
        player = await db.get(Character, session.player_character_id)
        if not player:
            raise HTTPException(404, "玩家角色不存在")
        return player

    member_result = await db.execute(
        select(SessionMember).where(
            SessionMember.session_id == session.id,
            SessionMember.user_id == user_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if member is None:
        raise HTTPException(403, "你不在该房间")
    if not member.character_id:
        raise HTTPException(403, "你在该房间没有绑定角色")

    player = await db.get(Character, member.character_id)
    if not player:
        raise HTTPException(404, "玩家角色不存在")
    if player.session_id and player.session_id != session.id:
        raise HTTPException(403, "角色不属于该房间")
    if not player.is_player or player.user_id != user_id:
        raise HTTPException(403, "这不是你的角色")
    return player
