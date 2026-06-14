"""
api.combat.spellcasting — legacy direct spell casting endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Character, CombatState, GameLog
from api.deps import (
    assert_can_act,
    assert_character_in_session,
    get_session_or_404,
    get_user_id,
)
from api.combat._shared import _assert_expected_turn_token, _broadcast_combat
from api.combat.schemas import SpellRequest
from schemas.combat_responses import CombatActionResult
from schemas.ws_events import CombatUpdate
from services.combat_direct_spell_service import CombatDirectSpellError, cast_direct_spell

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/spell", response_model=CombatActionResult)
async def cast_spell(
    session_id: str,
    req: SpellRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    施放法术（消耗法术位，计算升环效果）
    - 单目标：传 target_id
    - AoE 多目标：传 target_ids（空列表 = 命中所有存活敌人）
    - AoE 带豁免：每个目标各自豁免，成功者伤害减半
    """
    session = await get_session_or_404(session_id, db)
    await assert_can_act(session, user_id, req.caster_id, db)

    caster = await db.get(Character, req.caster_id)
    if not caster:
        raise HTTPException(404, "施法者不存在")

    await assert_character_in_session(caster, session, db)

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat_obj = combat_result.scalars().first()
    if combat_obj:
        _assert_expected_turn_token(combat_obj, req.expected_turn_token, detail_prefix="Spell")

    try:
        result = await cast_direct_spell(
            db,
            session_id=session_id,
            session=session,
            combat_obj=combat_obj,
            caster=caster,
            caster_id=req.caster_id,
            spell_name=req.spell_name,
            spell_level=req.spell_level,
            target_id=req.target_id,
            target_ids=req.target_ids,
        )
    except CombatDirectSpellError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    db.add(GameLog(
        session_id=session_id,
        role="player" if caster.is_player else f"companion_{caster.name}",
        content=result.narration,
        log_type="combat",
        dice_result=result.log_dice_result,
    ))
    for concentration_log in result.concentration_logs:
        db.add(concentration_log)

    await db.commit()
    response = result.to_response()
    await _broadcast_combat(
        session,
        combat_obj,
        CombatUpdate(
            actor_id=str(req.caster_id),
            actor_name=caster.name,
            narration=result.narration,
            action="spell",
            target_id=response.get("target_id"),
            target_new_hp=response.get("target_new_hp"),
            target_state=response.get("target_state"),
            actor_state=response.get("actor_state"),
            caster_state=response.get("caster_state"),
            resurrection_results=response.get("resurrection_results"),
            remaining_slots=response.get("remaining_slots"),
            combat_over=response.get("combat_over", False),
            outcome=response.get("outcome"),
        ),
        db=db,
    )
    return response
