"""多人联机房间业务逻辑

职责：
- 房间码生成（避免易混淆字符 0/O/1/I）
- 创建/加入/离开/解散房间
- 成员管理（角色认领、踢人、转让房主）
- 在线状态判断（基于 last_seen_at 心跳）

不负责：
- WebSocket 广播（由 ws_manager 处理）
- 战斗权限校验（由 combat 端点中间件处理）
"""
import random
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models import Session, Character, SessionMember, User


# ── 常量 ─────────────────────────────────────────────

ROOM_CODE_CHARS = "23456789"  # 8进制，去掉 0/1 易混字符
ROOM_CODE_LENGTH = 6
OFFLINE_THRESHOLD_SECONDS = 30  # 超过 30s 无心跳 → 视为离线 → AI 托管
MAX_CODE_GEN_ATTEMPTS = 20


# ── 房间码生成 ───────────────────────────────────────

async def generate_unique_room_code(db: AsyncSession) -> str:
    """生成 6 位数字房间码，确保数据库内唯一。"""
    for _ in range(MAX_CODE_GEN_ATTEMPTS):
        code = "".join(random.choices(ROOM_CODE_CHARS, k=ROOM_CODE_LENGTH))
        existing = await db.execute(
            select(Session.id).where(Session.room_code == code)
        )
        if existing.scalar_one_or_none() is None:
            return code
    raise HTTPException(500, "房间码生成失败，请重试")


# ── 创建/加入/离开 ───────────────────────────────────

async def create_room(
    db: AsyncSession,
    user_id: str,
    module_id: str,
    save_name: Optional[str],
    max_players: int,
) -> Session:
    """创建多人房间。创建者自动成为 host。"""
    # 验证模组存在
    from models import Module
    module = await db.get(Module, module_id)
    if not module:
        raise HTTPException(404, "模组不存在")

    code = await generate_unique_room_code(db)
    session = Session(
        user_id=user_id,
        module_id=module_id,
        save_name=save_name or f"多人房间 {code}",
        is_multiplayer=True,
        room_code=code,
        host_user_id=user_id,
        max_players=max_players,
        game_state={"multiplayer": {"current_speaker_user_id": None,
                                     "speak_round": 0,
                                     "pending_actions": [],
                                     "online_user_ids": [user_id]}},
    )
    db.add(session)
    await db.flush()  # 拿到 session.id

    host_member = SessionMember(
        session_id=session.id,
        user_id=user_id,
        role="host",
    )
    db.add(host_member)
    await db.commit()
    await db.refresh(session)
    return session


