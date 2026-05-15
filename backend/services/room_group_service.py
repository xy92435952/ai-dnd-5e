"""Multiplayer room group state service.

Keeps exploration split-party state separate from room membership and host actions.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models import Session, SessionMember, User

DEFAULT_GROUP_ID = "main"
DEFAULT_GROUP_NAME = "主队"
DEFAULT_GROUP_LOCATION = "当前场景"
READINESS_STATUSES = {"drafting", "ready", "waiting"}


async def ensure_multiplayer_state(
    db: AsyncSession,
    session_id: str,
) -> dict:
    """Normalize and return the multiplayer exploration group state."""
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")

    members = await _list_members_raw(db, session_id)
    member_ids = [member.user_id for member in members]
    member_id_set = set(member_ids)

    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    groups = _normalize_party_groups(mp.get("party_groups"), member_ids)
    pending = _normalize_group_actions(mp.get("pending_actions_by_group"), groups)
    readiness = _normalize_group_readiness(mp.get("group_readiness"), groups, member_id_set)

    active_group_id = mp.get("active_group_id") or DEFAULT_GROUP_ID
    if active_group_id not in {group["id"] for group in groups}:
        active_group_id = groups[0]["id"] if groups else DEFAULT_GROUP_ID

    mp["party_groups"] = groups
    mp["active_group_id"] = active_group_id
    mp["pending_actions_by_group"] = pending
    mp["group_readiness"] = readiness
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
    return {
        "party_groups": groups,
        "active_group_id": active_group_id,
        "pending_actions_by_group": pending,
        "group_readiness": readiness,
    }


async def set_member_group(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    group_id: str,
    group_name: Optional[str] = None,
    location: Optional[str] = None,
) -> None:
    """Move a member into an exploration group, creating the group if needed."""
    member = await _get_member(db, session_id, user_id)
    if not member:
        raise HTTPException(403, "你不在该房间中")

    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")

    clean_group_id = clean_group_id_value(group_id)
    clean_name = (group_name or "").strip() or (DEFAULT_GROUP_NAME if clean_group_id == DEFAULT_GROUP_ID else clean_group_id)
    clean_location = (location or "").strip() or DEFAULT_GROUP_LOCATION

    await ensure_multiplayer_state(db, session_id)
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    groups = list(mp.get("party_groups") or [])
    pending = dict(mp.get("pending_actions_by_group") or {})
    readiness = dict(mp.get("group_readiness") or {})

    target = None
    for group in groups:
        group["member_user_ids"] = [
            uid for uid in group.get("member_user_ids", [])
            if uid != user_id
        ]
        if group.get("id") == clean_group_id:
            target = group

    if target is None:
        target = {
            "id": clean_group_id,
            "name": clean_name,
            "location": clean_location,
            "member_user_ids": [],
        }
        groups.append(target)
    else:
        target["name"] = clean_name
        target["location"] = clean_location

    target["member_user_ids"] = _unique_preserve_order([
        *target.get("member_user_ids", []),
        user_id,
    ])
    groups = _drop_empty_non_default_groups(groups)
    pending.setdefault(clean_group_id, [])

    mp["party_groups"] = groups
    mp["pending_actions_by_group"] = {
        group["id"]: list(pending.get(group["id"], []))
        for group in groups
    }
    mp["group_readiness"] = {
        group["id"]: {
            uid: status
            for uid, status in dict(readiness.get(group["id"], {})).items()
            if uid in (group.get("member_user_ids") or [])
        }
        for group in groups
    }
    mp["group_readiness"].setdefault(clean_group_id, {})
    mp["group_readiness"][clean_group_id][user_id] = "drafting"
    mp["active_group_id"] = clean_group_id
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()


async def submit_group_action(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    group_id: str,
    action_text: str,
) -> None:
    """Append an exploration action intent to the user's current group."""
    text = (action_text or "").strip()
    if not text:
        raise HTTPException(400, "行动内容不能为空")
    if len(text) > 500:
        raise HTTPException(400, "行动内容过长")

    member = await _get_member(db, session_id, user_id)
    if not member:
        raise HTTPException(403, "你不在该房间中")

    user = await db.get(User, user_id)
    clean_group_id = clean_group_id_value(group_id)
    await ensure_multiplayer_state(db, session_id)

    session = await db.get(Session, session_id)
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    groups = list(mp.get("party_groups") or [])
    group = next((item for item in groups if item.get("id") == clean_group_id), None)
    if not group:
        raise HTTPException(404, "分队不存在")
    if user_id not in (group.get("member_user_ids") or []):
        raise HTTPException(403, "你不在该分队中")

    pending = dict(mp.get("pending_actions_by_group") or {})
    readiness = dict(mp.get("group_readiness") or {})
    actions = list(pending.get(clean_group_id) or [])
    actions.append({
        "user_id": user_id,
        "display_name": (user.display_name or user.username) if user else user_id,
        "text": text,
        "created_at": datetime.utcnow().isoformat(),
    })
    pending[clean_group_id] = actions[-20:]
    group_readiness = dict(readiness.get(clean_group_id) or {})
    group_readiness[user_id] = "drafting"
    readiness[clean_group_id] = group_readiness

    mp["pending_actions_by_group"] = pending
    mp["group_readiness"] = readiness
    mp["active_group_id"] = clean_group_id
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()


