"""
api.combat.spellcasting — 法术施放 + 骰子确认 + 法术列表查询

从原 combat.py (单体 5368 行) 按功能域拆出，逻辑未改动。
"""
import uuid
import random
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, Session, GameLog, CombatState, Module
from api.deps import (
    get_session_or_404, entity_snapshot, serialize_combat,
    get_user_id, assert_can_act, broadcast_to_session, current_turn_user_id,
)
from services.combat_service import CombatService
from services.spell_service import spell_service
from services.dnd_rules import roll_dice, _normalize_class
from services.combat_narrator import narrate_action, narrate_batch
from services.character_roster import CharacterRoster

from api.combat._shared import (
    _DEFAULT_TS, svc,
    _get_ts, _save_ts, _reset_ts,
    _broadcast_combat, _calc_entity_turn_limits,
    _chebyshev_dist, _check_attack_range, _ai_move_toward,
    _has_adjacent_enemy, _has_ally_adjacent_to,
    _do_concentration_check, _tick_conditions_char, _tick_conditions_enemy,
    _chebyshev, _resolve_opportunity_attacks,
)
from api.combat.schemas import (
    MoveRequest, ConditionRequest, CombatActionRequest, DeathSaveRequest,
    SmiteRequest, ClassFeatureRequest, ReactionRequest, GrappleShoveRequest,
    AttackRollRequest, DamageRollRequest, SpellRequest, SpellRollRequest,
    SpellConfirmRequest, ManeuverRequest,
)
from schemas.combat_responses import CombatActionResult

router = APIRouter(prefix="/game", tags=["combat"])


@router.get("/spells")
async def get_spell_list():
    """获取完整法术列表"""
    return spell_service.get_all()


@router.get("/spells/class/{class_name}")
async def get_spells_for_class(class_name: str, max_level: int = 9):
    """获取指定职业的可用法术"""
    return spell_service.get_for_class(class_name, max_level)


