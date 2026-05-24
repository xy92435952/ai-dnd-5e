"""
api.combat.maneuvers — Battle Master maneuver combat endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import CombatState, GameLog
from api.deps import get_session_or_404
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
):
    """
    Battle Master maneuver: consume 1 superiority die and apply effect.
    Maneuvers: precision, trip, disarm, riposte, menacing, pushing, goading
    """
    session = await get_session_or_404(session_id, db)
    result_db = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = result_db.scalars().first()

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
