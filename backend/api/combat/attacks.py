"""
api.combat.attacks — 玩家主动攻击类行动（近战/远程/smite/擒抱/职业特性）

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
from api.combat.attack_modifiers import (
    apply_ranged_close_penalty,
    build_attack_deriveds,
    calculate_cover_bonus,
    choose_feat_power_attack,
)
from api.combat.attack_targeting import get_target_conditions, resolve_attack_target
from api.combat.attack_actions import maybe_handle_pre_attack_action
from api.combat.schemas import (
    CombatActionRequest,
)
from schemas.combat_responses import CombatActionResult

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/action", response_model=CombatActionResult)
async def combat_action(
    session_id: str,
    req:        CombatActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    玩家战斗行动（攻击 / 闪避 / 冲刺 / 脱离接战 / 协助）。
    本端点不再自动推进回合——玩家需明确调用 /end-turn 结束回合。
    """
    action_text = req.action_text
    target_id   = req.target_id
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    await db.refresh(session)  # 确保读取最新 game_state
    player      = await db.get(Character, session.player_character_id)
    player_id   = session.player_character_id
    player_name = player.name if player else "你"
    state       = session.game_state or {}
    enemies     = list(state.get("enemies", []))

    pre_action = await maybe_handle_pre_attack_action(
        session_id=session_id,
        action_text=action_text,
        target_id=target_id,
        db=db,
        session=session,
        combat=combat,
        player=player,
        player_id=player_id,
        player_name=player_name,
        state=state,
        enemies=enemies,
    )
    if pre_action is not None:
        return pre_action

    # ── 获取并检查行动配额 ────────────────────────────────
    ts = _get_ts(combat, player_id)

    # ── 分支：普通攻击 / 远程攻击（含 Extra Attack / Sneak Attack / Fighting Style / Damage Resistance）──
    p_derived   = player.derived or {} if player else {}
    p_class     = _normalize_class(player.char_class) if player else ""
    p_level     = player.level if player else 1

    # Extra Attack: 计算允许的攻击次数
    max_attacks = svc.get_attack_count(p_derived, p_level, p_class)
    ts.setdefault("attacks_made", 0)
    ts["attacks_max"] = max_attacks

    if ts["attacks_made"] >= max_attacks:
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽，请使用「结束回合」")
        raise HTTPException(400, "本回合攻击次数已达上限")

    # 解析目标
    target = await resolve_attack_target(db, target_id, enemies, allow_auto_enemy=True)
    if not target:
        raise HTTPException(400, "没有可攻击的目标")
    target_derived = target.derived
    target_name = target.name
    target_is_enemy = target.is_enemy
    resolved_target_id = target.id

    # 状态条件对攻击的影响
    p_conditions = list(player.conditions or []) if player else []
    t_conditions = await get_target_conditions(db, target, enemies)

    atk_adv, atk_dis = svc.get_attack_modifiers(p_conditions)
    def_adv, def_dis = svc.get_defense_modifiers(t_conditions)

    # 「被协助」→ 攻击优势
    if ts.get("being_helped"):
        atk_adv = True
        ts["being_helped"] = False

    # 远程攻击：相邻敌人存在 → 劣势
    positions = dict(combat.entity_positions or {})
    atk_dis, ranged_penalty = apply_ranged_close_penalty(
        atk_dis=atk_dis,
        is_ranged=req.is_ranged,
        attacker_id=player_id,
        enemies=enemies,
        positions=positions,
        attacker_derived=p_derived,
    )

    # ── Cover bonus (P0-8) ────────────────────────────────
    cover_bonus = calculate_cover_bonus(
        grid_data=dict(combat.grid_data or {}),
        positions=positions,
        attacker_id=player_id,
        target_id=resolved_target_id,
        attacker_derived=p_derived,
        is_ranged=req.is_ranged,
    )

    # ── GWM / Sharpshooter feat power attack (P1-2) ────────
    feat_power = choose_feat_power_attack(
        attacker_derived=p_derived,
        target_derived=target_derived,
        cover_bonus=cover_bonus,
        is_ranged=req.is_ranged,
    )
    feat_power_attack = feat_power.active
    feat_power_bonus_dmg = feat_power.bonus_damage

    # Apply cover bonus to target AC for this attack
    attack_attacker_derived, attack_target_derived = build_attack_deriveds(
        attacker_derived=p_derived,
        target_derived=target_derived,
        cover_bonus=cover_bonus,
        is_ranged=req.is_ranged,
        power=feat_power,
    )

    # 狂暴攻击优势（鲁莽攻击，简化）
    class_res = player.class_resources or {} if player else {}
    is_raging = class_res.get("raging", False)

    # ── Assassinate: first round, advantage vs targets that haven't acted ──
    assassinate_active = False
    p_sub_effects = p_derived.get("subclass_effects", {})
    if p_sub_effects.get("assassinate") and combat.round_number == 1:
        # Check if target hasn't acted yet (its turn_order index > current_turn_index)
        turn_order = list(combat.turn_order or [])
        target_turn_idx = next((i for i, t in enumerate(turn_order) if t.get("character_id") == resolved_target_id), None)
        if target_turn_idx is not None and target_turn_idx >= combat.current_turn_index:
            atk_adv = True
            assassinate_active = True

    attack_result_obj = svc.resolve_melee_attack(
        attacker_derived = attack_attacker_derived,
        target_derived   = attack_target_derived,
        advantage        = atk_adv or def_adv,
        disadvantage     = atk_dis or def_dis,
        is_ranged        = req.is_ranged,
    )
    attack_result_dict = attack_result_obj.attack_roll
    damage             = attack_result_obj.damage
    damage_roll        = attack_result_obj.damage_roll
    extra_damage_notes = []

    # Assassinate auto-crit: if assassinate is active and hit, force crit
    if assassinate_active and attack_result_dict["hit"] and not attack_result_dict["is_crit"]:
        attack_result_dict["is_crit"] = True
        # Add extra crit damage (one extra die)
        hit_die = p_derived.get("hit_die", 8)
        extra_crit = roll_dice(f"1d{hit_die}")
        damage += extra_crit["total"]
        extra_damage_notes.append(f"暗杀暴击+{extra_crit['total']}")

    # ── GWM / Sharpshooter +10 damage ──
    if attack_result_dict["hit"] and feat_power_attack:
        damage += feat_power_bonus_dmg
        feat_name = "巨武器大师" if not req.is_ranged else "神射手"
        extra_damage_notes.append(f"{feat_name}+{feat_power_bonus_dmg}")

    # ── Fighting Style: Dueling bonus ──
    if attack_result_dict["hit"] and not req.is_ranged:
        melee_bonus = p_derived.get("melee_damage_bonus", 0)
        if melee_bonus > 0:
            damage += melee_bonus
            extra_damage_notes.append(f"决斗+{melee_bonus}")

    # ── Rage bonus damage ──
    if attack_result_dict["hit"] and is_raging and not req.is_ranged:
        rage_bonus = svc.get_rage_bonus(p_level)
        damage += rage_bonus
        extra_damage_notes.append(f"狂暴+{rage_bonus}")

    # ── Zealot Divine Fury (first hit per turn while raging) ──
    if attack_result_dict["hit"] and is_raging and p_sub_effects.get("divine_fury") and ts.get("attacks_made", 0) <= 1:
        fury_roll = roll_dice(f"1d6+{p_level // 2}")
        damage += fury_roll["total"]
        extra_damage_notes.append(f"神圣狂怒+{fury_roll['total']}")

    # ── Sneak Attack ──
    sneak_attack_applied = False
    sneak_attack_damage  = 0
    if attack_result_dict["hit"] and p_class == "Rogue":
        has_adv = atk_adv or def_adv
        # Check ally adjacent to target
        _roster = CharacterRoster(db, session)
        ally_list = [{"id": session.player_character_id, "hp_current": player.hp_current if player else 0}]
        for c in await _roster.companions():
            ally_list.append({"id": c.id, "hp_current": c.hp_current})
        ally_adj = _has_ally_adjacent_to(resolved_target_id, player_id, ally_list, positions)

        # Swashbuckler: check if no other enemy is adjacent to target
        is_swashbuckler = p_sub_effects.get("swashbuckler", False)
        no_other_enemy_adj = False
        if is_swashbuckler:
            other_enemies_adj = [e for e in enemies if e["id"] != resolved_target_id and e.get("hp_current", 0) > 0]
            no_other_enemy_adj = not _has_ally_adjacent_to(player_id, resolved_target_id, other_enemies_adj, positions)

        if svc.check_sneak_attack(p_class, has_adv, ally_adj, swashbuckler=is_swashbuckler, no_other_enemy_adjacent=no_other_enemy_adj) and ts.get("attacks_made", 0) == 0:
            # Sneak attack only once per turn
            sa_dice = svc.calc_sneak_attack_dice(p_level)
            sa_roll = roll_dice(f"{sa_dice}d6")
            sneak_attack_damage = sa_roll["total"]
            damage += sneak_attack_damage
            sneak_attack_applied = True
            extra_damage_notes.append(f"偷袭{sa_dice}d6={sneak_attack_damage}")

    # ── Damage Resistance ──
    damage_type = p_derived.get("damage_type", "钝击")
    if attack_result_dict["hit"] and target_is_enemy:
        t_enemy_data = next((e for e in enemies if e["id"] == resolved_target_id), {})
        resistances    = t_enemy_data.get("resistances", [])
        immunities     = t_enemy_data.get("immunities", [])
        vulnerabilities = t_enemy_data.get("vulnerabilities", [])
        damage = svc.apply_damage_with_resistance(damage, damage_type, resistances, immunities, vulnerabilities)

    mechanical_narration = svc._build_narration(player_name, target_name, attack_result_dict, damage)
    if ranged_penalty:
        mechanical_narration = f"（相邻敌人，远程劣势）{mechanical_narration}"
    if extra_damage_notes:
        mechanical_narration += f"（{', '.join(extra_damage_notes)}）"

    # LLM vivid narration for old-path attack
    vivid = await narrate_action(
        actor_name=player_name, actor_class=_normalize_class(player.char_class),
        target_name=target_name, action_type="attack",
        hit=attack_result_dict["hit"], is_crit=attack_result_dict["is_crit"],
        is_fumble=attack_result_dict["is_fumble"], damage=damage,
        damage_type=p_derived.get("damage_type", ""),
        extra_details=", ".join(extra_damage_notes) if extra_damage_notes else "",
    )
    narration = vivid if vivid else mechanical_narration

    # 更新 HP
    conc_log      = None
    target_new_hp = None
    if attack_result_dict["hit"]:
        if target_is_enemy:
            for e in enemies:
                if e["id"] == resolved_target_id:
                    e["hp_current"] = svc.apply_damage(e.get("hp_current", 0), damage, e.get("derived", {}).get("hp_max", 10))
                    target_new_hp   = e["hp_current"]
            state["enemies"]   = enemies
            session.game_state = dict(state); flag_modified(session, "game_state")
        else:
            tchar3 = await db.get(Character, resolved_target_id)
            if tchar3:
                tchar3.hp_current = svc.apply_damage(tchar3.hp_current, damage, (tchar3.derived or {}).get("hp_max", tchar3.hp_current))
                target_new_hp     = tchar3.hp_current
                conc_log          = await _do_concentration_check(tchar3, damage, session_id)

    # ── Dark One's Blessing: Warlock gains temp HP on kill ──
    if target_new_hp is not None and target_new_hp <= 0 and target_is_enemy:
        if p_sub_effects.get("dark_ones_blessing"):
            cha_mod_val = p_derived.get("ability_modifiers", {}).get("cha", 0)
            temp_hp = cha_mod_val + p_level
            extra_damage_notes.append(f"黑暗祝福+{temp_hp}临时HP")

    # 更新攻击计数
    ts["attacks_made"] = ts.get("attacks_made", 0) + 1
    if ts["attacks_made"] >= max_attacks:
        ts["action_used"] = True
    _save_ts(combat, player_id, ts)

    # Extra Attack 提示
    attacks_remaining = max_attacks - ts["attacks_made"]

    db.add(GameLog(
        session_id  = session_id,
        role        = "player",
        content     = narration,
        log_type    = "combat",
        dice_result = {
            "attack": attack_result_dict, "damage": damage_roll,
            "sneak_attack": sneak_attack_damage if sneak_attack_applied else None,
            "extra_damage": extra_damage_notes if extra_damage_notes else None,
        },
    ))
    if conc_log:
        db.add(conc_log)

    # 检查战斗是否结束（不推进回合）
    player_check         = await db.get(Character, session.player_character_id)
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
        "action":               "attack",
        "narration":            narration,
        "attack_result":        attack_result_dict,
        "damage":               damage,
        "target_id":            resolved_target_id,
        "target_new_hp":        target_new_hp,
        "ranged_penalty":       ranged_penalty,
        "cover_bonus":          cover_bonus,
        "feat_power_attack":    feat_power_attack,
        "sneak_attack":         sneak_attack_applied,
        "sneak_attack_damage":  sneak_attack_damage,
        "extra_damage_notes":   extra_damage_notes,
        "attacks_made":         ts["attacks_made"],
        "attacks_max":          max_attacks,
        "attacks_remaining":    attacks_remaining,
        "concentration_check":  conc_log.dice_result if conc_log else None,
        "turn_state":           ts,
        "next_turn_index":      combat.current_turn_index,
        "round_number":         combat.round_number,
        "combat_over":          combat_over,
        "outcome":              outcome,
    }