async def set_group_readiness(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    group_id: str,
    status: str,
) -> None:
    """Set a member's readiness marker inside a group."""
    clean_status = (status or "").strip().lower()
    if clean_status not in READINESS_STATUSES:
        raise HTTPException(400, "无效的分队准备状态")

    member = await _get_member(db, session_id, user_id)
    if not member:
        raise HTTPException(403, "你不在该房间中")

    clean_group_id = clean_group_id_value(group_id)
    await ensure_multiplayer_state(db, session_id)

    session = await db.get(Session, session_id)
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    groups = list(mp.get("party_groups") or [])
    group = next((item for item in groups if item.get("id") == clean_group_id), None)
    if not group:
        raise HTTPException(404, "分队不存在")
    if user_id not in (group.get("member_user_ids") or []):
        raise HTTPException(403, "你不在该分队中")

    readiness = dict(mp.get("group_readiness") or {})
    group_readiness = dict(readiness.get(clean_group_id) or {})
    group_readiness[user_id] = clean_status
    readiness[clean_group_id] = group_readiness

    mp["group_readiness"] = readiness
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()


async def set_active_group(
    db: AsyncSession,
    session_id: str,
    group_id: str,
    actor_user_id: Optional[str] = None,
) -> None:
    """Switch the active exploration focus group without moving members."""
    if actor_user_id is not None:
        member = await _get_member(db, session_id, actor_user_id)
        if not member:
            raise HTTPException(403, "你不在该房间中")

    clean_group_id = clean_group_id_value(group_id)
    await ensure_multiplayer_state(db, session_id)

    session = await db.get(Session, session_id)
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    group_ids = {group["id"] for group in mp.get("party_groups") or []}
    if clean_group_id not in group_ids:
        raise HTTPException(404, "分队不存在")

    mp["active_group_id"] = clean_group_id
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()


async def clear_group_actions(
    db: AsyncSession,
    session_id: str,
    group_id: str,
    actor_user_id: Optional[str] = None,
) -> None:
    """Clear pending action intents for an exploration group."""
    if actor_user_id is not None:
        member = await _get_member(db, session_id, actor_user_id)
        if not member:
            raise HTTPException(403, "你不在该房间中")

    clean_group_id = clean_group_id_value(group_id)
    await ensure_multiplayer_state(db, session_id)

    session = await db.get(Session, session_id)
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    pending = dict(mp.get("pending_actions_by_group") or {})
    readiness = dict(mp.get("group_readiness") or {})
    pending[clean_group_id] = []
    readiness[clean_group_id] = {}

    mp["pending_actions_by_group"] = pending
    mp["group_readiness"] = readiness
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()


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
) -> list[SessionMember]:
    result = await db.execute(
        select(SessionMember)
        .where(SessionMember.session_id == session_id)
        .order_by(SessionMember.joined_at.asc())
    )
    return list(result.scalars().all())


