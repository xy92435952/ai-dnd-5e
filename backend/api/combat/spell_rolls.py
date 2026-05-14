"""
api.combat.spell_rolls — two-step spell roll and confirmation endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, CombatState, GameLog
from api.deps import assert_can_act, get_session_or_404, get_user_id
from api.combat._shared import (
    _DEFAULT_TS,
    _get_ts,
    svc,
)
from services.combat_pending_spell_service import (
    complete_pending_spell,
    find_pending_spell,
)
from api.combat.schemas import SpellConfirmRequest, SpellRollRequest
from services.combat_spell_application_service import apply_confirmed_spell_effects
from services.combat_spell_prepare_service import prepare_spell_roll
from services.combat_spell_roll_service import (
    CombatSpellRollError,
)
from services.combat_spell_resolution_service import (
    CombatSpellResolutionError,
    build_spell_mechanical_narration,
    build_spell_resolution_context,
    choose_spell_narration_target,
    consume_spell_slot_for_confirmation,
)
from services.combat_wild_magic_service import (
    apply_wild_magic_mechanical_effect,
    resolve_wild_magic_for_spell,
)
from services.combat_narrator import narrate_action
from services.combat_outcome_service import check_and_cleanup_combat_outcome
from services.dnd_rules import _normalize_class, roll_dice, roll_wild_magic_surge
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
    spell_level = pending["spell_level"]
    target_ids = pending["target_ids"]
    is_cantrip = pending["is_cantrip"]
    is_aoe = pending["is_aoe"]
    spell_type = pending["spell_type"]

    spell = spell_service.get(spell_name)
    if not spell:
        raise HTTPException(400, f"未知法术：{spell_name}")

    # ── 消耗法术位 ──
    try:
        new_slots = consume_spell_slot_for_confirmation(
            current_slots=caster.spell_slots,
            spell_level=spell_level,
            is_cantrip=is_cantrip,
            consume_slot=spell_service.consume_slot,
        )
    except CombatSpellResolutionError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    caster.spell_slots = new_slots

    # ── 施法属性 ──
    spell_context = build_spell_resolution_context(caster.derived)
    spell_mod = spell_context["spell_mod"]
    spell_save_dc = spell_context["spell_save_dc"]
    bonus_healing = spell_context["bonus_healing"]

    state = session.game_state or {}
    enemies = list(state.get("enemies", []))

    spell_application = await apply_confirmed_spell_effects(
        db,
        session_id=session_id,
        enemies=enemies,
        target_ids=target_ids,
        is_aoe=is_aoe,
        spell_type=spell_type,
        spell_name=spell_name,
        spell_level=spell_level,
        spell_mod=spell_mod,
        bonus_healing=bonus_healing,
        spell=spell,
        damage_values=req.damage_values,
        spell_save_dc=spell_save_dc,
        resolve_damage=spell_service.resolve_damage,
        resolve_heal=spell_service.resolve_heal,
    )
    result_damage = spell_application.result_damage
    result_heal = spell_application.result_heal
    dice_detail = spell_application.dice_detail
    target_new_hp = spell_application.target_new_hp
    aoe_results = spell_application.aoe_results
    conc_logs = spell_application.concentration_logs
    condition_name = spell_application.condition_name
    save_detail = spell_application.save_detail
    if spell_application.enemies_changed:
        state["enemies"] = enemies
        session.game_state = dict(state)
        flag_modified(session, "game_state")

    # ── 专注 ──
    if spell.get("concentration"):
        caster.concentration = spell_name

    # ── 叙事 ──
    mechanical_narration = build_spell_mechanical_narration(
        caster_name=caster.name,
        spell_name=spell_name,
        spell_level=spell_level,
        is_cantrip=is_cantrip,
        is_aoe=is_aoe,
        aoe_results=aoe_results,
        result_damage=result_damage,
        result_heal=result_heal,
        spell_type=spell_type,
        save_detail=save_detail,
        condition_name=condition_name,
    )

    # LLM vivid narration for spells
    spell_target = choose_spell_narration_target(
        is_aoe=is_aoe,
        aoe_results=aoe_results,
        target_ids=target_ids,
    )
    vivid = await narrate_action(
        actor_name=caster.name,
        actor_class=_normalize_class(caster.char_class),
        target_name=spell_target if isinstance(spell_target, str) else str(spell_target),
        action_type="spell",
        spell_name=spell_name,
        damage=result_damage,
        heal_amount=result_heal,
        damage_type=spell.get("damage_type", ""),
    )
    narration = vivid if vivid else mechanical_narration

    db.add(GameLog(
        session_id=session_id,
        role="player" if caster.is_player else f"companion_{caster.name}",
        content=narration,
        log_type="combat",
        dice_result={
            "dice": dice_detail, "damage": result_damage, "heal": result_heal,
            "aoe": aoe_results,
        },
    ))
    for cl in conc_logs:
        db.add(cl)

    # ── 标记行动已用 ──
    spell_ts = complete_pending_spell(combat_obj, caster_entity_id, is_cantrip=is_cantrip)

    # ── 野蛮魔法涌动检测（Wild Magic Surge）──
    wild_magic = resolve_wild_magic_for_spell(
        caster_name=caster.name,
        is_cantrip=is_cantrip,
        derived=caster.derived,
        class_resources=caster.class_resources,
        roll_dice=roll_dice,
        roll_wild_magic_surge=roll_wild_magic_surge,
    )
    wild_magic_surge = wild_magic.surge
    wild_magic_check = wild_magic.check
    if wild_magic.narration_append:
        narration += f"\n\n{wild_magic.narration_append}"
    if wild_magic.updated_class_resources is not None:
        caster.class_resources = wild_magic.updated_class_resources
    if wild_magic.log_content:
        log_kwargs = {
            "session_id": session_id,
            "role": "system",
            "content": wild_magic.log_content,
            "log_type": "system",
        }
        if wild_magic.log_dice_result:
            log_kwargs["dice_result"] = wild_magic.log_dice_result
        db.add(GameLog(**log_kwargs))
    apply_wild_magic_mechanical_effect(
        caster=caster,
        surge=wild_magic_surge,
        roll_dice=roll_dice,
    )

    # ── 检查战斗结束 ──
    combat_over, outcome = await check_and_cleanup_combat_outcome(
        db,
        session=session,
        session_id=session_id,
        enemies=enemies,
        check_combat_over=svc.check_combat_over,
    )

    await db.commit()

    return {
        "narration": narration,
        "damage": result_damage,
        "heal": result_heal,
        "target_id": target_ids[0] if target_ids else None,
        "target_new_hp": target_new_hp,
        "aoe_results": aoe_results,
        "remaining_slots": new_slots,
        "dice_detail": dice_detail,
        "dice_result": {"total": result_damage or result_heal or 0},
        "turn_state": spell_ts,
        "is_concentration": spell.get("concentration", False),
        "is_aoe": is_aoe,
        "combat_over": combat_over,
        "outcome": outcome,
        "wild_magic_surge": wild_magic_surge,
        "wild_magic_check": wild_magic_check,
    }
