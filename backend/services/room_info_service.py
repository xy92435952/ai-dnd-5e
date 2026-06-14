"""Aggregated room info for multiplayer lobby and exploration UI."""

from copy import deepcopy
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import Session
from services.dm_styles import serialize_dm_style
from services.room_ai_companion_service import list_ai_companions
from services.room_group_service import ensure_multiplayer_state
from services.room_lifecycle_service import is_game_started
from services.room_member_service import list_members
from services.room_start_service import get_start_ready_user_ids
from services.room_vote_service import ensure_room_votes


async def get_room_info(
    db: AsyncSession,
    session_id: str,
    viewer_user_id: Optional[str] = None,
) -> dict:
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    mp_state = await ensure_multiplayer_state(db, session_id)
    room_votes = await ensure_room_votes(db, session_id)
    members = await list_members(db, session_id)
    ai_companions = await list_ai_companions(db, session_id)
    mp = (session.game_state or {}).get("multiplayer", {})
    room = {
        "session_id": session.id,
        "room_code": session.room_code,
        "module_id": session.module_id,
        "save_name": session.save_name,
        "host_user_id": session.host_user_id,
        "max_players": session.max_players,
        "is_multiplayer": session.is_multiplayer,
        "game_started": is_game_started(session),
        "members": members,
        "ai_companions": ai_companions,
        "current_speaker_user_id": mp.get("current_speaker_user_id"),
        "dm_thinking": mp.get("dm_thinking"),
        "speak_round": mp.get("speak_round", 0),
        "party_groups": mp_state["party_groups"],
        "active_group_id": mp_state["active_group_id"],
        "pending_actions_by_group": mp_state["pending_actions_by_group"],
        "group_readiness": mp_state["group_readiness"],
        "room_votes": room_votes,
        "start_ready_user_ids": get_start_ready_user_ids(session, members),
        "dm_style": serialize_dm_style((session.game_state or {}).get("dm_style")),
        "created_at": session.created_at,
    }
    return project_room_info_for_viewer(room, viewer_user_id=viewer_user_id)


def project_room_info_for_viewer(
    room: dict,
    *,
    viewer_user_id: Optional[str] = None,
) -> dict:
    """Return a player-facing room snapshot for one connected viewer."""
    if not isinstance(room, dict):
        return room
    projected = dict(room)
    groups = projected.get("party_groups") or []
    projected["pending_actions_by_group"] = project_pending_actions_for_viewer(
        projected.get("pending_actions_by_group") or {},
        groups,
        viewer_user_id=viewer_user_id,
    )
    projected["dm_thinking"] = project_dm_thinking_for_viewer(
        projected.get("dm_thinking"),
        groups,
        viewer_user_id=viewer_user_id,
    )
    return projected


def project_pending_actions_for_viewer(
    pending_actions_by_group: dict,
    party_groups: list[dict],
    *,
    viewer_user_id: Optional[str] = None,
) -> dict:
    if not isinstance(pending_actions_by_group, dict):
        return {}
    if not viewer_user_id:
        return deepcopy(pending_actions_by_group)

    projected: dict = {}
    for group_id, actions in pending_actions_by_group.items():
        action_list = list(actions or [])
        if _viewer_in_group(party_groups, viewer_user_id, str(group_id)):
            projected[group_id] = deepcopy(action_list)
            continue
        projected[group_id] = [
            _redacted_group_action(action, str(group_id))
            for action in action_list
            if isinstance(action, dict)
        ]
    return projected


def project_dm_thinking_for_viewer(
    dm_thinking: dict | None,
    party_groups: list[dict],
    *,
    viewer_user_id: Optional[str] = None,
) -> dict | None:
    if not dm_thinking:
        return None
    if not isinstance(dm_thinking, dict):
        return dm_thinking

    snapshot = deepcopy(dm_thinking)
    group_id = snapshot.get("group_id") or _group_id_for_user(
        party_groups,
        snapshot.get("by_user_id"),
    )
    if group_id:
        snapshot["group_id"] = group_id

    if (
        not viewer_user_id
        or not group_id
        or _viewer_in_group(party_groups, viewer_user_id, str(group_id))
    ):
        snapshot["redacted"] = False
        snapshot.pop("visibility", None)
        return snapshot

    return {
        "active": snapshot.get("active", True),
        "by_user_id": snapshot.get("by_user_id"),
        "started_at": snapshot.get("started_at"),
        "group_id": group_id,
        "redacted": True,
        "visibility": "other_group",
        "action_text": "Action text hidden for another group.",
    }


def _redacted_group_action(action: dict, group_id: str) -> dict:
    placeholder = {
        "redacted": True,
        "visibility": "other_group",
        "group_id": group_id,
    }
    if action.get("created_at"):
        placeholder["created_at"] = action.get("created_at")
    return placeholder


def _viewer_in_group(
    party_groups: list[dict],
    viewer_user_id: str,
    group_id: str,
) -> bool:
    viewer_id = str(viewer_user_id)
    for group in party_groups or []:
        if str(group.get("id")) != str(group_id):
            continue
        return viewer_id in {str(uid) for uid in group.get("member_user_ids") or []}
    return False


def _group_id_for_user(
    party_groups: list[dict],
    user_id: Optional[str],
) -> Optional[str]:
    if user_id is None:
        return None
    target = str(user_id)
    for group in party_groups or []:
        if target in {str(uid) for uid in group.get("member_user_ids") or []}:
            group_id = group.get("id")
            return str(group_id) if group_id else None
    return None