async def join_room(
    db: AsyncSession,
    user_id: str,
    room_code: str,
) -> Tuple[Session, SessionMember]:
    """通过房间码加入房间。游戏未开始 + 房间未满 才允许加入。"""
    result = await db.execute(
        select(Session).where(Session.room_code == room_code)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "房间码无效")
    if not session.is_multiplayer:
        raise HTTPException(400, "该房间不是多人房间")
    if _is_game_started(session):
        raise HTTPException(409, "游戏已经开始，无法加入")

    # 检查是否已在房间中
    existing = await db.execute(
        select(SessionMember).where(
            SessionMember.session_id == session.id,
            SessionMember.user_id == user_id,
        )
    )
    member = existing.scalar_one_or_none()
    if member:
        # 已在房间，刷新 last_seen 当作"重连"
        member.last_seen_at = datetime.utcnow()
        await db.commit()
        await db.refresh(member)
        return session, member

    # 检查房间容量
    members_count = await _count_members(db, session.id)
    if members_count >= session.max_players:
        raise HTTPException(409, "房间已满")

    member = SessionMember(
        session_id=session.id,
        user_id=user_id,
        role="player",
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return session, member


async def leave_room(
    db: AsyncSession,
    user_id: str,
    session_id: str,
) -> dict:
    """离开房间。

    - 房主离开 + 还有其他成员 → 自动转让给最早加入的成员
    - 房主离开 + 没有其他成员 → 解散房间（清理 session_members，session 保留以归档）
    - 普通成员离开 → 仅删除 SessionMember 记录；其角色会变为 NPC（is_player=False）
    """
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")

    member = await _get_member(db, session.id, user_id)
    if not member:
        raise HTTPException(404, "你不在该房间中")

    is_host = member.role == "host"

    # 删除该成员
    if member.character_id:
        # 真人角色降级为 AI 托管（is_player=False，user_id 清空）
        char = await db.get(Character, member.character_id)
        if char:
            char.user_id = None
            char.is_player = False
    await db.delete(member)
    await db.flush()

    if is_host:
        # 找下一位最早加入者作为新 host
        result = await db.execute(
            select(SessionMember)
            .where(SessionMember.session_id == session.id)
            .order_by(SessionMember.joined_at.asc())
        )
        new_host = result.scalars().first()
        if new_host:
            new_host.role = "host"
            session.host_user_id = new_host.user_id
            transfer_to = new_host.user_id
        else:
            # 房间空了，归档：room_code 失效，保留 session 数据
            session.room_code = None
            transfer_to = None
        await db.commit()
        return {"left": user_id, "host_transferred_to": transfer_to,
                "room_dissolved": transfer_to is None}

    await db.commit()
    return {"left": user_id, "host_transferred_to": None, "room_dissolved": False}


# ── 角色认领/踢人/转让 ───────────────────────────────

async def claim_character(
    db: AsyncSession,
    user_id: str,
    session_id: str,
    character_id: str,
) -> SessionMember:
    """认领一个角色。角色必须属于本 session 且 is_player=True 且未被其他成员认领。"""
    member = await _get_member(db, session_id, user_id)
    if not member:
        raise HTTPException(403, "你不在该房间中")

    char = await db.get(Character, character_id)
    if not char or char.session_id != session_id:
        raise HTTPException(404, "角色不存在或不属于该房间")
    if not char.is_player:
        raise HTTPException(400, "AI 队友角色不能被认领")

    # 检查是否已被他人认领
    existing = await db.execute(
        select(SessionMember).where(
            SessionMember.session_id == session_id,
            SessionMember.character_id == character_id,
        )
    )
    other = existing.scalar_one_or_none()
    if other and other.user_id != user_id:
        raise HTTPException(409, "该角色已被其他玩家认领")

    member.character_id = character_id
    char.user_id = user_id
    char.is_player = True
    await db.commit()
    await db.refresh(member)
    return member


async def kick_member(
    db: AsyncSession,
    actor_user_id: str,
    session_id: str,
    target_user_id: str,
) -> dict:
    """房主踢人。"""
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    if session.host_user_id != actor_user_id:
        raise HTTPException(403, "只有房主可以踢人")
    if target_user_id == actor_user_id:
        raise HTTPException(400, "不能踢出自己，请使用离开房间")

    target = await _get_member(db, session_id, target_user_id)
    if not target:
        raise HTTPException(404, "目标成员不在房间中")

    if target.character_id:
        char = await db.get(Character, target.character_id)
        if char:
            char.user_id = None
            char.is_player = False

    await db.delete(target)
    await db.commit()
    return {"kicked": target_user_id}


async def transfer_host(
    db: AsyncSession,
    actor_user_id: str,
    session_id: str,
    new_host_user_id: str,
) -> dict:
    """转让房主权限。"""
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    if session.host_user_id != actor_user_id:
        raise HTTPException(403, "只有房主可以转让")

    actor = await _get_member(db, session_id, actor_user_id)
    target = await _get_member(db, session_id, new_host_user_id)
    if not target:
        raise HTTPException(404, "目标成员不在房间中")
    if actor.user_id == target.user_id:
        raise HTTPException(400, "目标已是房主")

    actor.role = "player"
    target.role = "host"
    session.host_user_id = new_host_user_id
    await db.commit()
    return {"new_host_user_id": new_host_user_id}


# ── 开始游戏 ─────────────────────────────────────────

async def start_game(
    db: AsyncSession,
    actor_user_id: str,
    session_id: str,
) -> Session:
    """房主开始游戏。

    要求：
    - 至少 1 名成员已认领角色（其余空位将由 AI 托管）
    - 游戏尚未开始
    """
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    if session.host_user_id != actor_user_id:
        raise HTTPException(403, "只有房主可以开始游戏")
    if _is_game_started(session):
        raise HTTPException(409, "游戏已经开始")

    members = await _list_members_raw(db, session_id)
    claimed = [m for m in members if m.character_id]
    if not claimed:
        raise HTTPException(400, "至少需要一位玩家认领角色才能开始")

    # 标记游戏已开始：在 game_state 写一个 flag
    state = session.game_state or {}
    mp = state.setdefault("multiplayer", {})
    mp["game_started"] = True
    mp["online_user_ids"] = [m.user_id for m in members]
    # 初始发言者：第一位 claimed 玩家
    mp["current_speaker_user_id"] = claimed[0].user_id
    mp["speak_round"] = 1
    mp["pending_actions"] = []
    session.game_state = state

    await db.commit()
    await db.refresh(session)
    return session


# ── 查询 ─────────────────────────────────────────────

async def list_members(
    db: AsyncSession,
    session_id: str,
) -> List[dict]:
    """返回成员列表，包含 user 信息、character 名称、在线状态。"""
    rows = await db.execute(
        select(SessionMember, User, Character)
        .join(User, User.id == SessionMember.user_id)
        .outerjoin(Character, Character.id == SessionMember.character_id)
        .where(SessionMember.session_id == session_id)
        .order_by(SessionMember.joined_at.asc())
    )
    out = []
    now = datetime.utcnow()
    threshold = now - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS)
    for member, user, char in rows.all():
        out.append({
            "user_id": member.user_id,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "role": member.role,
            "character_id": member.character_id,
            "character_name": char.name if char else None,
            "is_online": member.last_seen_at is not None and member.last_seen_at >= threshold,
            "joined_at": member.joined_at,
        })
    return out


