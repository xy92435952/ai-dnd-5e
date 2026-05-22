"""
api.combat.grapples — Grapple and shove combat endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import CombatState, GameLog
from api.deps import (
    get_session_or_404,
    get_user_id,
    assert_can_act,
    resolve_controlled_player_character,
)
from api.combat.schemas import GrappleShoveRequest
from schemas.combat_responses import CombatActionResult
from services.combat_grapple_service import CombatGrappleError, resolve_grapple_shove

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/grapple-shove", response_model=CombatActionResult)
async def grapple_shove(
    session_id: str,
    req: GrappleShoveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    Grapple or Shove action. Replaces one attack.
    Grapple: contested Athletics check, success → target grappled (speed=0)
    Shove: contested Athletics check, success → target prone or pushed 5ft
    """
    session = await get_session_or_404(session_id, db)
    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    player = await resolve_controlled_player_character(session, user_id, db)
    await assert_can_act(session, user_id, player.id, db)

    try:
        result = await resolve_grapple_shove(
            db,
            session=session,
            combat=combat,
            action_type=req.action_type,
            target_id=req.target_id,
            shove_type=req.shove_type,
            actor_id=player.id,
        )
    except CombatGrappleError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    db.add(GameLog(
        session_id=session_id,
        role="player",
        content=result.narration,
        log_type="combat",
        dice_result=result.log_dice_result,
    ))
    await db.commit()
    return result.payload
