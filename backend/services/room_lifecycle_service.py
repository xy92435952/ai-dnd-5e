"""Room code, creation, join, leave, and start-state helpers."""

import random
from datetime import datetime
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character, Module, Session, SessionMember
from services import room_group_service
from services.dm_styles import normalize_dm_style
from services.room_member_service import count_members, get_member


ROOM_CODE_CHARS = "23456789"
ROOM_CODE_LENGTH = 6
MAX_CODE_GEN_ATTEMPTS = 20


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


async def create_room(
    db: AsyncSession,
    user_id: str,
    module_id: str,
    save_name: Optional[str],
    max_players: int,
    dm_style: Optional[str] = None,
) -> Session:
    """创建多人房间。创建者自动成为 host。"""
    module = await db.get(Module, module_id)
    if not module:
        raise HTTPException(404, "模组不存在")

    code = await generate_unique_room_code(db)
    style_key = normalize_dm_style(dm_style)
    session = Session(
        user_id=user_id,
        module_id=module_id,
        save_name=save_name or f"多人房间 {code}",
        is_multiplayer=True,
        room_code=code,
        host_user_id=user_id,
        max_players=max_players,
        game_state={"dm_style": style_key,
                    "multiplayer": {"current_speaker_user_id": None,
                                     "speak_round": 0,
                                     "pending_actions": [],
                                     "online_user_ids": [user_id],
                                     "active_group_id": room_group_service.DEFAULT_GROUP_ID,
                                     "party_groups": [{
                                         "id": room_group_service.DEFAULT_GROUP_ID,
                                         "name": room_group_service.DEFAULT_GROUP_NAME,
                                         "location": room_group_service.DEFAULT_GROUP_LOCATION,
                                         "member_user_ids": [user_id],
                                     }],
                                     "pending_actions_by_group": {room_group_service.DEFAULT_GROUP_ID: []},
                                     "group_readiness": {room_group_service.DEFAULT_GROUP_ID: {}}}},
    )
    db.add(session)
    await db.flush()

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
    if is_game_started(session):
        raise HTTPException(409, "游戏已经开始，无法加入")

    member = await get_member(db, session.id, user_id)
    if member:
        member.last_seen_at = datetime.utcnow()
        await db.commit()
        await db.refresh(member)
        return session, member

    members_count = await count_members(db, session.id)
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
    """离开房间，并在房主离开时转让房主或归档空房间。"""
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")

    member = await get_member(db, session.id, user_id)
    if not member:
        raise HTTPException(404, "你不在该房间中")

    is_host = member.role == "host"

    if member.character_id:
        char = await db.get(Character, member.character_id)
        if char:
            char.user_id = None
            char.is_player = False
    await db.delete(member)
    await db.flush()

    if is_host:
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
            session.room_code = None
            transfer_to = None
        await db.commit()
        return {"left": user_id, "host_transferred_to": transfer_to,
                "room_dissolved": transfer_to is None}

    await db.commit()
    return {"left": user_id, "host_transferred_to": None, "room_dissolved": False}


def is_game_started(session: Session) -> bool:
    """游戏开始的判定：multiplayer.game_started 为 True，或已有场景/战斗。"""
    state = session.game_state or {}
    if state.get("multiplayer", {}).get("game_started"):
        return True
    return bool(session.current_scene) or bool(session.combat_active)