# ── 两步施法流程：spell-roll → spell-confirm ──────────────────

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

    raw_ids = req.target_ids if req.target_ids is not None else (
        [req.target_id] if req.target_id else []
    )
    if is_aoe and not raw_ids:
        raw_ids = [e["id"] for e in enemies if e.get("hp_current", 0) > 0]

    target_names = []
    for tid in raw_ids:
        e = next((en for en in enemies if en["id"] == tid), None)
        if e:
            target_names.append(e["name"])
        else:
            tc = await db.get(Character, tid)
            if tc:
                target_names.append(tc.name)

    # ── 距离检查（法术射程）──
    positions = dict(combat_obj.entity_positions or {}) if combat_obj else {}
    caster_pos = positions.get(str(req.caster_id))
    spell_range_ft = spell.get("range", 0)
    if isinstance(spell_range_ft, str):
        import re as _re
        m = _re.search(r'(\d+)', str(spell_range_ft))
        spell_range_ft = int(m.group(1)) if m else 0
    if spell_range_ft > 0 and raw_ids:
        spell_range_tiles = max(spell_range_ft // 5, 1)
        for tid in raw_ids:
            tgt_pos = positions.get(str(tid))
            dist = _chebyshev_dist(caster_pos, tgt_pos)
            if dist > spell_range_tiles:
                raise HTTPException(400, f"目标超出法术射程（距离{dist*5}ft，射程{spell_range_ft}ft）")

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
    pending_id = str(uuid.uuid4())
    pending_spell = {
        "pending_spell_id": pending_id,
        "caster_id": req.caster_id,
        "spell_name": req.spell_name,
        "spell_level": req.spell_level,
        "target_ids": raw_ids,
        "is_cantrip": is_cantrip,
        "is_aoe": is_aoe,
        "spell_type": spell["type"],
    }

    if combat_obj:
        spell_ts["pending_spell"] = pending_spell
        _save_ts(combat_obj, req.caster_id, spell_ts)

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
        "pending_spell_id": pending_id,
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
    all_ts = dict(combat_obj.turn_states or {})
    caster_entity_id = None
    pending = None
    for eid, ets in all_ts.items():
        ps = ets.get("pending_spell")
        if ps and ps.get("pending_spell_id") == req.pending_spell_id:
            pending = ps
            caster_entity_id = eid
            break

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

    # ══ AoE 法术 ══
    if is_aoe:
        if spell_type == "damage":
            result_damage, dice_detail = spell_service.resolve_damage(spell_name, spell_level, spell_mod)
            # Frontend dice override for spell damage
            if req.damage_values:
                result_damage = sum(req.damage_values) + spell_mod
                dice_detail["total"] = result_damage
                if "base_roll" in dice_detail:
                    dice_detail["base_roll"]["rolls"] = req.damage_values
                    dice_detail["base_roll"]["total"] = sum(req.damage_values)
            save_ability = spell.get("save")
            half_on_save = spell.get("half_on_save", True)

            for tid in target_ids:
                dmg_this = result_damage
                save_result = None

                if save_ability:
                    target_enemy = next((e for e in enemies if e["id"] == tid), None)
                    target_char = None if target_enemy else await db.get(Character, tid)
                    t_derived = (target_enemy.get("derived", {}) if target_enemy
                                 else (target_char.derived or {} if target_char else {}))
                    t_saves = t_derived.get("saving_throws", {})
                    save_mod = t_saves.get(save_ability,
                                t_derived.get("ability_modifiers", {}).get(save_ability, 0))
                    from services.dnd_rules import roll_dice as _roll_d20
                    d20 = _roll_d20("1d20")["rolls"][0]
                    save_total = d20 + save_mod
                    saved = save_total >= spell_save_dc
                    save_result = {
                        "ability": save_ability, "dc": spell_save_dc,
                        "d20": d20, "modifier": save_mod, "total": save_total, "success": saved,
                    }
                    if saved and half_on_save:
                        dmg_this = dmg_this // 2

                target_enemy2 = next((e for e in enemies if e["id"] == tid), None)
                if target_enemy2:
                    old_hp = target_enemy2.get("hp_current", 0)
                    target_enemy2["hp_current"] = svc.apply_damage(
                        old_hp, dmg_this,
                        target_enemy2.get("derived", {}).get("hp_max", 10),
                    )
                    aoe_results.append({
                        "target_id": tid, "target_name": target_enemy2["name"],
                        "damage": dmg_this, "new_hp": target_enemy2["hp_current"],
                        "save": save_result,
                    })
                else:
                    tc = await db.get(Character, tid)
                    if tc:
                        tc.hp_current = svc.apply_damage(
                            tc.hp_current, dmg_this,
                            (tc.derived or {}).get("hp_max", tc.hp_current),
                        )
                        aoe_results.append({
                            "target_id": tid, "target_name": tc.name,
                            "damage": dmg_this, "new_hp": tc.hp_current,
                            "save": save_result,
                        })
                        cl = await _do_concentration_check(tc, dmg_this, session_id)
                        if cl:
                            conc_logs.append(cl)

            state["enemies"] = enemies
            session.game_state = dict(state); flag_modified(session, "game_state")

        elif spell_type == "heal":
            result_heal, dice_detail = spell_service.resolve_heal(spell_name, spell_level, spell_mod, bonus_healing)
            # Frontend dice override for spell heal
            if req.damage_values:
                result_heal = sum(req.damage_values) + spell_mod
                dice_detail["total"] = result_heal
                if "base_roll" in dice_detail:
                    dice_detail["base_roll"]["rolls"] = req.damage_values
                    dice_detail["base_roll"]["total"] = sum(req.damage_values)
            for tid in target_ids:
                tc = await db.get(Character, tid)
                if tc:
                    tc.hp_current = svc.apply_heal(
                        tc.hp_current, result_heal,
                        (tc.derived or {}).get("hp_max", tc.hp_current),
                    )
                    aoe_results.append({
                        "target_id": tid, "target_name": tc.name,
                        "heal": result_heal, "new_hp": tc.hp_current,
                    })

    # ══ 单目标法术 ══
    else:
        tid = target_ids[0] if target_ids else None
        if spell_type == "damage" and tid:
            result_damage, dice_detail = spell_service.resolve_damage(spell_name, spell_level, spell_mod)
            # Frontend dice override for spell damage
            if req.damage_values:
                result_damage = sum(req.damage_values) + spell_mod
                dice_detail["total"] = result_damage
                if "base_roll" in dice_detail:
                    dice_detail["base_roll"]["rolls"] = req.damage_values
                    dice_detail["base_roll"]["total"] = sum(req.damage_values)
            target_enemy = next((e for e in enemies if e["id"] == tid), None)
            if target_enemy:
                target_enemy["hp_current"] = svc.apply_damage(
                    target_enemy.get("hp_current", 0), result_damage,
                    target_enemy.get("derived", {}).get("hp_max", 10),
                )
                target_new_hp = target_enemy["hp_current"]
                state["enemies"] = enemies
                session.game_state = dict(state); flag_modified(session, "game_state")
            else:
                tc = await db.get(Character, tid)
                if tc:
                    tc.hp_current = svc.apply_damage(
                        tc.hp_current, result_damage,
                        (tc.derived or {}).get("hp_max", tc.hp_current),
                    )
                    target_new_hp = tc.hp_current
                    cl = await _do_concentration_check(tc, result_damage, session_id)
                    if cl:
                        conc_logs.append(cl)

        elif spell_type == "heal" and tid:
            result_heal, dice_detail = spell_service.resolve_heal(spell_name, spell_level, spell_mod, bonus_healing)
            # Frontend dice override for spell heal
            if req.damage_values:
                result_heal = sum(req.damage_values) + spell_mod
                dice_detail["total"] = result_heal
                if "base_roll" in dice_detail:
                    dice_detail["base_roll"]["rolls"] = req.damage_values
                    dice_detail["base_roll"]["total"] = sum(req.damage_values)
            tc = await db.get(Character, tid)
            if tc:
                tc.hp_current = svc.apply_heal(
                    tc.hp_current, result_heal,
                    (tc.derived or {}).get("hp_max", tc.hp_current),
                )
                target_new_hp = tc.hp_current

        elif spell_type in ("control", "utility") and tid:
            # Control/utility spells apply conditions
            _SPELL_CONDITIONS = {
                "Hold Person": ("paralyzed", "wis"),
                "定身术": ("paralyzed", "wis"),
                "Entangle": ("restrained", "str"),
                "纠缠术": ("restrained", "str"),
                "Web": ("restrained", "dex"),
                "蛛网": ("restrained", "dex"),
                "Sleep": ("unconscious", None),
                "睡眠术": ("unconscious", None),
                "Command": ("commanded", "wis"),
                "命令术": ("commanded", "wis"),
                "Faerie Fire": ("faerie_fire", "dex"),
                "妖火": ("faerie_fire", "dex"),
                "Blindness/Deafness": ("blinded", "con"),
                "目盲/耳聋": ("blinded", "con"),
                "Fear": ("frightened", "wis"),
                "恐惧术": ("frightened", "wis"),
                "Silence": ("silenced", None),
                "沉默术": ("silenced", None),
                "Hex": ("hexed", None),
                "妖术": ("hexed", None),
                "Bane": ("baned", "cha"),
                "灾祸术": ("baned", "cha"),
            }
            condition_info = _SPELL_CONDITIONS.get(spell_name, ("affected", spell.get("save")))
            condition_name, save_abil = condition_info

            saved = False
            save_detail = None
            if save_abil:
                target_enemy = next((e for e in enemies if e["id"] == tid), None)
                target_char_ctrl = None if target_enemy else await db.get(Character, tid)
                if target_enemy:
                    t_scores = target_enemy.get("ability_scores", {})
                    t_mod = (t_scores.get(save_abil, 10) - 10) // 2
                elif target_char_ctrl:
                    t_mod = (target_char_ctrl.derived or {}).get("saving_throws", {}).get(save_abil, 0)
                else:
                    t_mod = 0

                from services.dnd_rules import roll_dice as _ctrl_roll
                sr = _ctrl_roll("1d20")["rolls"][0]
                save_total = sr + t_mod
                saved = save_total >= spell_save_dc
                save_detail = {"ability": save_abil, "dc": spell_save_dc, "d20": sr, "modifier": t_mod, "total": save_total, "success": saved}

            if not saved:
                # Apply condition
                target_enemy2 = next((e for e in enemies if e["id"] == tid), None)
                if target_enemy2:
                    conds = target_enemy2.get("conditions", [])
                    if condition_name not in conds:
                        conds.append(condition_name)
                        target_enemy2["conditions"] = conds
                    state["enemies"] = enemies
                    session.game_state = dict(state)
                    flag_modified(session, "game_state")
                else:
                    tc_ctrl = await db.get(Character, tid)
                    if tc_ctrl:
                        conds = list(tc_ctrl.conditions or [])
                        if condition_name not in conds:
                            conds.append(condition_name)
                            tc_ctrl.conditions = conds

            # Also handle spells that do damage + control (like Tasha's Hideous Laughter does 0 damage but applies condition)
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
    if spell_type in ("control", "utility") and 'save_detail' in dir():
        if save_detail:
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
    spell_ts = _get_ts(combat_obj, caster_entity_id)
    spell_ts.pop("pending_spell", None)
    if not is_cantrip:
        spell_ts["action_used"] = True
    _save_ts(combat_obj, caster_entity_id, spell_ts)

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


@router.post("/combat/{session_id}/spell", response_model=CombatActionResult)
async def cast_spell(
    session_id: str, req: SpellRequest,
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

    spell = spell_service.get(req.spell_name)
    if not spell:
        raise HTTPException(400, f"未知法术：{req.spell_name}")

    err = spell_service.validate_slot_level(req.spell_name, req.spell_level)
    if err:
        raise HTTPException(400, err)

    caster = await db.get(Character, req.caster_id)
    if not caster:
        raise HTTPException(404, "施法者不存在")

    # ── 检查行动配额 ──────────────────────────────────────
    combat_result2 = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat_obj     = combat_result2.scalars().first()
    spell_ts       = _get_ts(combat_obj, req.caster_id) if combat_obj else dict(_DEFAULT_TS)
    if spell_ts["action_used"] and spell["level"] != 0:
        raise HTTPException(400, "本回合行动已用尽")

    # ── 消耗法术位 ────────────────────────────────────────
    is_cantrip = spell["level"] == 0
    if not is_cantrip:
        new_slots, slot_err = spell_service.consume_slot(dict(caster.spell_slots or {}), req.spell_level)
        if slot_err:
            raise HTTPException(400, slot_err)
        caster.spell_slots = new_slots
    else:
        new_slots = caster.spell_slots or {}

    # ── 施法属性 ──────────────────────────────────────────
    derived        = caster.derived or {}
    spell_abil     = derived.get("spell_ability")
    spell_mod      = derived.get("ability_modifiers", {}).get(spell_abil or "", 0) if spell_abil else 0
    spell_save_dc  = derived.get("spell_save_dc", 13)
    bonus_healing  = derived.get("bonus_healing", False)

    state   = session.game_state or {}
    enemies = list(state.get("enemies", []))

    result_damage  = 0
    result_heal    = 0
    dice_detail    = {}
    target_new_hp  = None        # 单目标时使用
    aoe_results    = []          # AoE 时每个目标的结果
    conc_logs      = []          # 需要写入的专注检定日志

    is_aoe = spell.get("aoe", False)

    # ══ AoE 法术 ══════════════════════════════════════════
    if is_aoe:
        # 伤害类 AoE
        if spell["type"] == "damage":
            result_damage, dice_detail = spell_service.resolve_damage(req.spell_name, req.spell_level, spell_mod)
            # 确定目标列表
            raw_ids = req.target_ids if req.target_ids is not None else (
                [req.target_id] if req.target_id else []
            )
            # target_ids 为空 → 命中所有存活敌人
            if not raw_ids:
                raw_ids = [e["id"] for e in enemies if e.get("hp_current", 0) > 0]

            save_ability = spell.get("save")
            half_on_save = spell.get("half_on_save", True)

            for tid in raw_ids:
                dmg_this = result_damage
                save_result = None

                # 如果法术有豁免，逐目标豁免检定
                if save_ability:
                    target_enemy = next((e for e in enemies if e["id"] == tid), None)
                    target_char  = None if target_enemy else await db.get(Character, tid)

                    t_derived = (target_enemy.get("derived", {}) if target_enemy
                                 else (target_char.derived or {} if target_char else {}))
                    t_saves   = t_derived.get("saving_throws", {})
                    save_mod  = t_saves.get(save_ability,
                                t_derived.get("ability_modifiers", {}).get(save_ability, 0))

                    from services.dnd_rules import roll_dice as _roll_d20
                    d20 = _roll_d20("1d20")["rolls"][0]
                    save_total = d20 + save_mod
                    saved = save_total >= spell_save_dc
                    save_result = {
                        "ability": save_ability, "dc": spell_save_dc,
                        "d20": d20, "modifier": save_mod, "total": save_total, "success": saved,
                    }
                    if saved and half_on_save:
                        dmg_this = dmg_this // 2

                # 更新 HP
                target_enemy2 = next((e for e in enemies if e["id"] == tid), None)
                if target_enemy2:
                    old_hp = target_enemy2.get("hp_current", 0)
                    target_enemy2["hp_current"] = svc.apply_damage(
                        old_hp, dmg_this,
                        target_enemy2.get("derived", {}).get("hp_max", 10),
                    )
                    aoe_results.append({
                        "target_id":   tid,
                        "target_name": target_enemy2["name"],
                        "damage":      dmg_this,
                        "new_hp":      target_enemy2["hp_current"],
                        "save":        save_result,
                    })
                else:
                    tc = await db.get(Character, tid)
                    if tc:
                        tc.hp_current = svc.apply_damage(
                            tc.hp_current, dmg_this,
                            (tc.derived or {}).get("hp_max", tc.hp_current),
                        )
                        aoe_results.append({
                            "target_id":   tid,
                            "target_name": tc.name,
                            "damage":      dmg_this,
                            "new_hp":      tc.hp_current,
                            "save":        save_result,
                        })
                        cl = await _do_concentration_check(tc, dmg_this, session_id)
                        if cl:
                            conc_logs.append(cl)

            state["enemies"] = enemies
            session.game_state = dict(state); flag_modified(session, "game_state")

        # 치유류 AoE（群体治愈）
        elif spell["type"] == "heal":
            result_heal, dice_detail = spell_service.resolve_heal(req.spell_name, req.spell_level, spell_mod, bonus_healing)
            _roster = CharacterRoster(db, session)
            heal_ids = req.target_ids if req.target_ids else (
                [session.player_character_id] + _roster.companion_ids()
            )
            for tid in heal_ids:
                tc = await db.get(Character, tid)
                if tc:
                    tc.hp_current = svc.apply_heal(
                        tc.hp_current, result_heal,
                        (tc.derived or {}).get("hp_max", tc.hp_current),
                    )
                    aoe_results.append({
                        "target_id": tid, "target_name": tc.name,
                        "heal": result_heal, "new_hp": tc.hp_current,
                    })

    # ══ 单目标法术 ════════════════════════════════════════
    else:
        if spell["type"] == "damage" and (req.target_id or req.target_ids):
            tid = req.target_id or (req.target_ids[0] if req.target_ids else None)
            if tid:
                result_damage, dice_detail = spell_service.resolve_damage(req.spell_name, req.spell_level, spell_mod)
                target_enemy = next((e for e in enemies if e["id"] == tid), None)
                if target_enemy:
                    target_enemy["hp_current"] = svc.apply_damage(
                        target_enemy.get("hp_current", 0), result_damage,
                        target_enemy.get("derived", {}).get("hp_max", 10),
                    )
                    target_new_hp    = target_enemy["hp_current"]
                    state["enemies"] = enemies
                    session.game_state = dict(state); flag_modified(session, "game_state")
                else:
                    tc = await db.get(Character, tid)
                    if tc:
                        tc.hp_current = svc.apply_damage(
                            tc.hp_current, result_damage,
                            (tc.derived or {}).get("hp_max", tc.hp_current),
                        )
                        target_new_hp = tc.hp_current
                        cl = await _do_concentration_check(tc, result_damage, session_id)
                        if cl:
                            conc_logs.append(cl)

        elif spell["type"] == "heal" and (req.target_id or req.target_ids):
            tid = req.target_id or (req.target_ids[0] if req.target_ids else None)
            if tid:
                result_heal, dice_detail = spell_service.resolve_heal(req.spell_name, req.spell_level, spell_mod, bonus_healing)
                tc = await db.get(Character, tid)
                if tc:
                    tc.hp_current = svc.apply_heal(
                        tc.hp_current, result_heal,
                        (tc.derived or {}).get("hp_max", tc.hp_current),
                    )
                    target_new_hp = tc.hp_current

    # ── 专注：施法者开始专注 ──────────────────────────────
    if spell.get("concentration"):
        caster.concentration = req.spell_name

    # ── 组装叙事 ──────────────────────────────────────────
    level_str = f"（{req.spell_level}环）" if not is_cantrip else "（戏法）"
    if is_aoe and aoe_results:
        targets_summary = "、".join(r.get("target_name", "?") for r in aoe_results[:4])
        narration = (
            f"✨ {caster.name} 施放了【{req.spell_name}】{level_str}，"
            f"命中 {targets_summary}{'等' if len(aoe_results) > 4 else ''}！"
            + (f"（单目标最高 {result_damage} 点伤害）" if result_damage else "")
            + (f"（每人恢复 {result_heal} HP）" if result_heal else "")
        )
    else:
        narration = (
            f"✨ {caster.name} 施放了【{req.spell_name}】{level_str}"
            + (f"，造成 {result_damage} 点伤害！" if result_damage else "")
            + (f"，恢复 {result_heal} HP！" if result_heal else "")
        )

    db.add(GameLog(
        session_id  = session_id,
        role        = "player" if caster.is_player else f"companion_{caster.name}",
        content     = narration,
        log_type    = "combat",
        dice_result = {
            "dice": dice_detail, "damage": result_damage, "heal": result_heal,
            "aoe": aoe_results,
        },
    ))
    for cl in conc_logs:
        db.add(cl)

    # ── 标记行动已用，不推进回合 ─────────────────────────────
    if combat_obj:
        if not is_cantrip:
            spell_ts["action_used"] = True
        _save_ts(combat_obj, req.caster_id, spell_ts)

    # ── 检查战斗是否结束 ──────────────────────────────────
    player_check2        = await db.get(Character, session.player_character_id)
    combat_over, outcome = svc.check_combat_over(enemies, player_check2.hp_current if player_check2 else 0)
    if combat_over:
        session.combat_active = False
        # 清理战斗状态记录，防止下次战斗残留旧数据
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs: await db.delete(_old_cs)
        except Exception: pass

    round_number = combat_obj.round_number if combat_obj else 1
    next_index   = combat_obj.current_turn_index if combat_obj else 0

    await db.commit()
    return {
        "narration":        narration,
        "damage":           result_damage,
        "heal":             result_heal,
        "target_id":        req.target_id,
        "target_new_hp":    target_new_hp,
        "aoe_results":      aoe_results,
        "remaining_slots":  new_slots,
        "dice_detail":      dice_detail,
        "dice_result":      {"total": result_damage or result_heal or 0},
        "turn_state":       spell_ts,
        "next_turn_index":  next_index,
        "round_number":     round_number,
        "is_concentration": spell.get("concentration", False),
        "is_aoe":           is_aoe,
        "combat_over":      combat_over,
        "outcome":          outcome,
    }


# ── 状态条件管理 ──────────────────────────────────────────

