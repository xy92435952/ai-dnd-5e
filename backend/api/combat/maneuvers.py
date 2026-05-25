"""
api.combat.maneuvers — Battle Master maneuver combat endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import CombatState, GameLog
from api.deps import assert_can_act, get_session_or_404, get_user_id
from api.combat._shared import _broadcast_combat
from api.combat.schemas import ManeuverRequest
from schemas.combat_responses import CombatActionResult
from schemas.ws_events import CombatUpdate
from services.combat_maneuver_service import CombatManeuverError, resolve_maneuver

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/maneuver", response_model=CombatActionResult)
async def use_maneuver(
    session_id: str,
    req: ManeuverRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    Battle Master maneuver: consume 1 superiority die and apply effect.
    Maneuvers: precision, trip, disarm, riposte, menacing, pushing, goading
    """
    session = await get_session_or_404(session_id, db)
    result_db = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = result_db.scalars().first()
    if combat and combat.turn_order:
        try:
            current = combat.turn_order[combat.current_turn_index or 0]
            actor_id = current.get("character_id") if isinstance(current, dict) else None
            if actor_id:
                await assert_can_act(session, user_id, actor_id, db)
        except (IndexError, AttributeError):
            pass

    try:
        result = await resolve_maneuver(
            db,
            session=session,
            combat=combat,
            maneuver_name=req.maneuver_name,
            target_id=req.target_id,
        )
    except CombatManeuverError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=result.narration,
        log_type="combat",
        dice_result=result.log_dice_result,
    ))
    await db.commit()
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            narration=result.narration,
            maneuver=req.maneuver_name,
            target_id=req.target_id,
        ),
        db=db,
    )
    return result.payload
