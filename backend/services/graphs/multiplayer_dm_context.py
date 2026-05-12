"""Context helpers for Multiplayer DM coordination."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from models import Session, User
from services import room_service


async def build_multiplayer_dm_context(db: AsyncSession, session: Session, actor_user_id: str) -> dict:
    """Build a normalized table-state snapshot for Multiplayer DM v1."""
    room = await room_service.get_room_info(db, session.id)
    groups = room.get("party_groups") or []
    pending_by_group = room.get("pending_actions_by_group") or {}
    group_readiness = room.get("group_readiness") or {}
    actor_group = next(
        (group for group in groups if actor_user_id in (group.get("member_user_ids") or [])),
        None,
    )
    active_group = next(
        (group for group in groups if group.get("id") == room.get("active_group_id")),
        None,
    )
    focus_group = actor_group or active_group or (groups[0] if groups else None)
    focus_group_id = focus_group.get("id") if focus_group else None
    actor_user = await db.get(User, actor_user_id)
    members_by_user_id = {
        member.get("user_id"): member
        for member in room.get("members") or []
        if member.get("user_id")
    }

    return {
        "room": room,
        "groups": groups,
        "pending_by_group": pending_by_group,
        "group_readiness": group_readiness,
        "actor_user_id": actor_user_id,
        "actor_display_name": (actor_user.display_name or actor_user.username) if actor_user else actor_user_id,
        "members_by_user_id": members_by_user_id,
        "actor_group": actor_group,
        "active_group": active_group,
        "focus_group": focus_group,
        "focus_group_id": focus_group_id,
        "focus_pending_actions": list(pending_by_group.get(focus_group_id, [])) if focus_group_id else [],
        "other_pending_counts": {
            group.get("id"): len(pending_by_group.get(group.get("id"), []))
            for group in groups
            if group.get("id") != focus_group_id and pending_by_group.get(group.get("id"))
        },
    }
