"""
api.combat.spell_rolls — two-step spell roll and confirmation endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Character, CombatState, GameLog
from api.deps import assert_can_act, get_session_or_404, get_user_id
from api.combat._shared import (
    _DEFAULT_TS,
    _get_ts,
)
from services.combat_pending_spell_service import (
    find_pending_spell,
)
from api.combat.schemas import SpellConfirmRequest, SpellRollRequest
from services.combat_spell_confirm_service import confirm_pending_spell, spell_actor_class
from services.combat_spell_prepare_service import prepare_spell_roll
from services.combat_spell_roll_service import (
    CombatSpellRollError,
)
from services.combat_spell_resolution_service import (
    CombatSpellResolutionError,
)
from services.combat_narrator import narrate_action
from services.combat_outcome_service import check_and_cleanup_combat_outcome
from services.spell_service import spell_service
from schemas.combat_responses import CombatActionResult

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/spell-roll", response_model=CombatActionResult)
async def spell_roll(
    session_id: str,
    req: SpellRollRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    两步施法 Step 1：验证法术/法术位/目标，返回将要掷的骰子信息。
    不实际掷伤害骰、不消耗法术位、不应用效果。
    将 pending_spell 存入 turn_states。
    """
    session = await get_session_or_404(session_id, db)
    # 多人联机：校验该用户有权操作施法者
    await assert_can_act(session, user_id, req.caster_id, db)

    spell = spell_service.get(req.spell_name)
    if not spell:
        raise HTTPException(400, f"未知法术：{req.spell_name}")

    err = spell_service.validate_slot_level(req.spell_name, req.spell_level)
    if err:
        raise HTTPException(400, err)

    caster = await db.get(Character, req.caster_id)
    if not caster:
        raise HTTPException(404, "施法者不��在")

    # ── 检查行动配额 ──
    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat_obj = combat_result.scalars().first()
    try:
        prepared = await prepare_spell_roll(
            db,
            combat_obj=combat_obj,
            caster=caster,
            caster_id=req.caster_id,
            spell_name=req.spell_name,
            spell_level=req.spell_level,
            spell=spell,
            target_id=req.target_id,
            target_ids=req.target_ids,
            enemies=list((session.game_state or {}).get("enemies", [])),
            default_turn_state=_DEFAULT_TS,
            get_turn_state=_get_ts,
            consume_slot=spell_service.consume_slot,
            calc_upcast_dice=spell_service.calc_upcast_dice,
        )
    except CombatSpellRollError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    await db.commit()

    return {
        "spell_name": req.spell_name,
        "spell_level": req.spell_level,
        "spell_type": spell["type"],
        "damage_dice": prepared.damage_dice,
        "heal_dice": prepared.heal_dice,
        "save_type": prepared.save_type,
        "save_dc": prepared.spell_save_dc if prepared.save_type else None,
        "is_cantrip": prepared.is_cantrip,
        "is_aoe": prepared.is_aoe,
        "is_concentration": prepared.is_concentration,
        "targets": prepared.targets,
        "pending_spell_id": prepared.pending_spell["pending_spell_id"],
        "turn_state": prepared.turn_state,
    }


@router.post("/combat/{session_id}/spell-confirm", response_model=CombatActionResult)
async def spell_confirm(
    session_id: str,
    req: SpellConfirmRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    两步施法 Step 2：掷伤害/治疗骰，消耗法术位，应用效果。
    必须在 /spell-roll 之后调用。
    """
    session = await get_session_or_404(session_id, db)

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat_obj = combat_result.scalars().first()
    if not combat_obj:
        raise HTTPException(404, "战斗状态不存在")

    await db.refresh(session)

    # ── 查找 pending_spell ──
    caster_entity_id, pending = find_pending_spell(
        dict(combat_obj.turn_states or {}),
        req.pending_spell_id,
    )

    if not pending:
        raise HTTPException(404, "未找到待处理的施法，可能已过期或 ID 错误")

    # 多人联机：校验该用户有权操作 pending_spell 的施法者
    await assert_can_act(session, user_id, caster_entity_id, db)

    caster = await db.get(Character, caster_entity_id)
    if not caster:
        raise HTTPException(404, "施法���不存在")

    spell_name = pending["spell_name"]

    spell = spell_service.get(spell_name)
    if not spell:
        raise HTTPException(400, f"未知法术：{spell_name}")

    try:
        confirmed = await confirm_pending_spell(
            db,
            session_id=session_id,
            combat_obj=combat_obj,
            caster=caster,
            caster_entity_id=caster_entity_id,
            pending=pending,
            spell=spell,
            state=session.game_state or {},
            enemies=list((session.game_state or {}).get("enemies", [])),
            damage_values=req.damage_values,
            session=session,
            spell_service_obj=spell_service,
            check_combat_outcome_func=check_and_cleanup_combat_outcome,
        )
    except CombatSpellResolutionError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    # LLM vivid narration for spells
    vivid = await narrate_action(
        actor_name=caster.name,
        actor_class=spell_actor_class(caster),
        target_name=confirmed.spell_target,
        action_type="spell",
        spell_name=spell_name,
        damage=confirmed.damage,
        heal_amount=confirmed.heal,
        damage_type=spell.get("damage_type", ""),
    )
    narration = vivid if vivid else confirmed.narration
    response_narration = narration
    if confirmed.wild_magic_narration_append:
        response_narration += f"\n\n{confirmed.wild_magic_narration_append}"

    db.add(GameLog(
        session_id=session_id,
        role="player" if caster.is_player else f"companion_{caster.name}",
        content=narration,
        log_type="combat",
        dice_result=confirmed.log_dice_result,
    ))
    for cl in confirmed.concentration_logs:
        db.add(cl)
    for wild_magic_log in confirmed.wild_magic_logs:
        db.add(wild_magic_log)

    await db.commit()

    return {
        "narration": response_narration,
        "damage": confirmed.damage,
        "heal": confirmed.heal,
        "target_id": confirmed.target_id,
        "target_new_hp": confirmed.target_new_hp,
        "aoe_results": confirmed.aoe_results,
        "remaining_slots": confirmed.remaining_slots,
        "dice_detail": confirmed.dice_detail,
        "dice_result": {"total": confirmed.damage or confirmed.heal or 0},
        "turn_state": confirmed.turn_state,
        "is_concentration": confirmed.is_concentration,
        "is_aoe": confirmed.is_aoe,
        "combat_over": confirmed.combat_over,
        "outcome": confirmed.outcome,
        "wild_magic_surge": confirmed.wild_magic_surge,
        "wild_magic_check": confirmed.wild_magic_check,
    }
