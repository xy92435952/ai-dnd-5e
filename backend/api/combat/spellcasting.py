"""
api.combat.spellcasting — legacy direct spell casting endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, GameLog, CombatState
from api.deps import (
    get_session_or_404,
    get_user_id,
    assert_can_act,
)
from services.spell_service import spell_service
from services.character_roster import CharacterRoster
from services.combat_outcome_service import check_and_cleanup_combat_outcome

from api.combat._shared import (
    _DEFAULT_TS,
    _get_ts,
    _save_ts,
    svc,
)
from api.combat.schemas import SpellRequest
from services.combat_spell_effect_service import (
    apply_spell_damage_to_target,
    apply_spell_heal_to_target,
    roll_spell_save,
)
from schemas.combat_responses import CombatActionResult

router = APIRouter(prefix="/game", tags=["combat"])


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

        # 치유류 AoE（群体治愈）
        elif spell["type"] == "heal":
            result_heal, dice_detail = spell_service.resolve_heal(req.spell_name, req.spell_level, spell_mod, bonus_healing)
            _roster = CharacterRoster(db, session)
            heal_ids = req.target_ids if req.target_ids else (
                [session.player_character_id] + _roster.companion_ids()
            )
            for tid in heal_ids:
                applied = await apply_spell_heal_to_target(db, tid, result_heal)
                if applied:
                    aoe_results.append(applied)

    # ══ 单目标法术 ════════════════════════════════════════
    else:
        if spell["type"] == "damage" and (req.target_id or req.target_ids):
            tid = req.target_id or (req.target_ids[0] if req.target_ids else None)
            if tid:
                result_damage, dice_detail = spell_service.resolve_damage(req.spell_name, req.spell_level, spell_mod)
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
                if any(e.get("id") == tid for e in enemies):
                    state["enemies"] = enemies
                    session.game_state = dict(state); flag_modified(session, "game_state")

        elif spell["type"] == "heal" and (req.target_id or req.target_ids):
            tid = req.target_id or (req.target_ids[0] if req.target_ids else None)
            if tid:
                result_heal, dice_detail = spell_service.resolve_heal(req.spell_name, req.spell_level, spell_mod, bonus_healing)
                applied = await apply_spell_heal_to_target(db, tid, result_heal)
                if applied:
                    target_new_hp = applied["new_hp"]

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
    combat_over, outcome = await check_and_cleanup_combat_outcome(
        db,
        session=session,
        session_id=session_id,
        enemies=enemies,
        check_combat_over=svc.check_combat_over,
    )

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
