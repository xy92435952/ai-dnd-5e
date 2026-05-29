from sqlalchemy.ext.asyncio import AsyncSession

from schemas.ws_events import MemberOffline
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