async def get_room_info(
    db: AsyncSession,
    session_id: str,
) -> dict:
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    members = await list_members(db, session_id)
    mp = (session.game_state or {}).get("multiplayer", {})
    return {
        "session_id": session.id,
        "room_code": session.room_code,
        "module_id": session.module_id,
        "save_name": session.save_name,
        "host_user_id": session.host_user_id,
        "max_players": session.max_players,
        "is_multiplayer": session.is_multiplayer,
        "game_started": _is_game_started(session),
        "members": members,
        "current_speaker_user_id": mp.get("current_speaker_user_id"),
        "speak_round": mp.get("speak_round", 0),
        "created_at": session.created_at,
    }


# ── 心跳 ─────────────────────────────────────────────

async def update_heartbeat(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> None:
    """更新成员的 last_seen_at（由 WebSocket 心跳调用）"""
    member = await _get_member(db, session_id, user_id)
    if member:
        member.last_seen_at = datetime.utcnow()
        await db.commit()


# ── 内部工具 ─────────────────────────────────────────

def _is_game_started(session: Session) -> bool:
    """游戏开始的判定：multiplayer.game_started 为 True，
    或者已有 current_scene/combat_active（向后兼容）"""
    state = session.game_state or {}
    if state.get("multiplayer", {}).get("game_started"):
        return True
    return bool(session.current_scene) or bool(session.combat_active)


async def _get_member(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> Optional[SessionMember]:
    result = await db.execute(
        select(SessionMember).where(
            SessionMember.session_id == session_id,
            SessionMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _list_members_raw(
    db: AsyncSession,
    session_id: str,
) -> List[SessionMember]:
    result = await db.execute(
        select(SessionMember)
        .where(SessionMember.session_id == session_id)
        .order_by(SessionMember.joined_at.asc())
    )
    return list(result.scalars().all())


async def _count_members(db: AsyncSession, session_id: str) -> int:
    result = await db.execute(
        select(SessionMember).where(SessionMember.session_id == session_id)
    )
    return len(list(result.scalars().all()))
