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
from api.combat.schemas import (
    MoveRequest, ConditionRequest, CombatActionRequest, DeathSaveRequest,
    SmiteRequest, ClassFeatureRequest, ReactionRequest, GrappleShoveRequest,
    AttackRollRequest, DamageRollRequest, SpellRequest, SpellRollRequest,
    SpellConfirmRequest, ManeuverRequest,
)

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/action")
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

    # ── 获取并检查行动配额 ────────────────────────────────
    ts = _get_ts(combat, player_id)

    # ── 分支：冲刺 ───────────────────────────────────────
    if "冲刺" in action_text:
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"]  = True
        ts["movement_max"] = ts["movement_max"] * 2   # 30ft → 60ft = 12格
        _save_ts(combat, player_id, ts)
        db.add(GameLog(
            session_id=session_id, role="player",
            content=f"{player_name} 使用「冲刺」行动，本回合移动力翻倍！",
            log_type="combat",
        ))
        await db.commit()
        return {
            "action": "dash", "narration": f"{player_name} 使用「冲刺」，移动力翻倍！",
            "turn_state": ts, "combat_over": False, "outcome": None,
        }

    # ── 分支：脱离接战 ────────────────────────────────────
    if "脱离" in action_text or "disengage" in action_text.lower():
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"] = True
        ts["disengaged"]  = True
        _save_ts(combat, player_id, ts)
        db.add(GameLog(
            session_id=session_id, role="player",
            content=f"{player_name} 「脱离接战」，本回合移动不会触发借机攻击。",
            log_type="combat",
        ))
        await db.commit()
        return {
            "action": "disengage", "narration": f"{player_name} 脱离接战。",
            "turn_state": ts, "combat_over": False, "outcome": None,
        }

    # ── 分支：协助 ────────────────────────────────────────
    if "协助" in action_text or "help" in action_text.lower():
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"] = True
        _save_ts(combat, player_id, ts)

        # 给目标队友设置 being_helped
        helped_name = "队友"
        if target_id:
            t_ts = _get_ts(combat, target_id)
            t_ts["being_helped"] = True
            _save_ts(combat, target_id, t_ts)
            tchar = await db.get(Character, target_id)
            if tchar:
                helped_name = tchar.name
        else:
            # 自动选最低 HP 的队友
            _roster = CharacterRoster(db, session)
            best_cid, best_hp_pct = None, 1.1
            for c in await _roster.companions_alive():
                pct = c.hp_current / max(1, (c.derived or {}).get("hp_max", 1))
                if pct < best_hp_pct:
                    best_hp_pct = pct
                    best_cid = c.id
                    helped_name = c.name
            if best_cid:
                t_ts = _get_ts(combat, best_cid)
                t_ts["being_helped"] = True
                _save_ts(combat, best_cid, t_ts)

        db.add(GameLog(
            session_id=session_id, role="player",
            content=f"{player_name} 「协助」{helped_name}，对方下次攻击具有优势！",
            log_type="combat",
        ))
        await db.commit()
        return {
            "action": "help", "narration": f"{player_name} 协助 {helped_name}。",
            "turn_state": ts, "combat_over": False, "outcome": None,
        }

    # ── 分支：闪避 ────────────────────────────────────────
    is_dodge = "闪避" in action_text or "dodge" in action_text.lower()
    if is_dodge:
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"] = True
        _save_ts(combat, player_id, ts)
        narration = f"{player_name} 采取了闪避姿态，专注于躲避攻击。"
        db.add(GameLog(session_id=session_id, role="player",
                       content=narration, log_type="combat"))
        await db.commit()
        return {
            "action": "dodge", "narration": narration,
            "turn_state": ts, "combat_over": False, "outcome": None,
        }

    # ── 分支：副手攻击（附赠行动，双武器战斗）─────────────
    is_offhand_attack = req.is_offhand or "副手" in action_text or "offhand" in action_text.lower()
    if is_offhand_attack:
        if not ts["action_used"]:
            raise HTTPException(400, "副手攻击需要先完成本回合的主手攻击")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        # 解析目标（与普通攻击相同逻辑）
        offhand_target_id    = req.target_id
        offhand_target_name  = ""
        offhand_target_deriv = {}
        offhand_target_enemy = False

        if offhand_target_id:
            otchar = await db.get(Character, offhand_target_id)
            if otchar:
                offhand_target_name, offhand_target_deriv, offhand_target_enemy = (
                    otchar.name, otchar.derived or {}, False
                )
            else:
                oenemy = next((e for e in enemies if e["id"] == offhand_target_id), None)
                if oenemy:
                    offhand_target_name, offhand_target_deriv, offhand_target_enemy = (
                        oenemy["name"], oenemy.get("derived", {}), True
                    )

        if not offhand_target_name:
            alive = [e for e in enemies if e.get("hp_current", 0) > 0]
            if alive:
                offhand_target_name  = alive[0]["name"]
                offhand_target_deriv = alive[0].get("derived", {})
                offhand_target_enemy = True
                offhand_target_id    = alive[0]["id"]

        if not offhand_target_name:
            raise HTTPException(400, "没有可攻击的目标")

        # 副手攻击：is_offhand=True 使伤害不加属性修正（除非有双武器战斗特技）
        offhand_result = svc.resolve_melee_attack(
            attacker_derived = player.derived or {} if player else {},
            target_derived   = offhand_target_deriv,
            is_offhand       = True,
        )

        offhand_conc_log  = None
        offhand_new_hp    = None
        if offhand_result.attack_roll["hit"]:
            if offhand_target_enemy:
                for e in enemies:
                    if e["id"] == offhand_target_id:
                        e["hp_current"] = svc.apply_damage(
                            e.get("hp_current", 0), offhand_result.damage,
                            e.get("derived", {}).get("hp_max", 10),
                        )
                        offhand_new_hp = e["hp_current"]
                state["enemies"]   = enemies
                session.game_state = dict(state); flag_modified(session, "game_state")
            else:
                otchar2 = await db.get(Character, offhand_target_id)
                if otchar2:
                    otchar2.hp_current = svc.apply_damage(
                        otchar2.hp_current, offhand_result.damage,
                        (otchar2.derived or {}).get("hp_max", otchar2.hp_current),
                    )
                    offhand_new_hp   = otchar2.hp_current
                    offhand_conc_log = await _do_concentration_check(
                        otchar2, offhand_result.damage, session_id
                    )

        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)

        offhand_narration = (
            f"【副手攻击】" +
            svc._build_narration(
                player_name, offhand_target_name,
                offhand_result.attack_roll, offhand_result.damage,
            )
        )
        db.add(GameLog(
            session_id  = session_id,
            role        = "player",
            content     = offhand_narration,
            log_type    = "combat",
            dice_result = {
                "attack": offhand_result.attack_roll,
                "damage": offhand_result.damage_roll,
                "offhand": True,
            },
        ))
        if offhand_conc_log:
            db.add(offhand_conc_log)

        offhand_over, offhand_outcome = svc.check_combat_over(
            enemies, (await db.get(Character, session.player_character_id)).hp_current
            if session.player_character_id else 0
        )
        if offhand_over:
            session.combat_active = False

        await db.commit()
        return {
            "action":              "offhand_attack",
            "narration":           offhand_narration,
            "attack_result":       offhand_result.attack_roll,
            "damage":              offhand_result.damage,
            "target_id":           offhand_target_id,
            "target_new_hp":       offhand_new_hp,
            "concentration_check": offhand_conc_log.dice_result if offhand_conc_log else None,
            "turn_state":          ts,
            "combat_over":         offhand_over,
            "outcome":             offhand_outcome,
        }

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
    target_derived     = {}
    target_name        = ""
    target_is_enemy    = False
    resolved_target_id = target_id

    if target_id:
        tchar = await db.get(Character, target_id)
        if tchar:
            target_name, target_derived, target_is_enemy = tchar.name, tchar.derived or {}, False
        else:
            enemy = next((e for e in enemies if e["id"] == target_id), None)
            if enemy:
                target_name, target_derived, target_is_enemy = enemy["name"], enemy.get("derived", {}), True

    if not target_name:
        alive = [e for e in enemies if e.get("hp_current", 0) > 0]
        if alive:
            target_name, target_derived, target_is_enemy = alive[0]["name"], alive[0].get("derived", {}), True
            resolved_target_id = alive[0]["id"]

    if not target_name:
        raise HTTPException(400, "没有可攻击的目标")

    # 状态条件对攻击的影响
    p_conditions = list(player.conditions or []) if player else []
    if target_is_enemy:
        t_enemy      = next((e for e in enemies if e["id"] == resolved_target_id), {})
        t_conditions = t_enemy.get("conditions", [])
    else:
        tchar2       = await db.get(Character, resolved_target_id) if resolved_target_id else None
        t_conditions = list(tchar2.conditions or []) if tchar2 else []

    atk_adv, atk_dis = svc.get_attack_modifiers(p_conditions)
    def_adv, def_dis = svc.get_defense_modifiers(t_conditions)

    # 「被协助」→ 攻击优势
    if ts.get("being_helped"):
        atk_adv = True
        ts["being_helped"] = False

    # 远程攻击：相邻敌人存在 → 劣势
    ranged_penalty = False
    cover_bonus = 0
    positions = dict(combat.entity_positions or {})
    if req.is_ranged:
        if _has_adjacent_enemy(player_id, enemies, positions):
            # Sharpshooter: ignore close-range disadvantage? No, that's Crossbow Expert.
            # Crossbow Expert feat negates adjacent enemy disadvantage
            has_crossbow_expert = p_derived.get("feat_effects", {}).get("Crossbow Expert", {}).get("crossbow_expert", False)
            if not has_crossbow_expert:
                atk_dis        = True
                ranged_penalty = True

    # ── Cover bonus (P0-8) ────────────────────────────────
    grid_data = dict(combat.grid_data or {})
    atk_pos = positions.get(str(player_id))
    tgt_pos = positions.get(str(resolved_target_id))
    if atk_pos and tgt_pos:
        cover_bonus = svc.get_cover_bonus(grid_data, atk_pos, tgt_pos)
        # Sharpshooter ignores half and three-quarters cover
        has_sharpshooter = bool(p_derived.get("feat_effects", {}).get("Sharpshooter"))
        if has_sharpshooter and req.is_ranged:
            cover_bonus = 0

    # ── GWM / Sharpshooter feat power attack (P1-2) ────────
    feat_power_attack = False
    feat_power_bonus_dmg = 0
    feat_power_hit_penalty = 0
    feat_effects = p_derived.get("feat_effects", {})

    # GWM: -5 hit / +10 damage with heavy melee weapons
    if not req.is_ranged and feat_effects.get("Great Weapon Master"):
        # Check if weapon has "heavy" property
        equipped_type = p_derived.get("equipped_weapon_type", "")
        if "heavy" in str(equipped_type).lower() or "two-handed" in str(equipped_type).lower():
            # Auto-apply if target AC is relatively low
            effective_ac = target_derived.get("ac", 13) + cover_bonus
            attack_bonus = p_derived.get("attack_bonus", 3)
            # Apply if we'd still have ~50% hit chance
            if attack_bonus - 5 + 10 >= effective_ac:
                feat_power_attack = True
                feat_power_hit_penalty = 5
                feat_power_bonus_dmg = 10

    # Sharpshooter: -5 hit / +10 damage with ranged weapons
    if req.is_ranged and feat_effects.get("Sharpshooter"):
        effective_ac = target_derived.get("ac", 13) + cover_bonus
        attack_bonus = p_derived.get("ranged_attack_bonus", 3)
        if attack_bonus - 5 + 10 >= effective_ac:
            feat_power_attack = True
            feat_power_hit_penalty = 5
            feat_power_bonus_dmg = 10

    # Apply cover bonus to target AC for this attack
    attack_target_derived = dict(target_derived)
    if cover_bonus > 0:
        attack_target_derived["ac"] = target_derived.get("ac", 10) + cover_bonus

    # Apply feat hit penalty to attacker
    attack_attacker_derived = dict(p_derived)
    if feat_power_attack:
        bonus_key = "ranged_attack_bonus" if req.is_ranged else "attack_bonus"
        attack_attacker_derived[bonus_key] = p_derived.get(bonus_key, 3) - feat_power_hit_penalty

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

    # Assassinate auto-crit: if assassinate is active and hit, force crit
    if assassinate_active and attack_result_dict["hit"] and not attack_result_dict["is_crit"]:
        attack_result_dict["is_crit"] = True
        # Add extra crit damage (one extra die)
        hit_die = p_derived.get("hit_die", 8)
        extra_crit = roll_dice(f"1d{hit_die}")
        damage += extra_crit["total"]
        extra_damage_notes.append(f"暗杀暴击+{extra_crit['total']}")
    extra_damage_notes = []

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


