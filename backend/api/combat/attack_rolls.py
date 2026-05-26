"""
api.combat.attack_rolls — two-step attack and damage roll endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, CombatState, GameLog
from api.deps import assert_can_act, assert_character_in_session, get_session_or_404, get_user_id
from api.combat._shared import (
    _get_ts,
    _broadcast_combat,
    _has_ally_adjacent_to,
    _save_ts,
    svc,
)
from services.combat_attack_damage_service import (
    apply_attack_damage_to_target,
    find_pending_attack,
    resolve_pending_attack_damage,
)
from api.combat.schemas import AttackRollRequest, DamageRollRequest
from services.combat_attack_prepare_service import prepare_attack_roll
from services.combat_attack_roll_service import CombatAttackRollError
from services.combat_narrator import narrate_action
from services.combat_outcome_service import check_and_cleanup_combat_outcome
from schemas.combat_responses import CombatActionResult

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/attack-roll", response_model=CombatActionResult)
async def attack_roll(
    session_id: str,
    req:        AttackRollRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    两步攻击流程 Step 1：仅掷 d20 攻击检定，判定命中/未中/暴击/大失手。
    不掷伤害骰、不扣 HP。结果暂存到 turn_states.pending_attack 供 /damage-roll 使用。
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")
    # 多人联机：校验该用户有权操作攻击者
    await assert_can_act(session, user_id, req.entity_id, db)

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    await db.refresh(session)
    player    = await db.get(Character, req.entity_id)
    if not player:
        raise HTTPException(404, "攻击者不存在")
    await assert_character_in_session(player, session, db)
    player_id   = req.entity_id
    state       = session.game_state or {}
    enemies     = list(state.get("enemies", []))

    try:
        prepared = await prepare_attack_roll(
            db,
            combat=combat,
            session=session,
            player=player,
            player_id=player_id,
            target_id=req.target_id,
            action_type=req.action_type,
            is_offhand=req.is_offhand,
            d20_value=req.d20_value,
            enemies=enemies,
        )
    except CombatAttackRollError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    # Generate vivid narration for miss / fumble (hit narration done in damage-roll)
    miss_narration = ""
    attack_roll_result = prepared.attack_roll_result
    if not attack_roll_result["hit"]:
        vivid = await narrate_action(
            actor_name=prepared.attacker_name,
            actor_class=prepared.attacker_class,
            target_name=prepared.target_name,
            action_type="attack", hit=False,
            is_fumble=attack_roll_result["is_fumble"],
        )
        if vivid:
            miss_narration = vivid
        else:
            miss_narration = svc._build_narration(
                prepared.attacker_name,
                prepared.target_name,
                attack_roll_result,
                0,
            )
        # Log miss
        db.add(GameLog(
            session_id=session_id, role="player",
            content=miss_narration, log_type="combat",
            dice_result={"attack": attack_roll_result},
        ))

    await db.commit()

    return {
        "d20":              attack_roll_result["d20"],
        "attack_bonus":     attack_roll_result["attack_bonus"],
        "condition_modifier": attack_roll_result.get("condition_modifier", 0),
        "roll_modifiers":    attack_roll_result.get("roll_modifiers", []),
        "attack_total":     attack_roll_result["attack_total"],
        "target_ac":        attack_roll_result["target_ac"],
        "hit":              attack_roll_result["hit"],
        "is_crit":          attack_roll_result["is_crit"],
        "is_fumble":        attack_roll_result["is_fumble"],
        "cover_bonus":      prepared.cover_bonus,
        "advantage":        prepared.advantage,
        "disadvantage":     prepared.disadvantage,
        "target_name":      prepared.target_name,
        "attacker_name":    prepared.attacker_name,
        "attacks_made":     prepared.turn_state["attacks_made"],
        "attacks_max":      prepared.attacks_max,
        "damage_dice":      prepared.damage_dice,
        "pending_attack_id": prepared.pending_attack_id,
        "turn_state":       prepared.turn_state,
        "narration":        miss_narration,
    }


@router.post("/combat/{session_id}/damage-roll", response_model=CombatActionResult)
async def damage_roll(
    session_id: str,
    req:        DamageRollRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    两步攻击流程 Step 2：掷伤害骰，应用伤害/偷袭/狂暴/专长/抗性，扣 HP。
    必须在 /attack-roll 命中后调用。
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    await db.refresh(session)
    state   = session.game_state or {}
    enemies = list(state.get("enemies", []))

    # ── 读取暂存的 pending_attack ──
    attacker_entity_id, pending = find_pending_attack(
        dict(combat.turn_states or {}),
        req.pending_attack_id,
    )

    if not pending:
        raise HTTPException(404, "未找到待处理的攻击检定，可能已过期或 ID 错误")

    # 多人联机：校验该用户有权操作该 pending_attack 的攻击者
    await assert_can_act(session, user_id, attacker_entity_id, db)

    if not pending["hit"]:
        # Miss — just clean up pending and return
        ts = _get_ts(combat, attacker_entity_id)
        ts.pop("pending_attack", None)
        _save_ts(combat, attacker_entity_id, ts)
        await db.commit()
        raise HTTPException(400, "该攻击未命中，无法掷伤害骰")

    player = await db.get(Character, attacker_entity_id)
    if not player:
        raise HTTPException(404, "攻击者角色不存在")

    await assert_character_in_session(player, session, db)
    player_name = player.name
    damage_resolution = await resolve_pending_attack_damage(
        db,
        session=session,
        combat=combat,
        player=player,
        attacker_entity_id=attacker_entity_id,
        pending=pending,
        enemies=enemies,
        damage_values=req.damage_values,
        has_ally_adjacent_to=_has_ally_adjacent_to,
    )

    # Build narration (mechanical fallback)
    mechanical_narration = svc._build_narration(
        player_name,
        damage_resolution.target_name,
        damage_resolution.attack_roll_result,
        damage_resolution.total_damage,
    )
    if pending.get("ranged_penalty"):
        mechanical_narration = f"（相邻敌人，远程劣势）{mechanical_narration}"
    if damage_resolution.extra_damage_notes:
        mechanical_narration += f"（{', '.join(damage_resolution.extra_damage_notes)}）"

    # LLM vivid narration (async, fallback to mechanical)
    vivid = await narrate_action(
        actor_name=player_name,
        actor_class=damage_resolution.player_class,
        target_name=damage_resolution.target_name,
        action_type="attack",
        hit=True,
        is_crit=damage_resolution.is_crit,
        damage=damage_resolution.total_damage,
        damage_type=damage_resolution.damage_type,
        extra_details=", ".join(damage_resolution.extra_damage_notes) if damage_resolution.extra_damage_notes else "",
    )
    narration = vivid if vivid else mechanical_narration

    # ── Apply HP ──
    target_new_hp, conc_log, target_state = await apply_attack_damage_to_target(
        db,
        session_id=session_id,
        enemies=enemies,
        target_id=damage_resolution.target_id,
        target_is_enemy=damage_resolution.target_is_enemy,
        damage=damage_resolution.total_damage,
        session=session,
        is_critical=damage_resolution.is_crit,
        attacker_id=str(attacker_entity_id),
        attacker_is_enemy=False,
        is_melee=not bool(pending.get("is_ranged")),
    )
    if damage_resolution.target_is_enemy:
        state["enemies"]   = enemies
        session.game_state = dict(state)
        flag_modified(session, "game_state")

    # ── Dark One's Blessing: Warlock gains temp HP on kill ──
    if target_new_hp is not None and target_new_hp <= 0 and damage_resolution.target_is_enemy:
        if damage_resolution.player_derived.get("subclass_effects", {}).get("dark_ones_blessing"):
            cha_mod_val = damage_resolution.player_derived.get("ability_modifiers", {}).get("cha", 0)
            temp_hp = cha_mod_val + damage_resolution.player_level
            damage_resolution.extra_damage_notes.append(f"黑暗祝福+{temp_hp}临时HP")

    # ── Clear pending_attack ──
    ts = _get_ts(combat, attacker_entity_id)
    ts.pop("pending_attack", None)
    _save_ts(combat, attacker_entity_id, ts)

    # ── GameLog ──
    db.add(GameLog(
        session_id  = session_id,
        role        = "player",
        content     = narration,
        log_type    = "combat",
        dice_result = {
            "attack": damage_resolution.attack_roll_result,
            "damage": damage_resolution.damage_roll_result,
            "sneak_attack": (
                damage_resolution.sneak_attack_damage
                if damage_resolution.sneak_attack_applied
                else None
            ),
            "extra_damage": (
                damage_resolution.extra_damage_notes
                if damage_resolution.extra_damage_notes
                else None
            ),
        },
    ))
    if conc_log:
        db.add(conc_log)

    # ── Check combat over ──
    combat_over, outcome = await check_and_cleanup_combat_outcome(
        db,
        session=session,
        session_id=session_id,
        enemies=enemies,
        check_combat_over=svc.check_combat_over,
    )

    await db.commit()

    from schemas.ws_events import CombatUpdate
    await _broadcast_combat(session, combat, CombatUpdate(), db=db)

    # Check if paladin can smite
    can_smite = damage_resolution.player_class in ("Paladin",) and not combat_over

    return {
        "damage_dice":          damage_resolution.damage_dice_expr,
        "damage_rolls":         damage_resolution.damage_rolls,
        "damage_modifier":      damage_resolution.dmg_mod,
        "damage_total":         damage_resolution.damage_roll_result["total"],
        "crit_extra":           damage_resolution.crit_extra,
        "damage_type":          damage_resolution.damage_type,
        "sneak_attack_dice":    (
            damage_resolution.sneak_attack_dice
            if damage_resolution.sneak_attack_applied
            else None
        ),
        "sneak_attack_damage":  (
            damage_resolution.sneak_attack_damage
            if damage_resolution.sneak_attack_applied
            else 0
        ),
        "dueling_bonus":        damage_resolution.dueling_bonus,
        "rage_bonus":           damage_resolution.rage_bonus,
        "feat_bonus":           damage_resolution.feat_power_bonus_dmg,
        "extra_damage_notes":   damage_resolution.extra_damage_notes,
        "total_damage":         damage_resolution.total_damage,
        "target_new_hp":        target_new_hp,
        "target_state":         target_state,
        "target_id":            damage_resolution.target_id,
        "target_name":          damage_resolution.target_name,
        "narration":            narration,
        "combat_over":          combat_over,
        "outcome":              outcome,
        "can_smite":            can_smite,
        "concentration_check":  conc_log.dice_result if conc_log else None,
        "turn_state":           ts,
    }
