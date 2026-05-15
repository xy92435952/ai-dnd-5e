from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models import Session


async def apply_multiplayer_room_decision(
    *,
    db: AsyncSession,
    session: Session,
    actor_user_id: str,
    multiplayer_decision,
) -> None:
    """Apply multiplayer table room updates and broadcast the fresh room snapshot."""
    if not multiplayer_decision:
        return

    from services import room_service
    from services.ws_manager import ws_manager
    from schemas.ws_events import RoomStateUpdated

    room_info = None
    for group_id in multiplayer_decision.clear_pending_group_ids:
        room_info = await room_service.clear_group_actions(
            db,
            session_id=session.id,
            group_id=group_id,
            actor_user_id=actor_user_id,
        )

    focus_group_id = multiplayer_decision.room_updates.get("active_group_id")
    next_ready_group_id = None
    if room_info:
        next_ready_group_id = find_next_ready_group_id(
            room_info,
            exclude_group_ids=set(multiplayer_decision.clear_pending_group_ids or []),
        )
    if next_ready_group_id:
        focus_group_id = next_ready_group_id

    if focus_group_id:
        room_info = await room_service.set_active_group(
            db,
            session_id=session.id,
            group_id=focus_group_id,
            actor_user_id=actor_user_id,
        )

    if room_info:
        try:
            await ws_manager.broadcast(session.id, RoomStateUpdated(room=room_info))
        except Exception:
            pass


def find_next_ready_group_id(room_info: dict, exclude_group_ids: set[str] | None = None) -> Optional[str]:
    """Pick the next group that has pending actions and every member marked ready."""
    exclude_group_ids = exclude_group_ids or set()
    pending_by_group = room_info.get("pending_actions_by_group") or {}
    readiness_by_group = room_info.get("group_readiness") or {}
    for group in room_info.get("party_groups") or []:
        group_id = group.get("id")
        if not group_id or group_id in exclude_group_ids:
            continue
        if not pending_by_group.get(group_id):
            continue
        member_ids = group.get("member_user_ids") or []
        if not member_ids:
            continue
        readiness = readiness_by_group.get(group_id) or {}
        if all(readiness.get(user_id) == "ready" for user_id in member_ids):
            return group_id
    return None


async def broadcast_multiplayer_table_message(
    *,
    session: Session,
    actor_user_id: str,
    table_message: str,
    table_reason: str = "",
    table_decision: Optional[dict] = None,
    visibility: Optional[dict] = None,
) -> None:
    """Broadcast a table-only Multiplayer DM result to room observers."""
    if not session.is_multiplayer:
        return

    from schemas.ws_events import DMResponded

    try:
        visibility = visibility or {}
        await send_dm_responded_with_visibility(
            session=session,
            visibility=visibility,
            event=DMResponded(
                by_user_id=actor_user_id,
                action_type="multiplayer_table",
                narrative=table_message,
                companion_reactions="",
                dice_display=[],
                combat_triggered=False,
                combat_ended=False,
                visibility=visibility,
                table_reason=table_reason,
                table_decision=table_decision or {},
            ),
        )
    except Exception:
        pass


async def send_dm_responded_with_visibility(
    *,
    session: Session,
    event,
    visibility: Optional[dict] = None,
) -> None:
    """Broadcast a DM response, respecting optional multiplayer visibility."""
    from services.ws_manager import ws_manager

    visibility = visibility or {}
    visible_to = list(visibility.get("visible_to_user_ids") or [])
    scope = visibility.get("scope") or "party"
    if session.is_multiplayer and scope in {"group", "private"} and visible_to:
        for target_user_id in visible_to:
            await ws_manager.send_to_user(session.id, target_user_id, event)
        return
    await ws_manager.broadcast(session.id, event)