# ── 攻击检定（仅 d20，不掷伤害）──────────────────────────────

@router.post("/combat/{session_id}/attack-roll")
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
    player_id   = req.entity_id
    player_name = player.name
    state       = session.game_state or {}
    enemies     = list(state.get("enemies", []))

    # ── 行动配额检查 ──
    ts = _get_ts(combat, player_id)

    p_derived = player.derived or {}
    p_class   = _normalize_class(player.char_class)
    p_level   = player.level

    # Extra Attack
    max_attacks = svc.get_attack_count(p_derived, p_level, p_class)
    ts.setdefault("attacks_made", 0)
    ts["attacks_max"] = max_attacks

    if ts["attacks_made"] >= max_attacks:
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽，请使用「结束回合」")
        raise HTTPException(400, "本回合攻击次数已达上限")

    # ── 副手攻击检查 ──
    is_offhand = req.is_offhand
    if is_offhand:
        if not ts["action_used"]:
            raise HTTPException(400, "副手攻击需要先完成本回合的主手攻击")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

    # ── 解析目标 ──
    target_derived     = {}
    target_name        = ""
    target_is_enemy    = False
    resolved_target_id = req.target_id

    tchar = await db.get(Character, req.target_id)
    if tchar:
        target_name, target_derived, target_is_enemy = tchar.name, tchar.derived or {}, False
    else:
        enemy = next((e for e in enemies if e["id"] == req.target_id), None)
        if enemy:
            target_name, target_derived, target_is_enemy = enemy["name"], enemy.get("derived", {}), True

    if not target_name:
        raise HTTPException(400, "目标不存在")

    # ── 距离检查 ──
    positions = dict(combat.entity_positions or {})
    atk_pos   = positions.get(str(player_id))
    tgt_pos   = positions.get(str(resolved_target_id))
    is_ranged = req.action_type == 'ranged'
    in_range, dist, range_err = _check_attack_range(atk_pos, tgt_pos, is_ranged)
    if not in_range:
        raise HTTPException(400, range_err)

    # ── 攻击修正 ──
    is_ranged = req.action_type == "ranged"
    p_conditions = list(player.conditions or [])
    if target_is_enemy:
        t_enemy      = next((e for e in enemies if e["id"] == resolved_target_id), {})
        t_conditions = t_enemy.get("conditions", [])
    else:
        tchar2       = await db.get(Character, resolved_target_id) if resolved_target_id else None
        t_conditions = list(tchar2.conditions or []) if tchar2 else []

    atk_adv, atk_dis = svc.get_attack_modifiers(p_conditions)
    def_adv, def_dis = svc.get_defense_modifiers(t_conditions)

    if ts.get("being_helped"):
        atk_adv = True
        ts["being_helped"] = False

    ranged_penalty = False
    positions = dict(combat.entity_positions or {})
    if is_ranged:
        has_crossbow_expert = p_derived.get("feat_effects", {}).get("Crossbow Expert", {}).get("crossbow_expert", False)
        if _has_adjacent_enemy(player_id, enemies, positions) and not has_crossbow_expert:
            atk_dis        = True
            ranged_penalty = True

    # Cover
    grid_data = dict(combat.grid_data or {})
    atk_pos = positions.get(str(player_id))
    tgt_pos = positions.get(str(resolved_target_id))
    cover_bonus = 0
    if atk_pos and tgt_pos:
        cover_bonus = svc.get_cover_bonus(grid_data, atk_pos, tgt_pos)
        has_sharpshooter = bool(p_derived.get("feat_effects", {}).get("Sharpshooter"))
        if has_sharpshooter and is_ranged:
            cover_bonus = 0

    # GWM / Sharpshooter power attack
    feat_power_attack = False
    feat_power_hit_penalty = 0
    feat_power_bonus_dmg = 0
    feat_effects = p_derived.get("feat_effects", {})

    if not is_ranged and feat_effects.get("Great Weapon Master"):
        equipped_type = p_derived.get("equipped_weapon_type", "")
        if "heavy" in str(equipped_type).lower() or "two-handed" in str(equipped_type).lower():
            effective_ac = target_derived.get("ac", 13) + cover_bonus
            attack_bonus = p_derived.get("attack_bonus", 3)
            if attack_bonus - 5 + 10 >= effective_ac:
                feat_power_attack = True
                feat_power_hit_penalty = 5
                feat_power_bonus_dmg = 10

    if is_ranged and feat_effects.get("Sharpshooter"):
        effective_ac = target_derived.get("ac", 13) + cover_bonus
        attack_bonus = p_derived.get("ranged_attack_bonus", 3)
        if attack_bonus - 5 + 10 >= effective_ac:
            feat_power_attack = True
            feat_power_hit_penalty = 5
            feat_power_bonus_dmg = 10

    # Build modified derived dicts for the roll
    attack_target_derived = dict(target_derived)
    if cover_bonus > 0:
        attack_target_derived["ac"] = target_derived.get("ac", 10) + cover_bonus

    attack_attacker_derived = dict(p_derived)
    if feat_power_attack:
        bonus_key = "ranged_attack_bonus" if is_ranged else "attack_bonus"
        attack_attacker_derived[bonus_key] = p_derived.get(bonus_key, 3) - feat_power_hit_penalty

    # Rage reckless attack (simplified)
    class_res = player.class_resources or {}
    is_raging = class_res.get("raging", False)

    # ── Roll ONLY d20 (via roll_attack from dnd_rules) ──
    crit_threshold = attack_attacker_derived.get("crit_threshold", 20)
    from services.dnd_rules import roll_attack as _roll_attack
    final_adv = atk_adv or def_adv
    final_dis = atk_dis or def_dis
    attack_roll_result = _roll_attack(
        attacker  = {"derived": attack_attacker_derived},
        target    = {"derived": attack_target_derived},
        is_ranged = is_ranged,
        advantage = final_adv,
        disadvantage = final_dis,
        crit_threshold = crit_threshold,
    )

    # Frontend dice override: use 3D physics result instead of server roll
    if req.d20_value is not None:
        d20_ov = req.d20_value
        atk_bonus_ov = attack_roll_result["attack_bonus"]
        new_total_ov = d20_ov + atk_bonus_ov
        target_ac_ov = attack_roll_result["target_ac"]
        is_crit_ov = d20_ov >= crit_threshold
        is_fumble_ov = d20_ov == 1
        hit_ov = (not is_fumble_ov) and (is_crit_ov or new_total_ov >= target_ac_ov)
        attack_roll_result = {
            **attack_roll_result,
            "d20": d20_ov,
            "attack_total": new_total_ov,
            "hit": hit_ov,
            "is_crit": is_crit_ov,
            "is_fumble": is_fumble_ov,
        }

    # ── Compute damage dice expression (使用装备武器的 damage_dice) ──
    equipment = player.equipment or {}
    equipped_weapons = equipment.get("weapons", [])
    weapon_damage = None
    weapon_hit_die = p_derived.get("hit_die", 8)
    if equipped_weapons:
        # 使用第一把装备的武器（equipped=true 优先）
        equipped = next((w for w in equipped_weapons if w.get("equipped")), equipped_weapons[0] if equipped_weapons else None)
        if equipped:
            weapon_damage = equipped.get("damage", f"1d{weapon_hit_die}")
    hit_die = weapon_hit_die  # fallback for crit calculation
    mods    = p_derived.get("ability_modifiers", {})
    raw_mod = mods.get("dex", 0) if is_ranged else mods.get("str", 0)
    if is_offhand and not p_derived.get("two_weapon_fighting", False):
        dmg_mod = 0
    else:
        dmg_mod = raw_mod
    if weapon_damage:
        # 装备武器: "1d8" + modifier
        damage_dice = f"{weapon_damage}+{dmg_mod}" if dmg_mod >= 0 else f"{weapon_damage}{dmg_mod}"
    else:
        # 无武器: 使用 hit_die (徒手 1d4 or fallback)
        damage_dice = f"1d{hit_die}+{dmg_mod}" if dmg_mod >= 0 else f"1d{hit_die}{dmg_mod}"

    # ── Generate a pending_attack_id and store in turn_states ──
    pending_id = str(uuid.uuid4())
    pending_attack = {
        "pending_attack_id": pending_id,
        "attacker_id":       player_id,
        "target_id":         resolved_target_id,
        "target_name":       target_name,
        "target_is_enemy":   target_is_enemy,
        "attacker_name":     player_name,
        "attack_roll":       attack_roll_result,
        "is_ranged":         is_ranged,
        "is_offhand":        is_offhand,
        "is_crit":           attack_roll_result["is_crit"],
        "hit":               attack_roll_result["hit"],
        "cover_bonus":       cover_bonus,
        "ranged_penalty":    ranged_penalty,
        "feat_power_attack": feat_power_attack,
        "feat_power_bonus_dmg": feat_power_bonus_dmg,
        "advantage":         final_adv,
        "disadvantage":      final_dis,
        "is_raging":         is_raging,
        "damage_dice":       damage_dice,
        "hit_die":           hit_die,
        "dmg_mod":           dmg_mod,
    }

    # Increment attack count
    ts["attacks_made"] = ts.get("attacks_made", 0) + 1
    if ts["attacks_made"] >= max_attacks:
        ts["action_used"] = True
    if is_offhand:
        ts["bonus_action_used"] = True

    ts["pending_attack"] = pending_attack
    _save_ts(combat, player_id, ts)

    # Generate vivid narration for miss / fumble (hit narration done in damage-roll)
    miss_narration = ""
    if not attack_roll_result["hit"]:
        vivid = await narrate_action(
            actor_name=player_name, actor_class=p_class, target_name=target_name,
            action_type="attack", hit=False,
            is_fumble=attack_roll_result["is_fumble"],
        )
        if vivid:
            miss_narration = vivid
        else:
            miss_narration = svc._build_narration(player_name, target_name, attack_roll_result, 0)
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
        "attack_total":     attack_roll_result["attack_total"],
        "target_ac":        attack_roll_result["target_ac"],
        "hit":              attack_roll_result["hit"],
        "is_crit":          attack_roll_result["is_crit"],
        "is_fumble":        attack_roll_result["is_fumble"],
        "cover_bonus":      cover_bonus,
        "advantage":        final_adv,
        "disadvantage":     final_dis,
        "target_name":      target_name,
        "attacker_name":    player_name,
        "attacks_made":     ts["attacks_made"],
        "attacks_max":      max_attacks,
        "damage_dice":      damage_dice,
        "pending_attack_id": pending_id,
        "turn_state":       ts,
        "narration":        miss_narration,
    }


