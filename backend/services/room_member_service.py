"""Room membership, character ownership, and presence helpers."""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character, Session, SessionMember, User


OFFLINE_THRESHOLD_SECONDS = 30


async def claim_character(
    db: AsyncSession,
    user_id: str,
    session_id: str,
    character_id: str,
) -> SessionMember:
    """
    认领（或接管）一个角色。允许的场景：

      1) 我自己的角色（重连续玩 / 换角色）—— 直接绑回
      2) "孤儿"角色（session_id 为 None）—— 刚从多人向导创建完，第一次绑
      3) 房间内的 AI 角色（is_player=False）—— 接管：fill_ai 生成的 / 其他玩家
         离开后降级的 / 长时间断线被托管的，都允许在线玩家拿回来玩

    拒绝的场景：
      - 角色属于别的 session
      - 角色已被**别的活跃 SessionMember** 绑（在线 / 离线但还没触发 leave）
    """
    member = await get_member(db, session_id, user_id)
    if not member:
        raise HTTPException(403, "你不在该房间中")

    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")
    if char.session_id is not None and char.session_id != session_id:
        raise HTTPException(404, "角色不属于该房间")

    existing = await db.execute(
        select(SessionMember).where(
            SessionMember.session_id == session_id,
            SessionMember.character_id == character_id,
        )
    )
    other = existing.scalar_one_or_none()
    if other and other.user_id != user_id:
        raise HTTPException(409, "该角色已被其他玩家认领")

    if member.character_id and member.character_id != character_id:
        prev = await db.get(Character, member.character_id)
        if prev:
            prev.user_id = None
            prev.is_player = False

    member.character_id = character_id
    char.user_id = user_id
    char.is_player = True
    char.session_id = session_id
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

    target = await get_member(db, session_id, target_user_id)
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

    actor = await get_member(db, session_id, actor_user_id)
    target = await get_member(db, session_id, new_host_user_id)
    if not target:
        raise HTTPException(404, "目标成员不在房间中")
    if actor.user_id == target.user_id:
        raise HTTPException(400, "目标已是房主")

    actor.role = "player"
    target.role = "host"
    session.host_user_id = new_host_user_id
    await db.commit()
    return {"new_host_user_id": new_host_user_id}


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
        seconds_since_seen = None
        if member.last_seen_at is not None:
            seconds_since_seen = max(0, int((now - member.last_seen_at).total_seconds()))
        out.append({
            "user_id": member.user_id,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "role": member.role,
            "character_id": member.character_id,
            "character_name": char.name if char else None,
            "is_online": member.last_seen_at is not None and member.last_seen_at >= threshold,
            "seconds_since_seen": seconds_since_seen,
            "joined_at": member.joined_at,
        })
    return out


async def update_heartbeat(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> None:
    """更新成员的 last_seen_at（由 WebSocket 心跳调用）"""
    member = await get_member(db, session_id, user_id)
    if member:
        member.last_seen_at = datetime.utcnow()
        await db.commit()


async def mark_offline(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> None:
    """显式断开连接时立即把成员标记为离线。"""
    member = await get_member(db, session_id, user_id)
    if member:
        member.last_seen_at = None
        await db.commit()


async def get_member(
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


async def list_members_raw(
    db: AsyncSession,
    session_id: str,
) -> List[SessionMember]:
    result = await db.execute(
        select(SessionMember)
        .where(SessionMember.session_id == session_id)
        .order_by(SessionMember.joined_at.asc())
    )
    return list(result.scalars().all())


async def count_members(db: AsyncSession, session_id: str) -> int:
    result = await db.execute(
        select(SessionMember).where(SessionMember.session_id == session_id)
    )
    return len(list(result.scalars().all()))