def clean_group_id_value(group_id: Optional[str]) -> str:
    clean = "".join(
        ch for ch in (group_id or DEFAULT_GROUP_ID).strip().lower()
        if ch.isalnum() or ch in {"_", "-"}
    )
    return clean[:40] or DEFAULT_GROUP_ID


def _normalize_party_groups(raw_groups, member_ids: list[str]) -> list[dict]:
    member_id_set = set(member_ids)
    groups: list[dict] = []
    assigned: set[str] = set()

    if isinstance(raw_groups, list):
        for raw in raw_groups:
            if not isinstance(raw, dict):
                continue
            group_id = clean_group_id_value(raw.get("id"))
            members = [
                uid for uid in _unique_preserve_order(raw.get("member_user_ids") or [])
                if uid in member_id_set and uid not in assigned
            ]
            assigned.update(members)
            groups.append({
                "id": group_id,
                "name": (raw.get("name") or (DEFAULT_GROUP_NAME if group_id == DEFAULT_GROUP_ID else group_id)).strip(),
                "location": (raw.get("location") or DEFAULT_GROUP_LOCATION).strip(),
                "member_user_ids": members,
            })

    if not groups:
        groups = [{
            "id": DEFAULT_GROUP_ID,
            "name": DEFAULT_GROUP_NAME,
            "location": DEFAULT_GROUP_LOCATION,
            "member_user_ids": [],
        }]

    main = next((group for group in groups if group["id"] == DEFAULT_GROUP_ID), None)
    if main is None:
        main = {
            "id": DEFAULT_GROUP_ID,
            "name": DEFAULT_GROUP_NAME,
            "location": DEFAULT_GROUP_LOCATION,
            "member_user_ids": [],
        }
        groups.insert(0, main)

    missing = [uid for uid in member_ids if uid not in assigned]
    main["member_user_ids"] = _unique_preserve_order([
        *main.get("member_user_ids", []),
        *missing,
    ])
    return _drop_empty_non_default_groups(groups)


def _normalize_group_actions(raw_pending, groups: list[dict]) -> dict:
    group_ids = [group["id"] for group in groups]
    pending = raw_pending if isinstance(raw_pending, dict) else {}
    normalized = {}
    for group_id in group_ids:
        actions = pending.get(group_id) if isinstance(pending, dict) else []
        normalized[group_id] = [
            action for action in (actions or [])
            if isinstance(action, dict) and action.get("text")
        ][-20:]
    return normalized


def _normalize_group_readiness(raw_readiness, groups: list[dict], member_id_set: set[str]) -> dict:
    readiness = raw_readiness if isinstance(raw_readiness, dict) else {}
    normalized = {}
    for group in groups:
        group_id = group["id"]
        member_ids = set(group.get("member_user_ids") or [])
        raw_group = readiness.get(group_id) if isinstance(readiness, dict) else {}
        if not isinstance(raw_group, dict):
            raw_group = {}
        normalized[group_id] = {
            uid: status
            for uid, status in raw_group.items()
            if uid in member_id_set
            and uid in member_ids
            and status in READINESS_STATUSES
        }
    return normalized


def _drop_empty_non_default_groups(groups: list[dict]) -> list[dict]:
    kept = [
        group for group in groups
        if group.get("id") == DEFAULT_GROUP_ID or group.get("member_user_ids")
    ]
    if not kept:
        return [{
            "id": DEFAULT_GROUP_ID,
            "name": DEFAULT_GROUP_NAME,
            "location": DEFAULT_GROUP_LOCATION,
            "member_user_ids": [],
        }]
    return kept


def _unique_preserve_order(values) -> list:
    out = []
    seen = set()
    for value in values or []:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