# ── 伤害骰（读取 pending_attack，掷伤害，扣 HP）──────────────

@router.post("/combat/{session_id}/damage-roll")
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
    # Scan all turn_states to find the matching pending_attack
    all_ts = dict(combat.turn_states or {})
    attacker_entity_id = None
    pending = None
    for eid, ets in all_ts.items():
        pa = ets.get("pending_attack")
        if pa and pa.get("pending_attack_id") == req.pending_attack_id:
            pending = pa
            attacker_entity_id = eid
            break

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

    p_derived = player.derived or {}
    p_class   = _normalize_class(player.char_class)
    p_level   = player.level
    player_name = player.name

    target_id       = pending["target_id"]
    target_name     = pending["target_name"]
    target_is_enemy = pending["target_is_enemy"]
    is_crit         = pending["is_crit"]
    is_ranged       = pending["is_ranged"]
    is_offhand      = pending["is_offhand"]
    hit_die         = pending["hit_die"]
    dmg_mod         = pending["dmg_mod"]
    attack_roll_result = pending["attack_roll"]

    # ── Roll damage ──
    damage_dice_expr = f"1d{hit_die}+{dmg_mod}" if dmg_mod >= 0 else f"1d{hit_die}{dmg_mod}"
    damage_roll_result = roll_dice(damage_dice_expr)
    damage = damage_roll_result["total"]
    damage_rolls = damage_roll_result.get("rolls", [])

    # Frontend dice override: use 3D physics results
    if req.damage_values:
        damage_rolls = req.damage_values
        damage_roll_result["rolls"] = req.damage_values
        damage_roll_result["total"] = sum(req.damage_values) + dmg_mod
        damage = damage_roll_result["total"]

    # Crit: double dice
    crit_extra = 0
    if is_crit:
        extra = roll_dice(f"1d{hit_die}")
        crit_extra = extra["total"]
        damage += crit_extra

    extra_damage_notes = []

    # GWM / Sharpshooter +10
    feat_power_bonus_dmg = pending.get("feat_power_bonus_dmg", 0)
    if pending.get("feat_power_attack") and feat_power_bonus_dmg > 0:
        damage += feat_power_bonus_dmg
        feat_name = "巨武器大师" if not is_ranged else "神射手"
        extra_damage_notes.append(f"{feat_name}+{feat_power_bonus_dmg}")

    # Fighting Style: Dueling bonus
    dueling_bonus = 0
    if not is_ranged:
        melee_bonus = p_derived.get("melee_damage_bonus", 0)
        if melee_bonus > 0:
            damage += melee_bonus
            dueling_bonus = melee_bonus
            extra_damage_notes.append(f"决斗+{melee_bonus}")

    # Rage bonus
    rage_bonus = 0
    if pending.get("is_raging") and not is_ranged:
        rage_bonus = svc.get_rage_bonus(p_level)
        damage += rage_bonus
        extra_damage_notes.append(f"狂暴+{rage_bonus}")

    # Zealot Divine Fury (first hit per turn while raging)
    p_sub_effects = p_derived.get("subclass_effects", {})
    if pending.get("is_raging") and p_sub_effects.get("divine_fury"):
        ts_check_fury = _get_ts(combat, attacker_entity_id)
        if ts_check_fury.get("attacks_made", 1) <= 1:
            fury_roll = roll_dice(f"1d6+{p_level // 2}")
            damage += fury_roll["total"]
            extra_damage_notes.append(f"神圣狂怒+{fury_roll['total']}")

    # Sneak Attack
    sneak_attack_applied = False
    sneak_attack_damage  = 0
    sneak_attack_dice    = ""
    if p_class == "Rogue":
        positions = dict(combat.entity_positions or {})
        has_adv = pending.get("advantage", False)
        _roster = CharacterRoster(db, session)
        ally_list = [{"id": session.player_character_id, "hp_current": player.hp_current}]
        for c in await _roster.companions():
            ally_list.append({"id": c.id, "hp_current": c.hp_current})
        ally_adj = _has_ally_adjacent_to(target_id, attacker_entity_id, ally_list, positions)

        # Swashbuckler: check if no other enemy is adjacent to attacker
        is_swashbuckler = p_sub_effects.get("swashbuckler", False)
        no_other_enemy_adj = False
        if is_swashbuckler:
            other_enemies_adj = [e for e in enemies if e["id"] != target_id and e.get("hp_current", 0) > 0]
            no_other_enemy_adj = not _has_ally_adjacent_to(attacker_entity_id, target_id, other_enemies_adj, positions)

        # Sneak attack only once per turn — check by looking at ts
        ts_check = _get_ts(combat, attacker_entity_id)
        attacks_before = ts_check.get("attacks_made", 1) - 1  # was incremented in attack-roll
        if svc.check_sneak_attack(p_class, has_adv, ally_adj, swashbuckler=is_swashbuckler, no_other_enemy_adjacent=no_other_enemy_adj) and attacks_before == 0:
            sa_dice_count = svc.calc_sneak_attack_dice(p_level)
            sa_roll = roll_dice(f"{sa_dice_count}d6")
            sneak_attack_damage = sa_roll["total"]
            sneak_attack_dice = f"{sa_dice_count}d6"
            damage += sneak_attack_damage
            sneak_attack_applied = True
            extra_damage_notes.append(f"偷袭{sa_dice_count}d6={sneak_attack_damage}")

    # Damage Resistance
    damage_type = p_derived.get("damage_type", "钝击")
    if target_is_enemy:
        t_enemy_data = next((e for e in enemies if e["id"] == target_id), {})
        resistances    = t_enemy_data.get("resistances", [])
        immunities     = t_enemy_data.get("immunities", [])
        vulnerabilities = t_enemy_data.get("vulnerabilities", [])
        damage = svc.apply_damage_with_resistance(damage, damage_type, resistances, immunities, vulnerabilities)

    total_damage = damage

    # Build narration (mechanical fallback)
    mechanical_narration = svc._build_narration(player_name, target_name, attack_roll_result, total_damage)
    if pending.get("ranged_penalty"):
        mechanical_narration = f"（相邻敌人，远程劣势）{mechanical_narration}"
    if extra_damage_notes:
        mechanical_narration += f"（{', '.join(extra_damage_notes)}）"

    # LLM vivid narration (async, fallback to mechanical)
    damage_type = p_derived.get("damage_type", "")
    vivid = await narrate_action(
        actor_name=player_name, actor_class=p_class, target_name=target_name,
        action_type="attack", hit=True, is_crit=is_crit,
        damage=total_damage, damage_type=damage_type,
        extra_details=", ".join(extra_damage_notes) if extra_damage_notes else "",
    )
    narration = vivid if vivid else mechanical_narration

    # ── Apply HP ──
    conc_log      = None
    target_new_hp = None
    if target_is_enemy:
        for e in enemies:
            if e["id"] == target_id:
                e["hp_current"] = svc.apply_damage(
                    e.get("hp_current", 0), total_damage,
                    e.get("derived", {}).get("hp_max", 10),
                )
                target_new_hp = e["hp_current"]
        state["enemies"]   = enemies
        session.game_state = dict(state)
        flag_modified(session, "game_state")
    else:
        tchar = await db.get(Character, target_id)
        if tchar:
            tchar.hp_current = svc.apply_damage(
                tchar.hp_current, total_damage,
                (tchar.derived or {}).get("hp_max", tchar.hp_current),
            )
            target_new_hp = tchar.hp_current
            conc_log = await _do_concentration_check(tchar, total_damage, session_id)

    # ── Dark One's Blessing: Warlock gains temp HP on kill ──
    if target_new_hp is not None and target_new_hp <= 0 and target_is_enemy:
        if p_sub_effects.get("dark_ones_blessing"):
            cha_mod_val = p_derived.get("ability_modifiers", {}).get("cha", 0)
            temp_hp = cha_mod_val + p_level
            extra_damage_notes.append(f"黑暗祝福+{temp_hp}临时HP")

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
            "attack": attack_roll_result,
            "damage": damage_roll_result,
            "sneak_attack": sneak_attack_damage if sneak_attack_applied else None,
            "extra_damage": extra_damage_notes if extra_damage_notes else None,
        },
    ))
    if conc_log:
        db.add(conc_log)

    # ── Check combat over ──
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

    # Check if paladin can smite
    can_smite = p_class in ("Paladin",) and not combat_over

    return {
        "damage_dice":          damage_dice_expr,
        "damage_rolls":         damage_rolls,
        "damage_modifier":      dmg_mod,
        "damage_total":         damage_roll_result["total"],
        "crit_extra":           crit_extra,
        "damage_type":          damage_type,
        "sneak_attack_dice":    sneak_attack_dice if sneak_attack_applied else None,
        "sneak_attack_damage":  sneak_attack_damage if sneak_attack_applied else 0,
        "dueling_bonus":        dueling_bonus,
        "rage_bonus":           rage_bonus,
        "feat_bonus":           feat_power_bonus_dmg,
        "extra_damage_notes":   extra_damage_notes,
        "total_damage":         total_damage,
        "target_new_hp":        target_new_hp,
        "target_id":            target_id,
        "target_name":          target_name,
        "narration":            narration,
        "combat_over":          combat_over,
        "outcome":              outcome,
        "can_smite":            can_smite,
        "concentration_check":  conc_log.dice_result if conc_log else None,
        "turn_state":           ts,
    }


