"""
api.combat.ai_end — end-combat endpoint.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import CombatState, GameLog
from api.deps import assert_session_access, broadcast_to_session, get_session_or_404, get_user_id
from api.combat._shared import _assert_ai_combat_driver, _release_turn_advance_lock
from schemas.combat_responses import EndTurnResult
from schemas.ws_events import CombatUpdate

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/end", response_model=EndTurnResult)
async def end_combat(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    await _assert_ai_combat_driver(db, session, user_id)
    session.combat_active = False
    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if combat:
        await db.delete(combat)
    db.add(GameLog(session_id=session_id, role="system",
                   content="⚔️ 战斗结束，队伍继续前进。", log_type="system"))
    await db.commit()
    _release_turn_advance_lock(session_id)
    await broadcast_to_session(
        session,
        CombatUpdate(combat=None, combat_over=True, outcome="ended"),
    )
    return {"ok": True}
