"""Room code, creation, join, leave, and start-state helpers."""

import random
from datetime import datetime
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.deps import assert_module_access
from models import Character, Module, Session, SessionMember
from services import room_group_service
from services import room_group_state_utils
from services.dm_styles import normalize_dm_style
from services.location_graph_service import build_location_graph_from_module
from services.loot_service import build_loot_pool_from_module
from services.module_content import get_module_content
from services.room_audit_service import add_room_audit_log
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

    assert_module_access(module, user_id)

    code = await generate_unique_room_code(db)
    style_key = normalize_dm_style(dm_style)
    parsed = get_module_content(module)
    location_graph = build_location_graph_from_module(parsed)
    loot_pool = build_loot_pool_from_module(parsed)
    session = Session(
        user_id=user_id,
        module_id=module_id,
        save_name=save_name or f"多人房间 {code}",
        is_multiplayer=True,
        room_code=code,
        host_user_id=user_id,
        max_players=max_players,
        game_state={
            "dm_style": style_key,
            "location_graph": location_graph,
            "loot_pool": loot_pool,
            "multiplayer": {
                "current_speaker_user_id": None,
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
                "group_readiness": {room_group_service.DEFAULT_GROUP_ID: {}},
            },
        },
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
    member = await get_member(db, session.id, user_id)
    if member:
        member.last_seen_at = datetime.utcnow()
        await db.commit()
        await db.refresh(member)
        return session, member

    if is_game_started(session):
        raise HTTPException(409, "游戏已经开始，无法加入")

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

    remaining_members = await _list_remaining_members(db, session.id)
    remaining_user_ids = [item.user_id for item in remaining_members]

    if is_host:
        new_host = remaining_members[0] if remaining_members else None
        if new_host:
            new_host.role = "host"
            session.host_user_id = new_host.user_id
            transfer_to = new_host.user_id
            add_room_audit_log(
                db,
                session_id=session.id,
                event_type="host_transferred",
                actor_user_id=user_id,
                target_user_id=transfer_to,
                details={"reason": "host_left", "previous_host_user_id": user_id},
            )
        else:
            session.room_code = None
            session.host_user_id = None
            transfer_to = None
            add_room_audit_log(
                db,
                session_id=session.id,
                event_type="room_dissolved",
                actor_user_id=user_id,
                target_user_id=user_id,
                details={"reason": "host_left"},
            )
        _prune_room_member_state(
            session,
            removed_user_id=user_id,
            remaining_user_ids=remaining_user_ids,
            preferred_speaker_user_id=transfer_to,
        )
        await db.commit()
        return {"left": user_id, "host_transferred_to": transfer_to,
                "room_dissolved": transfer_to is None}

    _prune_room_member_state(
        session,
        removed_user_id=user_id,
        remaining_user_ids=remaining_user_ids,
    )
    await db.commit()
    return {"left": user_id, "host_transferred_to": None, "room_dissolved": False}

async def _list_remaining_members(db: AsyncSession, session_id: str) -> list[SessionMember]:
    result = await db.execute(
        select(SessionMember)
        .where(SessionMember.session_id == session_id)
        .order_by(SessionMember.joined_at.asc())
    )
    return list(result.scalars().all())


def _prune_room_member_state(
    session: Session,
    *,
    removed_user_id: str,
    remaining_user_ids: list[str],
    preferred_speaker_user_id: Optional[str] = None,
) -> None:
    session.game_state = room_group_state_utils.prune_member_from_multiplayer_state(
        session.game_state,
        removed_user_id,
        remaining_user_ids,
        preferred_speaker_user_id=preferred_speaker_user_id,
    )
    flag_modified(session, "game_state")


def is_game_started(session: Session) -> bool:
    """游戏开始的判定：multiplayer.game_started 为 True，或已有场景/战斗。"""
    state = session.game_state or {}
    if state.get("multiplayer", {}).get("game_started"):
        return True
    return bool(session.current_scene) or bool(session.combat_active)
