from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models import Character, Session, SessionMember
from schemas.ws_events import MemberOffline, RoomDissolved
from services import room_group_state_utils
from services.room_audit_service import add_room_audit_log
from services.room_lifecycle_service import is_game_started
from services.room_member_service import list_members, list_stale_members, mark_offline
from services.ws_manager import ws_manager


async def cleanup_stale_ws_connections(
    db: AsyncSession,
    *,
    stale_after_seconds: int = 30,
) -> list[tuple[str, str]]:
    """Disconnect sockets whose heartbeat is older than the stale window."""
    stale_members = await list_stale_members(db, stale_after_seconds=stale_after_seconds)
    if not stale_members:
        return []

    unique_stale_members: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for session_id, user_id in stale_members:
        key = (session_id, user_id)
        if key in seen:
            continue
        seen.add(key)
        unique_stale_members.append(key)

    await ws_manager.prune_stale_connections(unique_stale_members)

    for session_id, user_id in unique_stale_members:
        await mark_offline(db, session_id, user_id)
        offline_members = await list_members(db, session_id)
        await ws_manager.broadcast(
            session_id,
            MemberOffline(user_id=user_id, members=offline_members),
        )

    return unique_stale_members


async def cleanup_abandoned_waiting_rooms(
    db: AsyncSession,
    *,
    abandoned_after_seconds: int = 120,
) -> list[str]:
    """Dissolve not-started multiplayer rooms after every member has gone stale."""
    threshold = datetime.utcnow() - timedelta(seconds=abandoned_after_seconds)
    result = await db.execute(
        select(Session)
        .where(Session.is_multiplayer.is_(True))
        .where(Session.room_code.is_not(None))
    )
    sessions = list(result.scalars().all())
    dissolved_session_ids: list[str] = []

    for session in sessions:
        if is_game_started(session):
            continue
        if await ws_manager.online_users(session.id):
            continue

        members = await _list_room_members(db, session.id)
        if not members:
            continue
        if not _all_members_abandoned(session, members, threshold):
            continue

        await _dissolve_waiting_room(db, session, members)
        dissolved_session_ids.append(session.id)

    if dissolved_session_ids:
        await db.commit()
        for session_id in dissolved_session_ids:
            await ws_manager.broadcast(
                session_id,
                RoomDissolved(by_user_id="system"),
            )
            await ws_manager.disconnect_room(
                session_id,
                code=4002,
                reason="Room abandoned",
            )

    return dissolved_session_ids


async def _list_room_members(db: AsyncSession, session_id: str) -> list[SessionMember]:
    result = await db.execute(
        select(SessionMember)
        .where(SessionMember.session_id == session_id)
        .order_by(SessionMember.joined_at.asc())
    )
    return list(result.scalars().all())


def _all_members_abandoned(
    session: Session,
    members: list[SessionMember],
    threshold: datetime,
) -> bool:
    offline_at_by_user_id = (
        ((session.game_state or {}).get("multiplayer", {}) or {})
        .get("last_offline_at_by_user_id")
        or {}
    )

    for member in members:
        if member.last_seen_at is not None and member.last_seen_at >= threshold:
            return False
        if member.last_seen_at is None:
            offline_at = (
                _parse_iso_datetime(offline_at_by_user_id.get(member.user_id))
                or member.joined_at
            )
            if offline_at is None or offline_at >= threshold:
                return False
    return True


def _parse_iso_datetime(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value[:-1] if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


async def _dissolve_waiting_room(
    db: AsyncSession,
    session: Session,
    members: list[SessionMember],
) -> None:
    for member in members:
        if member.character_id:
            character = await db.get(Character, member.character_id)
            if character:
                character.user_id = None
                character.is_player = False

    session.room_code = None
    session.host_user_id = None
    session.game_state = room_group_state_utils.prune_member_from_multiplayer_state(
        session.game_state,
        removed_user_id="",
        remaining_user_ids=[],
    )
    mp = dict((session.game_state or {}).get("multiplayer") or {})
    mp["party_groups"] = [{
        "id": room_group_state_utils.DEFAULT_GROUP_ID,
        "name": room_group_state_utils.DEFAULT_GROUP_NAME,
        "location": room_group_state_utils.DEFAULT_GROUP_LOCATION,
        "member_user_ids": [],
    }]
    mp["active_group_id"] = room_group_state_utils.DEFAULT_GROUP_ID
    mp["pending_actions_by_group"] = {room_group_state_utils.DEFAULT_GROUP_ID: []}
    mp["group_readiness"] = {room_group_state_utils.DEFAULT_GROUP_ID: {}}
    mp["pending_actions"] = []
    mp["online_user_ids"] = []
    mp["start_ready_user_ids"] = []
    mp["current_speaker_user_id"] = None
    mp.pop("last_offline_at_by_user_id", None)
    mp.pop("room_votes", None)
    mp.pop("dm_thinking", None)
    session.game_state = {
        **(session.game_state or {}),
        "multiplayer": mp,
    }
    flag_modified(session, "game_state")

    await db.execute(
        delete(SessionMember).where(SessionMember.session_id == session.id)
    )
    add_room_audit_log(
        db,
        session_id=session.id,
        event_type="room_dissolved",
        actor_user_id="system",
        details={
            "reason": "abandoned_room_cleanup",
            "member_count": len(members),
        },
    )
