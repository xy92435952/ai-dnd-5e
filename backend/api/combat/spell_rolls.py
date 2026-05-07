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
from api.combat.pending_spells import (
    build_pending_spell,
    complete_pending_spell,
    find_pending_spell,
    store_pending_spell,
)
from api.combat.schemas import SpellConfirmRequest, SpellRollRequest
from api.combat.spell_effects import (
    apply_frontend_dice_override,
    apply_control_spell_to_target,
    apply_spell_damage_to_target,
    apply_spell_heal_to_target,
    resolve_spell_condition,
    roll_spell_save,
)
from api.combat.spell_targets import (
    collect_spell_target_ids,
    collect_spell_target_names,
    validate_spell_range,
)
from services.combat_narrator import narrate_action
from services.dnd_rules import _normalize_class
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
    spell_ts = _get_ts(combat_obj, req.caster_id) if combat_obj else dict(_DEFAULT_TS)
    if spell_ts["action_used"] and spell["level"] != 0:
        raise HTTPException(400, "本回合行动已用尽")

    # ── 验证法术位 ──
    is_cantrip = spell["level"] == 0
    if not is_cantrip:
        current_slots = dict(caster.spell_slots or {})
        _, slot_err = spell_service.consume_slot(dict(current_slots), req.spell_level)
        if slot_err:
            raise HTTPException(400, slot_err)

    # ── 确定目标列表 ──
    state = session.game_state or {}
    enemies = list(state.get("enemies", []))
    is_aoe = spell.get("aoe", False)

    raw_ids = collect_spell_target_ids(req.target_id, req.target_ids, enemies, is_aoe=is_aoe)
    target_names = await collect_spell_target_names(db, raw_ids, enemies)

    # ── 距离检查（法术射程）──
    positions = dict(combat_obj.entity_positions or {}) if combat_obj else {}
    validate_spell_range(
        target_ids=raw_ids,
        positions=positions,
        caster_id=req.caster_id,
        spell_range_ft=spell.get("range", 0),
    )

    # ── 计算要掷的骰子 ──
    derived = caster.derived or {}
    spell_abil = derived.get("spell_ability")
    spell_mod = derived.get("ability_modifiers", {}).get(spell_abil or "", 0) if spell_abil else 0
    spell_save_dc = derived.get("spell_save_dc", 13)

    # Figure out the dice expression from spell data
    damage_dice = ""
    heal_dice = ""
    if spell["type"] == "damage":
        base_dice = spell.get("damage_dice", spell.get("damage", "1d6"))
        upcast_dice = spell_service.calc_upcast_dice(req.spell_name, req.spell_level)
        damage_dice = upcast_dice if upcast_dice else base_dice
    elif spell["type"] == "heal":
        base_dice = spell.get("heal_dice", spell.get("heal", "1d8"))
        upcast_dice = spell_service.calc_upcast_dice(req.spell_name, req.spell_level)
        heal_dice = upcast_dice if upcast_dice else base_dice

    save_type = spell.get("save", None)

    # ── 生成 pending_spell_id 并暂存 ──
    pending_spell = build_pending_spell(
        caster_id=req.caster_id,
        spell_name=req.spell_name,
        spell_level=req.spell_level,
        target_ids=raw_ids,
        is_cantrip=is_cantrip,
        is_aoe=is_aoe,
        spell_type=spell["type"],
    )

    if combat_obj:
        store_pending_spell(combat_obj, req.caster_id, spell_ts, pending_spell)

    await db.commit()

    return {
        "spell_name": req.spell_name,
        "spell_level": req.spell_level,
        "spell_type": spell["type"],
        "damage_dice": damage_dice,
        "heal_dice": heal_dice,
        "save_type": save_type,
        "save_dc": spell_save_dc if save_type else None,
        "is_cantrip": is_cantrip,
        "is_aoe": is_aoe,
        "is_concentration": spell.get("concentration", False),
        "targets": [{"id": tid, "name": n} for tid, n in zip(raw_ids, target_names)],
        "pending_spell_id": pending_spell["pending_spell_id"],
        "turn_state": spell_ts,
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
    if not is_cantrip:
        new_slots, slot_err = spell_service.consume_slot(dict(caster.spell_slots or {}), spell_level)
        if slot_err:
            raise HTTPException(400, slot_err)
        caster.spell_slots = new_slots
    else:
        new_slots = caster.spell_slots or {}

    # ── 施法属性 ──
    derived = caster.derived or {}
    spell_abil = derived.get("spell_ability")
    spell_mod = derived.get("ability_modifiers", {}).get(spell_abil or "", 0) if spell_abil else 0
    spell_save_dc = derived.get("spell_save_dc", 13)
    bonus_healing = derived.get("bonus_healing", False)

    state = session.game_state or {}
    enemies = list(state.get("enemies", []))

    result_damage = 0
    result_heal = 0
    dice_detail = {}
    target_new_hp = None
    aoe_results = []
    conc_logs = []
    condition_name = None
    save_detail = None

    # ══ AoE 法术 ══
    if is_aoe:
        if spell_type == "damage":
            result_damage, dice_detail = spell_service.resolve_damage(spell_name, spell_level, spell_mod)
            result_damage, dice_detail = apply_frontend_dice_override(
                value=result_damage,
                dice_detail=dice_detail,
                damage_values=req.damage_values,
                modifier=spell_mod,
            )
            save_ability = spell.get("save")
            half_on_save = spell.get("half_on_save", True)

            for tid in target_ids:
                dmg_this = result_damage
                save_result = await roll_spell_save(
                    db,
                    enemies,
                    tid,
                    save_ability=save_ability,
                    spell_save_dc=spell_save_dc,
                )
                if save_result and save_result["success"] and half_on_save:
                    dmg_this = dmg_this // 2

                applied, cl = await apply_spell_damage_to_target(
                    db,
                    session_id,
                    enemies,
                    tid,
                    dmg_this,
                    save_result=save_result,
                )
                if applied:
                    aoe_results.append(applied)
                if cl:
                    conc_logs.append(cl)

            state["enemies"] = enemies
            session.game_state = dict(state); flag_modified(session, "game_state")

        elif spell_type == "heal":
            result_heal, dice_detail = spell_service.resolve_heal(spell_name, spell_level, spell_mod, bonus_healing)
            result_heal, dice_detail = apply_frontend_dice_override(
                value=result_heal,
                dice_detail=dice_detail,
                damage_values=req.damage_values,
                modifier=spell_mod,
            )
            for tid in target_ids:
                applied = await apply_spell_heal_to_target(db, tid, result_heal)
                if applied:
                    aoe_results.append(applied)

    # ══ 单目标法术 ══
    else:
        tid = target_ids[0] if target_ids else None
        if spell_type == "damage" and tid:
            result_damage, dice_detail = spell_service.resolve_damage(spell_name, spell_level, spell_mod)
            result_damage, dice_detail = apply_frontend_dice_override(
                value=result_damage,
                dice_detail=dice_detail,
                damage_values=req.damage_values,
                modifier=spell_mod,
            )
            applied, cl = await apply_spell_damage_to_target(
                db,
                session_id,
                enemies,
                tid,
                result_damage,
            )
            if applied:
                target_new_hp = applied["new_hp"]
                if applied["target_id"] in {e.get("id") for e in enemies}:
                    state["enemies"] = enemies
                    session.game_state = dict(state); flag_modified(session, "game_state")
            if cl:
                conc_logs.append(cl)

        elif spell_type == "heal" and tid:
            result_heal, dice_detail = spell_service.resolve_heal(spell_name, spell_level, spell_mod, bonus_healing)
            result_heal, dice_detail = apply_frontend_dice_override(
                value=result_heal,
                dice_detail=dice_detail,
                damage_values=req.damage_values,
                modifier=spell_mod,
            )
            applied = await apply_spell_heal_to_target(db, tid, result_heal)
            if applied:
                target_new_hp = applied["new_hp"]

        elif spell_type in ("control", "utility") and tid:
            condition_name, save_abil = resolve_spell_condition(spell_name, spell)
            control_result = await apply_control_spell_to_target(
                db,
                enemies,
                tid,
                condition_name=condition_name,
                save_ability=save_abil,
                spell_save_dc=spell_save_dc,
            )
            save_detail = control_result["save_detail"]
            if control_result["applied"] and any(e["id"] == tid for e in enemies):
                state["enemies"] = enemies
                session.game_state = dict(state)
                flag_modified(session, "game_state")
            result_damage = 0
            dice_detail = {}

    # ── 专注 ──
    if spell.get("concentration"):
        caster.concentration = spell_name

    # ── 叙事 ──
    level_str = f"（{spell_level}环）" if not is_cantrip else "（戏法）"
    if is_aoe and aoe_results:
        targets_summary = "、".join(r.get("target_name", "?") for r in aoe_results[:4])
        mechanical_narration = (
            f"✨ {caster.name} 施放了【{spell_name}】{level_str}，"
            f"命中 {targets_summary}{'等' if len(aoe_results) > 4 else ''}！"
            + (f"（单目标最高 {result_damage} 点伤害）" if result_damage else "")
            + (f"（每人恢复 {result_heal} HP）" if result_heal else "")
        )
    else:
        mechanical_narration = (
            f"✨ {caster.name} 施放了【{spell_name}】{level_str}"
            + (f"，造成 {result_damage} 点伤害！" if result_damage else "")
            + (f"，恢复 {result_heal} HP！" if result_heal else "")
        )

    # Control spell narration
    if spell_type in ("control", "utility") and save_detail:
        saved_str = "通过" if save_detail["success"] else "未通过"
        mechanical_narration += f"\n{save_detail['ability'].upper()} 豁免 DC{save_detail['dc']}: d20={save_detail['d20']}+{save_detail['modifier']}={save_detail['total']} — {saved_str}！"
        if not save_detail["success"]:
            mechanical_narration += f"\n目标陷入【{condition_name}】状态！"

    # LLM vivid narration for spells
    spell_target = targets_summary if (is_aoe and aoe_results) else (target_ids[0] if target_ids else "")
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
    wild_magic_surge = None
    wild_magic_check = None
    if not is_cantrip:
        caster_sub_effects = (caster.derived or {}).get("subclass_effects", {})
        if caster_sub_effects.get("wild_magic"):
            from services.dnd_rules import roll_dice as _roll_surge, roll_wild_magic_surge

            forced_surge = (caster.class_resources or {}).get("tides_of_chaos_used", False)

            if forced_surge:
                # 使用混沌之潮后施法必定触发涌动
                wild_magic_surge = roll_wild_magic_surge()
                wild_magic_check = {"d20": "自动", "triggered": True, "forced": True,
                                    "surge_roll": wild_magic_surge.get("index", 0) + 1}  # d20 table index
                surge_narration = f"🌀 混沌反噬！混沌之潮的代价降临——{wild_magic_surge['effect']}"
                narration += f"\n\n{surge_narration}"
                db.add(GameLog(
                    session_id=session_id, role="system",
                    content=surge_narration, log_type="system",
                ))
                # 重置混沌之潮（可以再次使用）
                class_res = dict(caster.class_resources or {})
                class_res["tides_of_chaos_used"] = False
                caster.class_resources = class_res
            else:
                # 正常检测：掷 d20，1 则触发
                surge_check = _roll_surge("1d20")
                d20_val = surge_check["rolls"][0]
                if d20_val == 1:
                    wild_magic_surge = roll_wild_magic_surge()
                    wild_magic_check = {"d20": d20_val, "triggered": True, "forced": False,
                                        "surge_roll": wild_magic_surge.get("index", 0) + 1}
                    surge_narration = f"🌀 野蛮魔法涌动！d20={d20_val}——{caster.name} 体内的混沌能量失控！{wild_magic_surge['effect']}"
                    narration += f"\n\n{surge_narration}"
                    db.add(GameLog(
                        session_id=session_id, role="system",
                        content=surge_narration, log_type="system",
                        dice_result={"type": "wild_magic_surge", "d20": d20_val, **wild_magic_surge},
                    ))
                else:
                    # 未触发，但仍告知玩家检测发生了
                    wild_magic_check = {"d20": d20_val, "triggered": False, "forced": False}
                    db.add(GameLog(
                        session_id=session_id, role="system",
                        content=f"🎲 野蛮魔法检测: d20={d20_val}（未触发涌动，需要1）",
                        log_type="system",
                    ))

            # 应用有机械效果的涌动
            if wild_magic_surge:
                mech = wild_magic_surge.get("mechanical", {})
                if mech.get("type") == "heal":
                    heal_roll = _roll_surge(mech["dice"])
                    caster.hp_current = min(
                        (caster.derived or {}).get("hp_max", caster.hp_current),
                        caster.hp_current + heal_roll["total"],
                    )
                elif mech.get("type") == "condition":
                    conds = list(caster.conditions or [])
                    conds.append(mech["condition"])
                    caster.conditions = conds

    # ── 检查战斗结束 ──
    player_check = await db.get(Character, session.player_character_id)
    combat_over, outcome = svc.check_combat_over(enemies, player_check.hp_current if player_check else 0)
    if combat_over:
        session.combat_active = False
        # 清理战斗状态记录，防止下次战斗残留旧数据
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs: await db.delete(_old_cs)
        except Exception: pass

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
