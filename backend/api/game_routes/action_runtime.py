from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import CombatState, GameLog, SessionMember


async def broadcast_dm_thinking(
    session_id: str,
    user_id: str,
    action_text: str,
    *,
    dm_thinking: dict | None = None,
    party_groups: list[dict] | None = None,
) -> None:
    try:
        from schemas.ws_events import DMThinkingStart
        from services.room_info_service import project_dm_thinking_for_viewer
        from services.ws_manager import ws_manager

        snapshot = dict(dm_thinking or {})
        snapshot.setdefault("active", True)
        snapshot.setdefault("by_user_id", user_id)
        snapshot.setdefault("action_text", action_text[:80])
        groups = party_groups or []
        online_users = await ws_manager.online_users(session_id)
        if online_users and groups:
            for viewer_user_id in online_users:
                projected = project_dm_thinking_for_viewer(
                    snapshot,
                    groups,
                    viewer_user_id=viewer_user_id,
                )
                await ws_manager.send_to_user(
                    session_id,
                    viewer_user_id,
                    DMThinkingStart(
                        by_user_id=projected.get("by_user_id") or user_id,
                        action_text=projected.get("action_text", ""),
                        redacted=bool(projected.get("redacted")),
                        visibility=projected.get("visibility"),
                        group_id=projected.get("group_id"),
                        started_at=projected.get("started_at"),
                    ),
                )
            return

        await ws_manager.broadcast(
            session_id,
            DMThinkingStart(
                by_user_id=snapshot.get("by_user_id") or user_id,
                action_text=snapshot.get("action_text", action_text[:80]),
                redacted=False,
                group_id=snapshot.get("group_id"),
                started_at=snapshot.get("started_at"),
            ),
        )
    except Exception:
        pass


async def maybe_block_combat_input(
    *,
    db: AsyncSession,
    session_id: str,
    action_text: str,
    action_source: str,
) -> Optional[dict]:
    from services.input_guard import classify_player_input

    guard = await classify_player_input(action_text, source=action_source)
    if guard["verdict"] not in ("off_topic", "rule_violation", "injection"):
        return None

    db.add(GameLog(
        session_id=session_id,
        role="dm",
        content=guard["refusal"],
        log_type="combat",
    ))
    await db.commit()
    return {
        "type": f"blocked_{guard['verdict']}",
        "narrative": guard["refusal"],
        "companion_reactions": "",
        "dice_display": [],
        "player_choices": [],
        "needs_check": {"required": False},
        "combat_triggered": False,
        "combat_ended": False,
        "combat_end_result": None,
        "combat_update": None,
        "errors": [],
    }


async def load_latest_combat_state(db: AsyncSession, session_id: str):
    result = await db.execute(
        select(CombatState)
        .where(CombatState.session_id == session_id)
        .order_by(CombatState.created_at.desc())
    )
    return result.scalars().first()


async def get_session_member(db: AsyncSession, session_id: str, user_id: str):
    result = await db.execute(
        select(SessionMember).where(
            SessionMember.session_id == session_id,
            SessionMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def load_recent_log_contents(db: AsyncSession, session_id: str) -> list[str]:
    result = await db.execute(
        select(GameLog)
        .where(GameLog.session_id == session_id)
        .order_by(GameLog.created_at.desc())
        .limit(8)
    )
    return [log.content for log in reversed(result.scalars().all())]