# ── 结束玩家回合（明确���进回合）────────────────────────────


@router.post("/combat/{session_id}/grapple-shove")
async def grapple_shove(
    session_id: str,
    req: GrappleShoveRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Grapple or Shove action. Replaces one attack.
    Grapple: contested Athletics check, success → target grappled (speed=0)
    Shove: contested Athletics check, success → target prone or pushed 5ft
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    player = await db.get(Character, session.player_character_id)
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    player_id = session.player_character_id
    ts = _get_ts(combat, player_id)

    # Uses one attack (or the action if no attacks remain)
    max_attacks = svc.get_attack_count(player.derived or {}, player.level, _normalize_class(player.char_class))
    ts.setdefault("attacks_made", 0)
    ts["attacks_max"] = max_attacks
    if ts["attacks_made"] >= max_attacks:
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        raise HTTPException(400, "本回合攻击次数已达上限")

    state = session.game_state or {}
    enemies = list(state.get("enemies", []))

    # Get target
    target_name = ""
    target_derived = {}
    target_is_enemy = False
    target_skills = []

    tchar = await db.get(Character, req.target_id)
    if tchar:
        target_name = tchar.name
        target_derived = tchar.derived or {}
        target_skills = tchar.proficient_skills or []
    else:
        enemy = next((e for e in enemies if e["id"] == req.target_id), None)
        if enemy:
            target_name = enemy["name"]
            target_derived = enemy.get("derived", {})
            target_is_enemy = True

    if not target_name:
        raise HTTPException(404, "目标不存在")

    p_derived = player.derived or {}
    p_skills = player.proficient_skills or []

    if req.action_type == "grapple":
        result = svc.resolve_grapple(p_derived, target_derived, p_skills, target_skills)
        if result["success"]:
            # Apply grappled condition
            if target_is_enemy:
                for e in enemies:
                    if e["id"] == req.target_id:
                        conds = list(e.get("conditions", []))
                        if "grappled" not in conds:
                            conds.append("grappled")
                        e["conditions"] = conds
                state["enemies"] = enemies
                session.game_state = dict(state); flag_modified(session, "game_state")
            else:
                conds = list(tchar.conditions or [])
                if "grappled" not in conds:
                    conds.append("grappled")
                tchar.conditions = conds

            narration = f"🤼 {player.name} 成功擒抱 {target_name}！{target_name} 速度降为0！"
        else:
            narration = f"🤼 {player.name} 尝试擒抱 {target_name}，但失败了！"

    elif req.action_type == "shove":
        result = svc.resolve_shove(p_derived, target_derived, p_skills, target_skills, req.shove_type)
        if result["success"]:
            if req.shove_type == "prone":
                if target_is_enemy:
                    for e in enemies:
                        if e["id"] == req.target_id:
                            conds = list(e.get("conditions", []))
                            if "prone" not in conds:
                                conds.append("prone")
                            e["conditions"] = conds
                    state["enemies"] = enemies
                    session.game_state = dict(state); flag_modified(session, "game_state")
                else:
                    conds = list(tchar.conditions or [])
                    if "prone" not in conds:
                        conds.append("prone")
                    tchar.conditions = conds
                narration = f"💥 {player.name} 成功推倒 {target_name}！{target_name} 陷入倒地状态！"
            else:
                # Push 5ft away
                positions = dict(combat.entity_positions or {})
                p_pos = positions.get(str(player_id))
                t_pos = positions.get(str(req.target_id))
                if p_pos and t_pos:
                    dx = t_pos["x"] - p_pos["x"]
                    dy = t_pos["y"] - p_pos["y"]
                    # Normalize direction and push 1 tile
                    push_x = t_pos["x"] + (1 if dx > 0 else (-1 if dx < 0 else 0))
                    push_y = t_pos["y"] + (1 if dy > 0 else (-1 if dy < 0 else 0))
                    push_x = max(0, min(19, push_x))
                    push_y = max(0, min(11, push_y))
                    positions[str(req.target_id)] = {"x": push_x, "y": push_y}
                    combat.entity_positions = positions; flag_modified(combat, "entity_positions")
                narration = f"💥 {player.name} 推开 {target_name}！{target_name} 被推后5英尺！"
        else:
            narration = f"💥 {player.name} 尝试推撞 {target_name}，但失败了！"
    else:
        raise HTTPException(400, f"未知动作类型：{req.action_type}")

    # Count as one attack
    ts["attacks_made"] = ts.get("attacks_made", 0) + 1
    if ts["attacks_made"] >= max_attacks:
        ts["action_used"] = True
    _save_ts(combat, player_id, ts)

    # LLM vivid narration for grapple/shove
    vivid = await narrate_action(
        actor_name=player.name, actor_class=_normalize_class(player.char_class),
        target_name=target_name, action_type=req.action_type,
        hit=result["success"],
    )
    if vivid:
        narration = vivid

    db.add(GameLog(
        session_id=session_id, role="player",
        content=narration, log_type="combat",
        dice_result={
            "type": req.action_type,
            "success": result["success"],
            "attacker_roll": result["attacker_roll"],
            "target_roll": result["target_roll"],
        },
    ))
    await db.commit()

    return {
        "action": req.action_type,
        "success": result["success"],
        "narration": narration,
        "attacker_roll": result["attacker_roll"],
        "target_roll": result["target_roll"],
        "turn_state": ts,
        "combat_over": False,
        "outcome": None,
    }


# ── 神圣斩击 (Divine Smite) ───────────────────────────────

@router.post("/combat/{session_id}/smite")
async def divine_smite(
    session_id: str,
    req: SmiteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    Paladin Divine Smite -- 成功命中后追加辐光伤害。
    前端在攻击命中后弹出选择，玩家决定消耗法术位。
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    # 多人联机：根据 user_id 查找该用户在房间内绑定的角色
    if session.is_multiplayer:
        from models import SessionMember
        member_q = await db.execute(
            select(SessionMember).where(
                SessionMember.session_id == session_id,
                SessionMember.user_id == user_id,
            )
        )
        member = member_q.scalar_one_or_none()
        if not member or not member.character_id:
            raise HTTPException(403, "你在该房间没有绑定角色")
        player = await db.get(Character, member.character_id)
    else:
        player = await db.get(Character, session.player_character_id)
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    p_class = _normalize_class(player.char_class)
    if p_class != "Paladin":
        raise HTTPException(400, "只有圣武士可以使用神圣斩击")

    # 消耗法术位
    slot_key = ["1st", "2nd", "3rd", "4th", "5th"][min(req.slot_level - 1, 4)]
    current_slots = dict(player.spell_slots or {})
    available = current_slots.get(slot_key, 0)
    if available <= 0:
        raise HTTPException(400, f"没有可用的{slot_key}环法术位")
    current_slots[slot_key] = available - 1
    player.spell_slots = current_slots

    # 计算斩击伤害
    smite = svc.calc_divine_smite_damage(req.slot_level, req.target_is_undead)

    # 前端骰子物理结果覆盖
    if req.damage_values:
        smite["damage"] = sum(req.damage_values)

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()

    state   = session.game_state or {}
    enemies = list(state.get("enemies", []))

    # 确定斩击目标：优先用前端传入的 target_id
    smite_target_id = req.target_id
    if not smite_target_id:
        # Fallback：从 pending_attack 或最近日志推断
        if combat:
            all_ts = dict(combat.turn_states or {})
            player_ts = all_ts.get(str(session.player_character_id), {})
            smite_target_id = player_ts.get("last_attack_target")
        if not smite_target_id:
            # 最后兜底：第一个存活敌人
            for e in enemies:
                if e.get("hp_current", 0) > 0:
                    smite_target_id = e["id"]
                    break

    # 对目标施加伤害
    target_new_hp = None
    target_name   = "目标"
    smite_applied = False
    for e in enemies:
        if str(e.get("id")) != str(smite_target_id):
            continue
        if e.get("hp_current", 0) <= 0:
            continue
        e["hp_current"] = svc.apply_damage(
            e.get("hp_current", 0), smite["damage"],
            e.get("derived", {}).get("hp_max", 10),
        )
        target_new_hp = e["hp_current"]
        target_name   = e["name"]
        smite_applied = True
        break

    if not smite_applied:
        current_slots[slot_key] = available
        player.spell_slots = current_slots
        raise HTTPException(400, "没有可施加斩击的目标")

    state["enemies"]   = enemies
    session.game_state = dict(state); flag_modified(session, "game_state")

    undead_note = "（对亡灵/邪魔额外+1d8）" if req.target_is_undead else ""
    mechanical_narration = f"✨ {player.name} 释放神圣斩击！{smite['dice']}辐光伤害{undead_note}，对 {target_name} 造成 {smite['damage']} 点伤害！"

    vivid = await narrate_action(
        actor_name=player.name, actor_class=_normalize_class(player.char_class),
        target_name=target_name, action_type="smite",
        damage=smite["damage"], damage_type="辐光",
    )
    narration = vivid if vivid else mechanical_narration

    db.add(GameLog(
        session_id  = session_id,
        role        = "player",
        content     = narration,
        log_type    = "combat",
        dice_result = {"type": "divine_smite", "slot_level": req.slot_level, **smite},
    ))

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
        "action":          "divine_smite",
        "narration":       narration,
        "smite_damage":    smite["damage"],
        "smite_dice":      smite["dice"],
        "target_name":     target_name,
        "target_new_hp":   target_new_hp,
        "remaining_slots": current_slots,
        "combat_over":     combat_over,
        "outcome":         outcome,
    }


# ── 职业特性 (Class Features) ─────────────────────────────

@router.post("/combat/{session_id}/class-feature")
async def use_class_feature(
    session_id: str,
    req: ClassFeatureRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    使用职业战斗特性：
    - second_wind:  Fighter 1+, 恢复 1d10+level HP, 附赠行动, 每短休1次
    - action_surge: Fighter 2+, 本回合获得额外行动, 每短休1次
    - rage:         Barbarian 1+, 进入/退出狂暴, 附赠行动
    - cunning_action_dash: Rogue 2+, 附赠行动冲刺
    - cunning_action_disengage: Rogue 2+, 附赠行动脱离
    - cunning_action_hide: Rogue 2+, 附赠行动隐匿
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    player = await db.get(Character, session.player_character_id)
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    player_id = session.player_character_id
    ts = _get_ts(combat, player_id)
    p_class = _normalize_class(player.char_class)
    p_level = player.level
    derived = player.derived or {}
    class_res = dict(player.class_resources or {})

    feature = req.feature_name
    narration = ""
    dice_roll = None  # {faces, result, label} for frontend dice animation

    # ── Second Wind (Fighter) ─────────────────────────────
    if feature == "second_wind":
        if p_class != "Fighter":
            raise HTTPException(400, "只有战士可以使用活力恢复")
        if class_res.get("second_wind_used", False):
            raise HTTPException(400, "本次休息后已使用过活力恢复")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        heal_roll = roll_dice(f"1d10+{p_level}")
        heal_amt  = heal_roll["total"]
        hp_max    = derived.get("hp_max", player.hp_current)
        old_hp    = player.hp_current
        player.hp_current = min(hp_max, player.hp_current + heal_amt)

        class_res["second_wind_used"] = True
        player.class_resources = class_res
        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)

        narration = f"🛡️ {player.name} 使用「活力恢复」！1d10+{p_level}={heal_amt}，恢复 {player.hp_current - old_hp} HP（{player.hp_current}/{hp_max}）"
        dice_roll = {"faces": 10, "result": heal_amt, "label": f"活力恢复 1d10+{p_level}"}

    # ── Action Surge (Fighter) ────────────────────────────
    elif feature == "action_surge":
        if p_class != "Fighter":
            raise HTTPException(400, "只有战士可以使用行动奔涌")
        if p_level < 2:
            raise HTTPException(400, "需要战士2级以上才能使用行动奔涌")
        if class_res.get("action_surge_used", False):
            raise HTTPException(400, "本次休息后已使用过行动奔涌")

        class_res["action_surge_used"] = True
        player.class_resources = class_res
        # 重置行动配额（不重置移动力和附赠行动）
        ts["action_used"]  = False
        ts["attacks_made"]  = 0
        _save_ts(combat, player_id, ts)

        narration = f"⚡ {player.name} 使用「行动奔涌」！本回合获得额外一次完整行动！"

    # ── Rage (Barbarian) ──────────────────────────────────
    elif feature == "rage":
        if p_class != "Barbarian":
            raise HTTPException(400, "只有野蛮人可以使用狂暴")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        is_raging = class_res.get("raging", False)
        if is_raging:
            # 退出狂暴
            class_res["raging"] = False
            player.class_resources = class_res
            # 移除 rage 给的伤害抗性条件
            conditions = list(player.conditions or [])
            player.conditions = [c for c in conditions if c != "raging"]
            narration = f"😤 {player.name} 停止了狂暴。"
        else:
            # 进入狂暴
            rage_remaining = class_res.get("rage_remaining", svc.get_rage_uses(p_level))
            if rage_remaining <= 0:
                raise HTTPException(400, "狂暴次数已用尽（长休后恢复）")
            class_res["raging"] = True
            class_res["rage_remaining"] = rage_remaining - 1
            player.class_resources = class_res
            ts["bonus_action_used"] = True
            _save_ts(combat, player_id, ts)
            rage_bonus = svc.get_rage_bonus(p_level)
            narration = f"🔥 {player.name} 进入狂暴！近战伤害+{rage_bonus}，物理伤害抗性！（剩余{rage_remaining - 1}次）"

    # ── Cunning Action — Dash (Rogue) ─────────────────────
    elif feature == "cunning_action_dash":
        if p_class != "Rogue":
            raise HTTPException(400, "只有游荡者可以使用灵巧动作")
        if p_level < 2:
            raise HTTPException(400, "需要游荡者2级以上才能使用灵巧动作")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        ts["bonus_action_used"] = True
        ts["movement_max"]      = ts["movement_max"] * 2
        _save_ts(combat, player_id, ts)
        narration = f"💨 {player.name} 使用「灵巧动作-冲刺」！移动力翻倍！"

    # ── Cunning Action — Disengage (Rogue) ────────────────
    elif feature == "cunning_action_disengage":
        if p_class != "Rogue":
            raise HTTPException(400, "只有游荡者可以使用灵巧动作")
        if p_level < 2:
            raise HTTPException(400, "需要游荡者2级以上才能使用灵巧动作")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        ts["bonus_action_used"] = True
        ts["disengaged"]        = True
        _save_ts(combat, player_id, ts)
        narration = f"💨 {player.name} 使用「灵巧动作-脱离」！本回合移动不触发借机攻击。"

    # ── Cunning Action — Hide (Rogue) ─────────────────────
    elif feature == "cunning_action_hide":
        if p_class != "Rogue":
            raise HTTPException(400, "只有游荡者可以使用灵巧动作")
        if p_level < 2:
            raise HTTPException(400, "需要游荡者2级以上才能使用灵巧动作")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)
        # 添加隐匿条件（攻击时获得优势）
        conditions = list(player.conditions or [])
        if "hidden" not in conditions:
            conditions.append("hidden")
            player.conditions = conditions
        narration = f"🫥 {player.name} 使用「灵巧动作-隐匿」！下次攻击获得优势！"

    # ── Fighting Spirit (Samurai Fighter) ────────────────
    elif feature == "fighting_spirit":
        if not (p_class == "Fighter"):
            raise HTTPException(400, "非战士无法使用战意")
        fs_rem = class_res.get("fighting_spirit_remaining", 0)
        if fs_rem <= 0:
            raise HTTPException(400, "战意次数已用完")
        class_res["fighting_spirit_remaining"] = fs_rem - 1
        # Grant advantage on all attacks this turn + temp HP = fighter level
        ts["fighting_spirit_active"] = True
        _save_ts(combat, player_id, ts)
        player.class_resources = class_res
        narration = f"⚔️ {player.name} 集中精神，燃起不屈的战意！本回合所有攻击获得优势，获得 {player.level} 点临时生命值。"

    # ── Bardic Inspiration (Bard) ─────────────────────────
    elif feature == "bardic_inspiration":
        if not (p_class == "Bard"):
            raise HTTPException(400, "非吟游诗人无法使用灵感骰")
        bi_rem = class_res.get("bardic_inspiration_remaining", 0)
        if bi_rem <= 0:
            raise HTTPException(400, "灵感骰次数已用完")
        class_res["bardic_inspiration_remaining"] = bi_rem - 1
        derived = player.derived or {}
        die = derived.get("subclass_effects", {}).get("inspiration_die", "d6")
        bi_faces = int(die.replace("d", "")) if die.startswith("d") else 6
        bi_roll = roll_dice(die)
        player.class_resources = class_res
        narration = f"🎵 {player.name} 演奏了一段鼓舞人心的旋律！一名盟友获得 {die} 灵感骰（{bi_roll['rolls'][0]}）。"
        dice_roll = {"faces": bi_faces, "result": bi_roll["rolls"][0], "label": f"灵感骰 {die}"}

    # ── Ki: Flurry of Blows (Monk, 1 ki) ─────────────────
    elif feature == "ki_flurry":
        if not (p_class == "Monk"):
            raise HTTPException(400, "非武僧无法使用疾风连击")
        ki = class_res.get("ki_remaining", 0)
        if ki < 1:
            raise HTTPException(400, "气不足")
        class_res["ki_remaining"] = ki - 1
        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)
        # Roll 2 unarmed attacks
        d = player.derived or {}
        atk_mod = d.get("attack_bonus", 2)
        martial_die = "1d4" if player.level < 5 else ("1d6" if player.level < 11 else ("1d8" if player.level < 17 else "1d10"))
        results = []
        for i in range(2):
            atk = roll_dice("1d20")
            hit_total = atk["rolls"][0] + atk_mod
            results.append(f"攻击{i+1}: d20={atk['rolls'][0]}+{atk_mod}={hit_total}")
        player.class_resources = class_res
        narration = f"👊 {player.name} 以气驱动疾风连击！{' | '.join(results)}"
        dice_roll = {"faces": 20, "result": roll_dice("1d20")["rolls"][0], "label": "疾风连击"}

    # ── Ki: Stunning Strike (Monk, 1 ki) ──────────────────
    elif feature == "ki_stunning_strike":
        if not (p_class == "Monk"):
            raise HTTPException(400, "非武僧无法使用震慑打击")
        ki = class_res.get("ki_remaining", 0)
        if ki < 1:
            raise HTTPException(400, "气不足")
        class_res["ki_remaining"] = ki - 1
        player.class_resources = class_res
        ki_dc = 8 + derived.get("proficiency_bonus", 2) + derived.get("ability_modifiers", {}).get("wis", 0)
        narration = f"💥 {player.name} 将气灌注于一击之中！目标必须进行 DC{ki_dc} 体质豁免，失败则被震慑至你的下一回合结束。"
        dice_roll = {"faces": 20, "result": ki_dc, "label": f"震慑打击 DC{ki_dc}"}

    # ── Shadow Step (Shadow Monk, 2 ki) ───────────────────
    elif feature == "shadow_step":
        if not (p_class == "Monk"):
            raise HTTPException(400, "非武僧无法使用暗影步")
        ki = class_res.get("ki_remaining", 0)
        if ki < 2:
            raise HTTPException(400, "气不足（需要2点）")
        class_res["ki_remaining"] = ki - 2
        player.class_resources = class_res
        narration = f"🌑 {player.name} 融入阴影之中，瞬间出现在另一片黑暗处！下一次近战攻击获得优势。"
        dice_roll = {"faces": 20, "result": roll_dice("1d20")["rolls"][0], "label": "暗影步"}

    # ── Channel Divinity (Paladin) ────────────────────────
    elif feature == "channel_divinity":
        if not (p_class == "Paladin"):
            raise HTTPException(400, "非圣武士无法引导神力")
        if class_res.get("channel_divinity_used"):
            raise HTTPException(400, "引导神力已使用（每次短休恢复）")
        class_res["channel_divinity_used"] = True
        sub_effects = (player.derived or {}).get("subclass_effects", {})
        if sub_effects.get("devotion"):
            narration = f"✨ {player.name} 引导神力——神圣武器！武器散发圣光，攻击加上魅力修正，持续1分钟。"
        elif sub_effects.get("vengeance"):
            narration = f"⚔️ {player.name} 引导神力——仇敌誓约！标记一个目标，对其攻击获得优势，持续1分钟。"
            ts["vow_of_enmity_active"] = True
            _save_ts(combat, player_id, ts)
        elif sub_effects.get("ancients"):
            narration = f"🌿 {player.name} 引导神力——自然之怒！藤蔓缠绕目标使其束缚！"
        elif sub_effects.get("glory"):
            narration = f"🌟 {player.name} 引导神力——鼓舞冲锋！30尺内盟友移动速度+10尺，持续10分钟。"
        else:
            narration = f"✨ {player.name} 引导神力！"
        player.class_resources = class_res

    # ── Lay on Hands (Paladin) ────────────────────────────
    elif feature == "lay_on_hands":
        if not (p_class == "Paladin"):
            raise HTTPException(400, "非圣武士无法使用圣手")
        pool = class_res.get("lay_on_hands_remaining", 0)
        if pool <= 0:
            raise HTTPException(400, "圣手治疗池已耗尽")
        # Heal 5 HP (or remaining pool, whichever is less)
        heal_amount = min(5, pool)
        class_res["lay_on_hands_remaining"] = pool - heal_amount
        hp_max = (player.derived or {}).get("hp_max", player.hp_current)
        player.hp_current = min(hp_max, player.hp_current + heal_amount)
        player.class_resources = class_res
        narration = f"🤲 {player.name} 将圣光注入伤口，恢复了 {heal_amount} 点生命值！（剩余治疗池: {pool - heal_amount}）"
        dice_roll = {"faces": 20, "result": heal_amount, "label": f"圣手治疗 +{heal_amount}HP"}

    # ── War Priest Attack (War Cleric) ────────────────────
    elif feature == "war_priest_attack":
        if not (p_class == "Cleric"):
            raise HTTPException(400, "非牧师无法使用战争牧师")
        wp_rem = class_res.get("war_priest_remaining", 0)
        if wp_rem <= 0:
            raise HTTPException(400, "战争牧师额外攻击次数已用完")
        class_res["war_priest_remaining"] = wp_rem - 1
        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)
        player.class_resources = class_res
        narration = f"⚔️ {player.name} 以战神之名发动额外攻击！本回合可用附赠动作进行一次武器攻击。"

    # ── Destructive Wrath (Tempest Cleric) ────────────────
    elif feature == "destructive_wrath":
        if not (p_class == "Cleric"):
            raise HTTPException(400, "非牧师无法使用毁灭之怒")
        if class_res.get("channel_divinity_used"):
            raise HTTPException(400, "引导神力已使用")
        class_res["channel_divinity_used"] = True
        ts["destructive_wrath_active"] = True
        _save_ts(combat, player_id, ts)
        player.class_resources = class_res
        narration = f"⚡ {player.name} 引导神力——毁灭之怒！下一次闪电或雷鸣伤害将自动取最大值！"

    # ── Wild Shape (Moon Druid) ───────────────────────────
    elif feature == "wild_shape":
        if not (p_class == "Druid"):
            raise HTTPException(400, "非德鲁伊无法使用野性形态")
        ws_rem = class_res.get("wild_shape_remaining", 0)
        if ws_rem <= 0:
            raise HTTPException(400, "野性形态次数已用完")
        class_res["wild_shape_remaining"] = ws_rem - 1
        sub_effects = (player.derived or {}).get("subclass_effects", {})
        max_cr = sub_effects.get("wild_shape_max_cr", 0.25)
        # Default to Bear form
        from services.dnd_rules import WILD_SHAPE_FORMS
        form_name = "Bear" if max_cr >= 1 else "Wolf"
        form = WILD_SHAPE_FORMS.get(form_name, {})
        class_res["wild_shape_active"] = form_name
        class_res["wild_shape_hp"] = form.get("hp", 20)
        player.class_resources = class_res
        narration = f"🐻 {player.name} 的身体扭曲变化，化身为{form_name}！获得 {form.get('hp',20)} 点额外生命值，AC {form.get('ac',12)}。"
        dice_roll = {"faces": 20, "result": form.get("hp", 20), "label": f"野性形态·{form_name}"}

    # ── Symbiotic Entity (Spores Druid) ───────────────────
    elif feature == "symbiotic_entity":
        if not (p_class == "Druid"):
            raise HTTPException(400, "非德鲁伊无法激活共生实体")
        ws_rem = class_res.get("wild_shape_remaining", 0)
        if ws_rem <= 0:
            raise HTTPException(400, "需要消耗一次野性形态")
        class_res["wild_shape_remaining"] = ws_rem - 1
        temp_hp = (player.derived or {}).get("subclass_effects", {}).get("symbiotic_temp_hp", 4 * player.level)
        class_res["symbiotic_entity_active"] = True
        player.class_resources = class_res
        narration = f"🍄 {player.name} 激活共生实体！孢子覆盖全身，获得 {temp_hp} 点临时生命值，近战附加毒素伤害。"
        dice_roll = {"faces": 20, "result": temp_hp, "label": f"共生实体 +{temp_hp}临时HP"}

    # ── Tides of Chaos (Wild Magic Sorcerer) ──────────────
    elif feature == "tides_of_chaos":
        if not (p_class == "Sorcerer"):
            raise HTTPException(400, "非术士无法使用混沌之潮")
        if class_res.get("tides_of_chaos_used"):
            raise HTTPException(400, "混沌之潮已使用（每次长休恢复）")
        class_res["tides_of_chaos_used"] = True
        ts["tides_of_chaos_active"] = True  # Next d20 roll gets advantage
        _save_ts(combat, player_id, ts)
        player.class_resources = class_res
        narration = f"🌀 {player.name} 引导体内不稳定的魔法能量！下一次攻击/检定/豁免获得优势。但这可能触发野蛮魔法涌动..."

    # ── Portent (Divination Wizard) ───────────────────────
    elif feature == "portent":
        if not (p_class == "Wizard"):
            raise HTTPException(400, "非法师无法使用预言骰")
        p_rem = class_res.get("portent_remaining", 0)
        if p_rem <= 0:
            raise HTTPException(400, "预言骰已用完（每次长休恢复）")
        class_res["portent_remaining"] = p_rem - 1
        portent_roll = roll_dice("1d20")
        class_res["portent_value"] = portent_roll["rolls"][0]
        player.class_resources = class_res
        narration = f"🔮 {player.name} 预见了命运的走向——预言骰: {portent_roll['rolls'][0]}！可以用此值替换任意一次d20检定。"
        dice_roll = {"faces": 20, "result": portent_roll["rolls"][0], "label": "预言骰"}

    else:
        raise HTTPException(400, f"未知职业特性：{feature}")

    # LLM vivid narration for class features
    vivid = await narrate_action(
        actor_name=player.name, actor_class=p_class,
        target_name="",
        action_type="class_feature",
        extra_details=narration,
    )
    if vivid:
        narration = vivid

    db.add(GameLog(
        session_id  = session_id,
        role        = "player",
        content     = narration,
        log_type    = "combat",
        dice_result = {"type": "class_feature", "feature": feature},
    ))
    await db.commit()

    return {
        "action":          "class_feature",
        "feature":         feature,
        "narration":       narration,
        "turn_state":      ts,
        "class_resources": class_res,
        "hp_current":      player.hp_current,
        "hp_max":          derived.get("hp_max", player.hp_current),
        "dice_roll":       dice_roll,
    }


