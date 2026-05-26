"""
api.combat.grapples — Grapple and shove combat endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import CombatState, GameLog
from api.deps import (
    assert_can_act,
    assert_character_can_act,
    assert_optional_session_access,
    get_optional_user_id,
    get_session_or_404,
)
from api.combat._shared import _broadcast_combat
from api.combat.schemas import GrappleShoveRequest
from schemas.combat_responses import CombatActionResult
from schemas.ws_events import CombatUpdate
from services.combat_grapple_service import CombatGrappleError, resolve_grapple_shove

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/grapple-shove", response_model=CombatActionResult)
async def grapple_shove(
    session_id: str,
    req: GrappleShoveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    Grapple or Shove action. Replaces one attack.
    Grapple: contested Athletics check, success → target grappled (speed=0)
    Shove: contested Athletics check, success → target prone or pushed 5ft
    """
    session = await get_session_or_404(session_id, db)
    await assert_optional_session_access(session, user_id, db)
    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if combat and combat.turn_order:
        try:
            current = combat.turn_order[combat.current_turn_index or 0]
            actor_id = current.get("character_id") if isinstance(current, dict) else None
            if actor_id:
                if user_id:
                    await assert_can_act(session, user_id, actor_id, db)
                else:
                    await assert_character_can_act(actor_id, db)
        except (IndexError, AttributeError):
            pass

    try:
        result = await resolve_grapple_shove(
            db,
            session=session,
            combat=combat,
            action_type=req.action_type,
            target_id=req.target_id,
            shove_type=req.shove_type,
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
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            narration=result.narration,
            action=req.action_type,
            target_id=req.target_id,
        ),
        db=db,
    )
    return result.payload
