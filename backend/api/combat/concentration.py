from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.combat._shared import _broadcast_combat
from api.deps import (
    assert_can_act,
    assert_character_in_session,
    assert_session_access,
    get_session_or_404,
    get_user_id,
)
from database import get_db
from models import Character, CombatState, GameLog
from schemas.ws_events import CombatUpdate
from services.combat_concentration_end_service import end_concentration_for_character

router = APIRouter(prefix="/game", tags=["combat"])


class EndConcentrationRequest(BaseModel):
    character_id: str


@router.post("/combat/{session_id}/concentration/end")
async def end_concentration(
    session_id: str,
    req: EndConcentrationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Voluntarily end a character's concentration without spending an action."""
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)

    character = await db.get(Character, req.character_id)
    if not character:
        raise HTTPException(404, "角色不存在")
    await assert_character_in_session(character, session, db)
    await assert_can_act(
        session,
        user_id,
        character.id,
        db,
        require_current_turn=False,
        allow_incapacitated=True,
    )

    result = await end_concentration_for_character(db, session, character)
    response = result.to_response()
    dice_result = {
        "type": "concentration_end",
        "actor_id": character.id,
        "actor_name": character.name,
        "actor_state": result.actor_state,
        "caster_state": result.actor_state,
        "concentration_ended": result.ended,
        "concentration_spell_name": result.spell_name,
        "concentration_effect_updates": result.concentration_effect_updates,
        "ready_action_failed": result.ready_action_failed,
    }
    response_payload = {
        **response,
        "action": "concentration_end",
        "actor_id": character.id,
        "actor_name": character.name,
        "dice_result": dice_result,
        "special_action": dice_result,
    }

    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=result.narration,
        log_type="combat",
        dice_result=dice_result,
    ))
    await db.commit()

    combat_result = await db.execute(
        select(CombatState)
        .where(CombatState.session_id == session_id)
        .order_by(CombatState.created_at.desc())
    )
    combat = combat_result.scalars().first()
    if combat:
        await _broadcast_combat(
            session,
            combat,
            CombatUpdate(
                actor_id=character.id,
                actor_name=character.name,
                narration=result.narration,
                action="concentration_end",
                actor_state=result.actor_state,
                caster_state=result.actor_state,
                concentration_ended=result.ended,
                concentration_spell_name=result.spell_name,
                concentration_effect_updates=result.concentration_effect_updates,
                ready_action_failed=result.ready_action_failed,
                dice_result=dice_result,
                special_action=dice_result,
            ),
            db=db,
        )

    return response_payload