# ── AI 回合 ───────────────────────────────────────────────


@router.post("/combat/{session_id}/maneuver")
async def use_maneuver(session_id: str, req: ManeuverRequest, db: AsyncSession = Depends(get_db)):
    """
    Battle Master maneuver: consume 1 superiority die and apply effect.
    Maneuvers: precision, trip, disarm, riposte, menacing, pushing, goading
    """
    session = await get_session_or_404(session_id, db)
    result_db = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = result_db.scalars().first()
    if not combat:
        raise HTTPException(404, "当前没有进行中的战斗")

    turn_order = combat.turn_order or []
    if not turn_order:
        raise HTTPException(400, "无回合顺序")

    current_entry = turn_order[combat.current_turn_index % len(turn_order)]
    actor_id = str(current_entry.get("character_id", ""))

    # Verify actor is a Battle Master
    actor_char = await db.get(Character, actor_id)
    if not actor_char:
        raise HTTPException(404, "当前行动角色不存在")
    derived = actor_char.derived or {}
    sub_effects = derived.get("subclass_effects", {})
    if not sub_effects.get("battle_master"):
        raise HTTPException(400, "当前角色不是战争大师，无法使用战技")

    # Check superiority dice remaining
    class_resources = dict(actor_char.class_resources or {})
    sd_remaining = class_resources.get("superiority_dice_remaining", 0)
    if sd_remaining <= 0:
        raise HTTPException(400, "优势骰已耗尽（短休后恢复）")

    # Validate maneuver name
    valid_maneuvers = sub_effects.get("maneuvers", [])
    if req.maneuver_name not in valid_maneuvers:
        raise HTTPException(400, f"无效战技: {req.maneuver_name}，可用: {valid_maneuvers}")

    # Consume 1 superiority die
    class_resources["superiority_dice_remaining"] = sd_remaining - 1
    actor_char.class_resources = class_resources

    # Roll superiority die
    sd_die = sub_effects.get("superiority_die", "d8")
    sd_roll = roll_dice(sd_die)
    sd_value = sd_roll["total"]

    # Resolve target
    game_state = session.game_state or {}
    enemies = game_state.get("enemies", [])
    target_enemy = None
    target_char = None
    target_name = "Unknown"
    target_is_enemy = False

    for e in enemies:
        if str(e.get("id")) == req.target_id:
            target_enemy = e
            target_name = e.get("name", "Enemy")
            target_is_enemy = True
            break
    if not target_enemy:
        target_char = await db.get(Character, req.target_id)
        if target_char:
            target_name = target_char.name

    maneuver_result = {
        "maneuver": req.maneuver_name,
        "superiority_die_roll": sd_value,
        "superiority_die": sd_die,
        "dice_remaining": sd_remaining - 1,
        "actor": actor_char.name,
        "target": target_name,
    }

    actor_derived = derived
    prof = actor_derived.get("proficiency_bonus", 2)
    # Maneuver save DC = 8 + prof + max(STR, DEX)
    spell_dc = 8 + prof + max(
        actor_derived.get("ability_modifiers", {}).get("str", 0),
        actor_derived.get("ability_modifiers", {}).get("dex", 0),
    )

    if req.maneuver_name == "precision":
        maneuver_result["effect"] = f"下次攻击骰+{sd_value}"
        maneuver_result["attack_bonus"] = sd_value
        msg = f"⚔️ {actor_char.name} 使用精准打击，攻击骰+{sd_value}"

    elif req.maneuver_name == "trip":
        save_roll = random.randint(1, 20)
        target_str_mod = 0
        if target_enemy:
            t_scores = target_enemy.get("ability_scores", {})
            target_str_mod = (t_scores.get("str", 10) - 10) // 2
        elif target_char:
            target_str_mod = (target_char.derived or {}).get("ability_modifiers", {}).get("str", 0)
        save_total = save_roll + target_str_mod
        tripped = save_total < spell_dc
        maneuver_result["save_roll"] = save_roll
        maneuver_result["save_total"] = save_total
        maneuver_result["dc"] = spell_dc
        maneuver_result["tripped"] = tripped
        maneuver_result["extra_damage"] = sd_value
        if tripped:
            msg = f"⚔️ {actor_char.name} 使用绊摔攻击！{target_name} 摔倒（俯卧），额外伤害{sd_value}"
            if target_enemy:
                t_conds = target_enemy.get("conditions", [])
                if "prone" not in t_conds:
                    t_conds.append("prone")
                    target_enemy["conditions"] = t_conds
                    session.game_state = game_state
            elif target_char:
                t_conds = list(target_char.conditions or [])
                if "prone" not in t_conds:
                    t_conds.append("prone")
                    target_char.conditions = t_conds
        else:
            msg = f"⚔️ {actor_char.name} 使用绊摔攻击，{target_name} 站稳了！额外伤害{sd_value}"

    elif req.maneuver_name == "disarm":
        save_roll = random.randint(1, 20)
        target_str_mod = 0
        if target_enemy:
            t_scores = target_enemy.get("ability_scores", {})
            target_str_mod = (t_scores.get("str", 10) - 10) // 2
        elif target_char:
            target_str_mod = (target_char.derived or {}).get("ability_modifiers", {}).get("str", 0)
        save_total = save_roll + target_str_mod
        disarmed = save_total < spell_dc
        maneuver_result["save_roll"] = save_roll
        maneuver_result["save_total"] = save_total
        maneuver_result["dc"] = spell_dc
        maneuver_result["disarmed"] = disarmed
        if disarmed:
            msg = f"⚔️ {actor_char.name} 使用缴械打击！{target_name} 武器脱手！"
        else:
            msg = f"⚔️ {actor_char.name} 使用缴械打击，{target_name} 握紧了武器"

    elif req.maneuver_name == "riposte":
        maneuver_result["extra_damage"] = sd_value
        maneuver_result["effect"] = "反击攻击"
        msg = f"⚔️ {actor_char.name} 使用反击！额外伤害+{sd_value}"

    elif req.maneuver_name == "menacing":
        save_roll = random.randint(1, 20)
        target_wis_mod = 0
        if target_enemy:
            t_scores = target_enemy.get("ability_scores", {})
            target_wis_mod = (t_scores.get("wis", 10) - 10) // 2
        elif target_char:
            target_wis_mod = (target_char.derived or {}).get("ability_modifiers", {}).get("wis", 0)
        save_total = save_roll + target_wis_mod
        frightened = save_total < spell_dc
        maneuver_result["save_roll"] = save_roll
        maneuver_result["save_total"] = save_total
        maneuver_result["dc"] = spell_dc
        maneuver_result["frightened"] = frightened
        maneuver_result["extra_damage"] = sd_value
        if frightened:
            msg = f"⚔️ {actor_char.name} 使用威吓攻击！{target_name} 陷入恐惧，额外伤害{sd_value}"
            if target_enemy:
                t_conds = target_enemy.get("conditions", [])
                if "frightened" not in t_conds:
                    t_conds.append("frightened")
                    target_enemy["conditions"] = t_conds
                    session.game_state = game_state
            elif target_char:
                t_conds = list(target_char.conditions or [])
                if "frightened" not in t_conds:
                    t_conds.append("frightened")
                    target_char.conditions = t_conds
        else:
            msg = f"⚔️ {actor_char.name} 使用威吓攻击，{target_name} 不为所动！额外伤害{sd_value}"

    elif req.maneuver_name == "pushing":
        maneuver_result["push_distance"] = 15
        maneuver_result["extra_damage"] = sd_value
        msg = f"⚔️ {actor_char.name} 使用推击！{target_name} 被推开15尺，额外伤害{sd_value}"

    elif req.maneuver_name == "goading":
        save_roll = random.randint(1, 20)
        target_wis_mod = 0
        if target_enemy:
            t_scores = target_enemy.get("ability_scores", {})
            target_wis_mod = (t_scores.get("wis", 10) - 10) // 2
        elif target_char:
            target_wis_mod = (target_char.derived or {}).get("ability_modifiers", {}).get("wis", 0)
        save_total = save_roll + target_wis_mod
        goaded = save_total < spell_dc
        maneuver_result["save_roll"] = save_roll
        maneuver_result["save_total"] = save_total
        maneuver_result["dc"] = spell_dc
        maneuver_result["goaded"] = goaded
        maneuver_result["extra_damage"] = sd_value
        if goaded:
            msg = f"⚔️ {actor_char.name} 使用激怒攻击！{target_name} 攻击其他目标时有劣势，额外伤害{sd_value}"
        else:
            msg = f"⚔️ {actor_char.name} 使用激怒攻击，{target_name} 不受影响！额外伤害{sd_value}"

    else:
        msg = f"⚔️ {actor_char.name} 使用了未知战技"

    # Log
    db.add(GameLog(
        session_id  = session_id,
        role        = "system",
        content     = msg,
        log_type    = "combat",
        dice_result = maneuver_result,
    ))

    flag_modified(actor_char, "class_resources")
    if target_is_enemy:
        flag_modified(session, "game_state")

    await db.commit()
    # Add dice_roll for frontend animation
    sd_faces = int(sd_die.replace("d", "")) if sd_die.startswith("d") else 8
    maneuver_result["dice_roll"] = {"faces": sd_faces, "result": sd_value, "label": f"战技·{req.maneuver_name}"}
    maneuver_result["narration"] = msg
    return maneuver_result
