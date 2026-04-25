"""
api.combat.ai_turn — NPC 自动回合 + 结束战斗

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
from schemas.combat_responses import EndTurnResult

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/ai-turn", response_model=EndTurnResult)
async def ai_combat_turn(session_id: str, db: AsyncSession = Depends(get_db)):
    """处理当前 AI 实体的回合（队友或敌人）"""
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    turn_order = combat.turn_order or []
    if not turn_order:
        raise HTTPException(400, "先攻顺序为空")

    current    = turn_order[combat.current_turn_index]
    if current.get("is_player"):
        raise HTTPException(400, "当前是玩家回合，请使用 /action 接口")

    actor_id   = current.get("character_id", "")
    actor_name = current.get("name", "未知")
    state      = session.game_state or {}
    enemies    = list(state.get("enemies", []))
    is_enemy   = actor_id in [e["id"] for e in enemies]

    # ── 回合开始：重置施动者回合状态 ────────────────────────
    ai_atk_max, ai_move_max = await _calc_entity_turn_limits(db, session, actor_id)
    _reset_ts(combat, actor_id, attacks_max=ai_atk_max, movement_max=ai_move_max)

    # ── 获取施动者数据 ─────────────────────────────────────
    actor_derived = {}
    actor_hp      = 1
    ai_tick_logs  = []
    e     = None  # 敌人实体引用（供回合结束条件tick使用）
    achar = None  # 队友实体引用（供回合结束条件tick使用）
    if is_enemy:
        e = next((x for x in enemies if x["id"] == actor_id), None)
        if e:
            actor_derived = e.get("derived", {})
            actor_hp      = e.get("hp_current", 0)
    else:
        achar = await db.get(Character, actor_id)
        if achar:
            actor_derived = achar.derived or {}
            actor_hp      = achar.hp_current

    # 已死亡：跳过
    if actor_hp <= 0:
        next_index = (combat.current_turn_index + 1) % max(len(turn_order), 1)
        combat.current_turn_index = next_index
        if next_index == 0:
            combat.round_number += 1
        if turn_order:
            _ne = turn_order[next_index]["character_id"]
            _na, _nm = await _calc_entity_turn_limits(db, session, _ne)
            _reset_ts(combat, _ne, attacks_max=_na, movement_max=_nm)
        await db.commit()
        return {
            "actor_name": actor_name, "narration": f"{actor_name} 已倒下，跳过回合。",
            "attack_result": {}, "damage": 0, "target_id": None, "target_new_hp": None,
            "next_turn_index": next_index, "round_number": combat.round_number,
            "combat_over": False, "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        }

    # ── 计算下一回合索引（多处提前返回需要使用）────────────
    next_index = (combat.current_turn_index + 1) % max(len(turn_order), 1)

    # ── AI 决策：选择目标和行动 ─────────────────────────────
    from services.ai_combat_agent import get_ai_decision, calc_difficulty

    _roster = CharacterRoster(db, session)
    player = await _roster.player()
    companions_alive = []
    for c in await _roster.companions_alive():
        companions_alive.append({
            "id": c.id, "name": c.name, "char_class": c.char_class, "level": c.level,
            "hp_current": c.hp_current, "hp_max": (c.derived or {}).get("hp_max", c.hp_current),
            "ac": (c.derived or {}).get("ac", 10), "derived": c.derived or {},
            "conditions": c.conditions or [], "concentration": c.concentration,
            "known_spells": c.known_spells or [], "cantrips": c.cantrips or [],
            "spell_slots": c.spell_slots or {}, "is_player": c.is_player,
            "equipment": c.equipment or {},
        })

    enemies_alive = [e for e in enemies if e.get("hp_current", 0) > 0]

    # 构建角色快照列表（玩家+队友）
    all_characters = []
    if player and player.hp_current > 0:
        all_characters.append({
            "id": player.id, "name": player.name, "char_class": player.char_class, "level": player.level,
            "hp_current": player.hp_current, "hp_max": (player.derived or {}).get("hp_max", player.hp_current),
            "ac": (player.derived or {}).get("ac", 10), "derived": player.derived or {},
            "conditions": player.conditions or [], "concentration": player.concentration,
            "is_player": True,
        })
    all_characters.extend(companions_alive)

    # 构建行动者数据
    actor_full = dict(actor_derived)
    actor_full["id"] = actor_id
    actor_full["name"] = actor_name
    if is_enemy and e:
        actor_full.update({
            "hp_current": e.get("hp_current", 0), "hp_max": e.get("hp_max", e.get("derived", {}).get("hp_max", 10)),
            "ac": e.get("ac", e.get("derived", {}).get("ac", 10)),
            "actions": e.get("actions", []), "speed": e.get("speed", 30),
            "tactics": e.get("tactics", ""), "type": e.get("type", ""),
        })
    elif achar:
        actor_full.update({
            "hp_current": achar.hp_current, "hp_max": (achar.derived or {}).get("hp_max", achar.hp_current),
            "ac": (achar.derived or {}).get("ac", 10), "char_class": achar.char_class, "level": achar.level,
            "known_spells": achar.known_spells or [], "cantrips": achar.cantrips or [],
            "spell_slots": achar.spell_slots or [], "speed": 30,
            "equipment": achar.equipment or {}, "personality": achar.personality or "",
            "actions": [{"name": w.get("name","武器"), "type": "melee_attack",
                         "damage_dice": w.get("damage","1d8"), "attack_bonus": actor_derived.get("attack_bonus",2)}
                        for w in (achar.equipment or {}).get("weapons", [])],
            "prepared_spells": achar.prepared_spells or [],
        })

    # 获取模组难度
    _module = await db.get(Module, session.module_id) if session.module_id else None
    _parsed = (_module.parsed_content or {}) if _module else {}
    _difficulty = calc_difficulty(_parsed)

    # 获取战术/性格
    _tactics = actor_full.get("tactics", "") if is_enemy else ""
    _personality = ""
    if not is_enemy and achar:
        _personality = f"{achar.personality or ''} 战斗偏好: {actor_derived.get('combat_preference', '平衡')}"

    # 调用 AI 决策
    decision = await get_ai_decision(
        actor=actor_full,
        actor_is_enemy=is_enemy,
        all_characters=all_characters,
        all_enemies=enemies_alive,
        positions=dict(combat.entity_positions or {}),
        module_difficulty=_difficulty,
        module_tactics=_tactics,
        actor_personality=_personality,
    )

    # 从决策中获取目标
    decided_target_id = decision.get("target_id")
    decided_action = decision.get("action_type", "attack")
    decided_reason = decision.get("reason", "")

    # ── 处理非攻击决策 ──
    if decided_action == "dodge":
        ts_dodge = _get_ts(combat, actor_id)
        ts_dodge["dodging"] = True
        _save_ts(combat, actor_id, ts_dodge)
        combat.current_turn_index = next_index
        if next_index == 0:
            combat.round_number += 1
        if turn_order:
            _ne = turn_order[next_index]["character_id"]
            _na, _nm = await _calc_entity_turn_limits(db, session, _ne)
            _reset_ts(combat, _ne, attacks_max=_na, movement_max=_nm)
        await db.commit()
        return {
            "actor_name": actor_name, "actor_id": actor_id,
            "narration": f"🛡️ {actor_name} 采取闪避动作。{decided_reason}",
            "attack_result": {}, "damage": 0, "target_id": None, "target_new_hp": None,
            "next_turn_index": next_index, "round_number": combat.round_number,
            "combat_over": False, "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        }

    if decided_action == "dash":
        # 双倍移动，不攻击
        if decided_target_id:
            dash_tgt_pos = positions.get(str(decided_target_id))
            dash_ts = _get_ts(combat, actor_id)
            dash_budget = (dash_ts["movement_max"] - dash_ts["movement_used"]) + dash_ts["movement_max"]
            dash_result = _ai_move_toward(positions.get(str(actor_id)), dash_tgt_pos, dash_budget, positions, actor_id)
            if dash_result:
                positions[str(actor_id)] = {"x": dash_result["x"], "y": dash_result["y"]}
                combat.entity_positions = positions
        combat.current_turn_index = next_index
        if next_index == 0:
            combat.round_number += 1
        if turn_order:
            _ne = turn_order[next_index]["character_id"]
            _na, _nm = await _calc_entity_turn_limits(db, session, _ne)
            _reset_ts(combat, _ne, attacks_max=_na, movement_max=_nm)
        await db.commit()
        return {
            "actor_name": actor_name, "actor_id": actor_id,
            "narration": f"🏃 {actor_name} 全力冲刺！{decided_reason}",
            "attack_result": {}, "damage": 0, "target_id": None, "target_new_hp": None,
            "next_turn_index": next_index, "round_number": combat.round_number,
            "combat_over": False, "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        }

    if decided_action == "disengage":
        ts_dis = _get_ts(combat, actor_id)
        ts_dis["disengaged"] = True
        _save_ts(combat, actor_id, ts_dis)
        combat.current_turn_index = next_index
        if next_index == 0:
            combat.round_number += 1
        if turn_order:
            _ne = turn_order[next_index]["character_id"]
            _na, _nm = await _calc_entity_turn_limits(db, session, _ne)
            _reset_ts(combat, _ne, attacks_max=_na, movement_max=_nm)
        await db.commit()
        return {
            "actor_name": actor_name, "actor_id": actor_id,
            "narration": f"🚪 {actor_name} 脱离战斗！{decided_reason}",
            "attack_result": {}, "damage": 0, "target_id": None, "target_new_hp": None,
            "next_turn_index": next_index, "round_number": combat.round_number,
            "combat_over": False, "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        }

    # ── AI 施法分支 ──
    if decided_action == "spell" and decision.get("action_name"):
        # AI 施法
        spell_name = decision["action_name"]
        spell_level = decision.get("spell_level") or 1
        spell_target = decided_target_id

        spell_data = spell_service.get(spell_name)
        if spell_data:
            from services.dnd_rules import roll_dice as _ai_roll
            derived_ai = actor_derived
            spell_mod = 0
            spell_abil = derived_ai.get("spell_ability")
            if spell_abil:
                spell_mod = derived_ai.get("ability_modifiers", {}).get(spell_abil, 0)
            spell_save_dc = derived_ai.get("spell_save_dc", 13)
            bonus_healing_ai = derived_ai.get("bonus_healing", False)

            is_cantrip = spell_data.get("level", 0) == 0
            is_aoe = spell_data.get("aoe", False)
            spell_type = spell_data.get("type", "damage")

            # Consume spell slot (if not cantrip and has character)
            if not is_cantrip and achar:
                slots = dict(achar.spell_slots or {})
                slot_key = ["1st","2nd","3rd","4th","5th","6th","7th","8th","9th"][min(spell_level-1, 8)]
                if slots.get(slot_key, 0) > 0:
                    slots[slot_key] = slots[slot_key] - 1
                    achar.spell_slots = slots
                else:
                    # No slot available, fall through to attack
                    spell_data = None

        if spell_data:
            # Resolve spell effect
            ai_spell_damage = 0
            ai_spell_heal = 0
            ai_spell_narration_parts = []
            target_new_hp = None
            target_name = ""

            if spell_type == "damage":
                total_dmg, dice_detail = spell_service.resolve_damage(spell_name, spell_level, spell_mod)

                if is_aoe:
                    # Hit all targets (enemies for companions, characters for enemies)
                    targets_list = []
                    if is_enemy:
                        # Enemy casts AoE on players
                        for c in all_characters:
                            if c.get("hp_current", 0) > 0:
                                targets_list.append(c)
                    else:
                        # Companion casts AoE on enemies
                        for en in enemies_alive:
                            targets_list.append(en)

                    save_ability = spell_data.get("save")
                    half_on_save = spell_data.get("half_on_save", True)

                    for tgt in targets_list[:4]:  # Max 4 targets
                        dmg_this = total_dmg
                        if save_ability:
                            t_derived = tgt.get("derived", {})
                            t_save_mod = t_derived.get("saving_throws", {}).get(save_ability,
                                t_derived.get("ability_modifiers", {}).get(save_ability, 0))
                            save_roll = _ai_roll("1d20")["rolls"][0]
                            if save_roll + t_save_mod >= spell_save_dc:
                                if half_on_save:
                                    dmg_this = dmg_this // 2
                                else:
                                    dmg_this = 0

                        tid = str(tgt.get("id", ""))
                        # Apply damage
                        if not is_enemy:  # Companion hits enemy
                            for e2 in enemies:
                                if str(e2.get("id")) == tid:
                                    e2["hp_current"] = svc.apply_damage(e2.get("hp_current", 0), dmg_this, e2.get("derived", {}).get("hp_max", 10))
                        else:  # Enemy hits character
                            tc = await db.get(Character, tid)
                            if tc:
                                tc.hp_current = svc.apply_damage(tc.hp_current, dmg_this, (tc.derived or {}).get("hp_max", tc.hp_current))
                        ai_spell_damage += dmg_this

                    state["enemies"] = enemies
                    session.game_state = dict(state)
                    flag_modified(session, "game_state")
                else:
                    # Single target damage
                    if spell_target:
                        target_enemy_sp = next((e2 for e2 in enemies if str(e2.get("id")) == str(spell_target)), None)
                        if target_enemy_sp:
                            save_ability = spell_data.get("save")
                            if save_ability:
                                t_saves = target_enemy_sp.get("derived", {}).get("saving_throws", {})
                                t_mod = t_saves.get(save_ability, 0)
                                sr = _ai_roll("1d20")["rolls"][0]
                                if sr + t_mod >= spell_save_dc:
                                    if spell_data.get("half_on_save"):
                                        total_dmg = total_dmg // 2
                                    else:
                                        total_dmg = 0
                            target_enemy_sp["hp_current"] = svc.apply_damage(target_enemy_sp.get("hp_current", 0), total_dmg, target_enemy_sp.get("derived", {}).get("hp_max", 10))
                            target_new_hp = target_enemy_sp["hp_current"]
                            target_name = target_enemy_sp.get("name", "敌人")
                            state["enemies"] = enemies
                            session.game_state = dict(state)
                            flag_modified(session, "game_state")
                        else:
                            tc = await db.get(Character, spell_target)
                            if tc:
                                tc.hp_current = svc.apply_damage(tc.hp_current, total_dmg, (tc.derived or {}).get("hp_max", tc.hp_current))
                                target_new_hp = tc.hp_current
                                target_name = tc.name
                        ai_spell_damage = total_dmg

            elif spell_type == "heal":
                total_heal, dice_detail = spell_service.resolve_heal(spell_name, spell_level, spell_mod, bonus_healing_ai)
                # Heal target
                if spell_target:
                    tc = await db.get(Character, spell_target)
                    if tc:
                        hp_max_t = (tc.derived or {}).get("hp_max", tc.hp_current)
                        tc.hp_current = min(hp_max_t, tc.hp_current + total_heal)
                        target_new_hp = tc.hp_current
                        target_name = tc.name
                ai_spell_heal = total_heal

            elif spell_type in ("control", "utility"):
                # Apply condition to target
                condition_map = {
                    "Hold Person": "paralyzed",
                    "定身术": "paralyzed",
                    "Entangle": "restrained",
                    "纠缠术": "restrained",
                    "Web": "restrained",
                    "蛛网": "restrained",
                    "Sleep": "unconscious",
                    "睡眠术": "unconscious",
                    "Command": "commanded",
                    "命令术": "commanded",
                    "Faerie Fire": "faerie_fire",
                    "妖火": "faerie_fire",
                    "Blindness/Deafness": "blinded",
                    "目盲/耳聋": "blinded",
                    "Fear": "frightened",
                    "恐惧术": "frightened",
                    "Silence": "silenced",
                    "沉默术": "silenced",
                }
                condition = condition_map.get(spell_name, "hexed")
                save_ability = spell_data.get("save")

                if spell_target and save_ability:
                    # Target makes save
                    target_enemy_ctrl = next((e2 for e2 in enemies if str(e2.get("id")) == str(spell_target)), None)
                    if target_enemy_ctrl:
                        t_scores = target_enemy_ctrl.get("ability_scores", {})
                        t_mod = (t_scores.get(save_ability, 10) - 10) // 2
                        sr = _ai_roll("1d20")["rolls"][0]
                        if sr + t_mod < spell_save_dc:
                            conds = target_enemy_ctrl.get("conditions", [])
                            if condition not in conds:
                                conds.append(condition)
                                target_enemy_ctrl["conditions"] = conds
                            ai_spell_narration_parts.append(f"{target_enemy_ctrl.get('name')} 未通过豁免，陷入{condition}状态！")
                        else:
                            ai_spell_narration_parts.append(f"{target_enemy_ctrl.get('name')} 通过了豁免！")
                        target_name = target_enemy_ctrl.get("name", "敌人")
                        state["enemies"] = enemies
                        session.game_state = dict(state)
                        flag_modified(session, "game_state")
                    else:
                        tc = await db.get(Character, spell_target)
                        if tc:
                            t_derived = tc.derived or {}
                            t_mod = t_derived.get("saving_throws", {}).get(save_ability, 0)
                            sr = _ai_roll("1d20")["rolls"][0]
                            if sr + t_mod < spell_save_dc:
                                conds = list(tc.conditions or [])
                                if condition not in conds:
                                    conds.append(condition)
                                    tc.conditions = conds
                                ai_spell_narration_parts.append(f"{tc.name} 未通过豁免，陷入{condition}状态！")
                            else:
                                ai_spell_narration_parts.append(f"{tc.name} 通过了豁免！")
                            target_name = tc.name

            # Concentration
            if spell_data.get("concentration") and achar:
                achar.concentration = spell_name

            # Build narration
            level_str = f"{spell_level}环" if not is_cantrip else "戏法"
            spell_narr = f"✨ {actor_name} 施放了【{spell_name}】（{level_str}）！"
            if ai_spell_damage > 0:
                spell_narr += f"造成 {ai_spell_damage} 点伤害！"
            if ai_spell_heal > 0:
                spell_narr += f"恢复 {ai_spell_heal} HP！"
            if ai_spell_narration_parts:
                spell_narr += " ".join(ai_spell_narration_parts)
            if decided_reason:
                spell_narr += f"（{decided_reason}）"

            # LLM narration
            ai_class_sp = _normalize_class(achar.char_class) if achar else actor_name
            vivid = await narrate_action(
                actor_name=actor_name, actor_class=ai_class_sp,
                target_name=target_name or "目标", action_type="spell",
                spell_name=spell_name, damage=ai_spell_damage, heal_amount=ai_spell_heal,
            )
            if vivid:
                spell_narr = vivid

            # Log
            db.add(GameLog(
                session_id=session_id, role="enemy" if is_enemy else f"companion_{actor_name}",
                content=spell_narr, log_type="combat",
            ))

            # Advance turn
            combat.current_turn_index = next_index
            if next_index == 0:
                combat.round_number += 1
            if turn_order:
                ne_id = turn_order[next_index]["character_id"]
                n_atk, n_mv = await _calc_entity_turn_limits(db, session, ne_id)
                _reset_ts(combat, ne_id, attacks_max=n_atk, movement_max=n_mv)

            flag_modified(session, "game_state")
            await db.commit()
            return {
                "actor_name": actor_name, "actor_id": actor_id,
                "narration": spell_narr,
                "attack_result": {}, "damage": ai_spell_damage,
                "target_id": str(spell_target) if spell_target else None,
                "target_new_hp": target_new_hp,
                "next_turn_index": next_index, "round_number": combat.round_number,
                "combat_over": False, "outcome": None,
                "entity_positions": dict(combat.entity_positions or {}),
            }

    # ── 攻击/法术：查找目标数据 ──
    # Fallback 目标选择（当 AI 决策失败或 target_id 无效时）
    target_data = None
    if decided_target_id:
        # 在敌人和角色中查找目标
        for t in enemies_alive:
            if str(t.get("id")) == str(decided_target_id):
                target_data = t
                break
        if not target_data:
            for t in all_characters:
                if str(t.get("id")) == str(decided_target_id):
                    target_data = t
                    break

    if not target_data:
        # AI 决策失败或 target_id 无效，回退到旧逻辑
        target_data = svc.choose_ai_target(
            actor_is_enemy=is_enemy,
            player={"id": player.id, "hp_current": player.hp_current, "derived": player.derived or {}} if player else None,
            allies=companions_alive,
            enemies_alive=enemies_alive,
        )

    # ── 解析攻击（含 Extra Attack / Sneak Attack / Rage for AI）──
    target_id       = None
    target_name     = ""
    target_new_hp   = None
    target_is_enemy = False
    total_damage    = 0
    all_narrations  = []
    positions       = dict(combat.entity_positions or {})

    # Determine AI actor's class/level for class features
    ai_class = ""
    ai_level = 1
    ai_class_res = {}
    if achar:
        ai_class = _normalize_class(achar.char_class)
        ai_level = achar.level
        ai_class_res = dict(achar.class_resources or {})

    # AI Barbarian: auto-rage if not already raging
    if achar and ai_class == "Barbarian" and not ai_class_res.get("raging", False):
        rage_rem = ai_class_res.get("rage_remaining", svc.get_rage_uses(ai_level))
        if rage_rem > 0:
            ai_class_res["raging"] = True
            ai_class_res["rage_remaining"] = rage_rem - 1
            achar.class_resources = ai_class_res
            all_narrations.append(f"🔥 {actor_name} 进入狂暴！")

    # Calculate number of attacks
    num_attacks = 1
    if achar:
        num_attacks = svc.get_attack_count(actor_derived, ai_level, ai_class)

    result_obj = None
    first_attack_roll = None

    if target_data:
        target_id      = target_data["id"]
        target_derived = target_data.get("derived", {})

        # Cover bonus for AI attacks (P0-8)
        ai_grid = dict(combat.grid_data or {})
        ai_atk_pos = positions.get(str(actor_id))
        ai_tgt_pos = positions.get(str(target_id))
        ai_cover = 0
        if ai_atk_pos and ai_tgt_pos:
            ai_cover = svc.get_cover_bonus(ai_grid, ai_atk_pos, ai_tgt_pos)
        ai_target_derived = dict(target_derived)
        if ai_cover > 0:
            ai_target_derived["ac"] = target_derived.get("ac", 10) + ai_cover

        # Shield spell AC bonus (P0-6): if target has shield_spell condition, +5 AC
        if not is_enemy:
            pass  # enemy attacks character - check character conditions
        target_char_for_shield = await db.get(Character, target_id) if target_id else None
        if target_char_for_shield and "shield_spell" in (target_char_for_shield.conditions or []):
            ai_target_derived["ac"] = ai_target_derived.get("ac", 10) + 5

        # ── AI 距离检查 + 自动移动 ─────────────────────────
        ai_is_ranged = False
        # 判断 AI 是否使用远程武器（从装备中检测）
        if achar and achar.equipment:
            ai_weapons = (achar.equipment or {}).get("weapons", [])
            for w in ai_weapons:
                wp = (w.get("properties") or "")
                if isinstance(wp, list):
                    wp = ",".join(wp)
                if "远程" in wp or "ranged" in wp.lower() or w.get("type", "") in ("简易远程武器", "军用远程武器"):
                    ai_is_ranged = True
                    break
        # 怪物默认近战（无 Character 对象时）
        if not achar:
            # 检查怪物数据中的 actions 判断是否远程
            for e in enemies:
                if str(e.get("id")) == str(actor_id):
                    for act in e.get("actions", []):
                        if "远程" in act.get("type", "") or "ranged" in act.get("type", "").lower():
                            ai_is_ranged = True
                    break

        in_range, ai_dist, _ = _check_attack_range(ai_atk_pos, ai_tgt_pos, ai_is_ranged)
        if not in_range and ai_atk_pos and ai_tgt_pos:
            # 尝试自动移动靠近目标
            actor_ts_pre = _get_ts(combat, actor_id)
            move_remaining = actor_ts_pre["movement_max"] - actor_ts_pre["movement_used"]
            move_result = _ai_move_toward(ai_atk_pos, ai_tgt_pos, move_remaining, positions, actor_id)
            if move_result:
                new_pos = {"x": move_result["x"], "y": move_result["y"]}
                positions[str(actor_id)] = new_pos
                combat.entity_positions = positions
                actor_ts_pre["movement_used"] += move_result["steps"]
                _save_ts(combat, actor_id, actor_ts_pre)
                all_narrations.append(f"🏃 {actor_name} 向目标移动了 {move_result['steps']*5}ft")
                # 重新检查距离
                in_range, ai_dist, _ = _check_attack_range(new_pos, ai_tgt_pos, ai_is_ranged)
                # 更新掩体计算
                if in_range:
                    ai_cover = svc.get_cover_bonus(ai_grid, new_pos, ai_tgt_pos)
                    if ai_cover > 0:
                        ai_target_derived["ac"] = target_derived.get("ac", 10) + ai_cover

        if not in_range:
            # 仍然不在攻击范围内，跳过攻击
            all_narrations.append(f"{actor_name} 无法到达目标（距离 {ai_dist*5}ft）")
            narrate_text = await narrate_batch(
                [{"actor": actor_name, "action": "移动", "target": "", "result": "移动但无法接近目标"}]
            )
            if narrate_text and narrate_text[0]:
                all_narrations.append(narrate_text[0])

            # 推进回合
            combat.current_turn_index = next_index
            if next_index == 0:
                combat.round_number += 1
            if turn_order:
                _ne = turn_order[next_index]["character_id"]
                _na, _nm = await _calc_entity_turn_limits(db, session, _ne)
                _reset_ts(combat, _ne, attacks_max=_na, movement_max=_nm)
            flag_modified(session, "game_state")
            flag_modified(combat, "entity_positions")
            flag_modified(combat, "turn_states")
            await db.commit()
            return {
                "actor_name": actor_name,
                "actor_id": actor_id,
                "narration": "\n".join(all_narrations),
                "attack_result": {}, "damage": 0,
                "target_id": str(target_id) if target_id else None,
                "target_new_hp": None,
                "next_turn_index": next_index, "round_number": combat.round_number,
                "combat_over": False, "outcome": None,
                "entity_positions": dict(combat.entity_positions or {}),
            }

        # 「被协助」→ 攻击优势
        actor_ts   = _get_ts(combat, actor_id)
        extra_adv  = actor_ts.get("being_helped", False)
        if extra_adv:
            actor_ts["being_helped"] = False
            _save_ts(combat, actor_id, actor_ts)

        for atk_idx in range(num_attacks):
            result_obj = svc.resolve_melee_attack(
                attacker_derived = actor_derived,
                target_derived   = ai_target_derived,
                advantage        = extra_adv if atk_idx == 0 else False,
            )
            if first_attack_roll is None:
                first_attack_roll = result_obj

            atk_damage = result_obj.damage

            # AI Rage bonus
            if result_obj.attack_roll["hit"] and achar and ai_class_res.get("raging", False):
                rage_bonus = svc.get_rage_bonus(ai_level)
                atk_damage += rage_bonus
                # Zealot Divine Fury (first hit per turn while raging)
                ai_sub_effects = actor_derived.get("subclass_effects", {})
                if ai_sub_effects.get("divine_fury") and atk_idx == 0:
                    fury_roll = roll_dice(f"1d6+{ai_level // 2}")
                    atk_damage += fury_roll["total"]

            # AI Sneak Attack (first hit only)
            if result_obj.attack_roll["hit"] and achar and ai_class == "Rogue" and atk_idx == 0:
                # Check ally adjacency for sneak attack
                ally_list_for_sa = [{"id": a["id"], "hp_current": a.get("hp_current", 0)} for a in enemies_alive] if not is_enemy else []
                if is_enemy:
                    pass  # enemies don't get sneak attack
                else:
                    p_data = {"id": player.id, "hp_current": player.hp_current} if player else None
                    ally_list_sa = [p_data] if p_data else []
                    ally_list_sa += [{"id": ca["id"], "hp_current": ca.get("hp_current", 0)} for ca in companions_alive]
                    ally_adj = _has_ally_adjacent_to(target_id, actor_id, ally_list_sa, positions)
                    has_adv = extra_adv if atk_idx == 0 else False
                    # Swashbuckler AI companion
                    ai_sub_sa = actor_derived.get("subclass_effects", {})
                    ai_swash = ai_sub_sa.get("swashbuckler", False)
                    ai_no_other = False
                    if ai_swash:
                        other_enemies_sa = [e for e in enemies if e["id"] != target_id and e.get("hp_current", 0) > 0]
                        ai_no_other = not _has_ally_adjacent_to(actor_id, target_id, other_enemies_sa, positions)
                    if svc.check_sneak_attack(ai_class, has_adv, ally_adj, swashbuckler=ai_swash, no_other_enemy_adjacent=ai_no_other):
                        sa_dice = svc.calc_sneak_attack_dice(ai_level)
                        sa_roll = roll_dice(f"{sa_dice}d6")
                        atk_damage += sa_roll["total"]

            if result_obj.attack_roll["hit"]:
                if not is_enemy:  # 队友攻击敌人
                    for e2 in enemies:
                        if e2["id"] == target_id:
                            e2["hp_current"] = svc.apply_damage(e2.get("hp_current", 0), atk_damage, e2.get("derived", {}).get("hp_max", 10))
                            target_new_hp   = e2["hp_current"]
                    state["enemies"]      = enemies
                    session.game_state = dict(state); flag_modified(session, "game_state")
                    target_name           = target_data.get("name", "敌人")
                else:  # 敌人攻击玩家/队友
                    tchar = await db.get(Character, target_id)
                    if tchar:
                        # Apply damage resistance for raging barbarian targets
                        final_dmg = atk_damage
                        if tchar and _normalize_class(tchar.char_class) == "Barbarian":
                            t_res = dict(tchar.class_resources or {})
                            if t_res.get("raging", False):
                                dmg_type = actor_derived.get("damage_type", "钝击")
                                t_sub_effects = (tchar.derived or {}).get("subclass_effects", {})
                                if t_sub_effects.get("bear_totem"):
                                    # Bear Totem: resist ALL damage except psychic
                                    if dmg_type not in ("心灵", "psychic"):
                                        final_dmg = final_dmg // 2
                                elif dmg_type in ("钝击", "穿刺", "挥砍", "bludgeoning", "piercing", "slashing"):
                                    final_dmg = final_dmg // 2
                        tchar.hp_current  = svc.apply_damage(tchar.hp_current, final_dmg, (tchar.derived or {}).get("hp_max", tchar.hp_current))
                        target_new_hp     = tchar.hp_current
                        target_name       = tchar.name

            total_damage += atk_damage
            all_narrations.append(svc._build_narration(actor_name, target_name or target_data.get("name", "?"), result_obj.attack_roll, atk_damage))

            # Dark One's Blessing: AI Warlock gains temp HP on kill
            if target_new_hp is not None and target_new_hp <= 0 and not is_enemy and achar:
                ai_sub_eff = actor_derived.get("subclass_effects", {})
                if ai_sub_eff.get("dark_ones_blessing"):
                    cha_val = actor_derived.get("ability_modifiers", {}).get("cha", 0)
                    _temp_hp = cha_val + ai_level
                    all_narrations.append(f"{actor_name} 获得 {_temp_hp} 临时HP（黑暗祝福）")

            # If target is dead, stop attacking
            if target_new_hp is not None and target_new_hp <= 0:
                break

    if not all_narrations:
        all_narrations.append(f"{actor_name} 没有找到目标，跳过回合。")

    mechanical_narration = " | ".join(all_narrations) if len(all_narrations) > 1 else all_narrations[0]
    # Use first_attack_roll for the response (backward compat)
    result_obj = first_attack_roll

    # ── LLM vivid narration for AI turn ──
    ai_actor_class = ai_class if achar else (e.get("name", "怪物") if e else "")
    batch_actions = [{
        "actor_name": actor_name,
        "actor_class": ai_actor_class,
        "target_name": target_name or "目标",
        "mechanical_desc": f"{mechanical_narration}" + (f"（战术：{decided_reason}）" if decided_reason and not decision.get("_fallback") else ""),
    }]
    vivid_results = await narrate_batch(batch_actions)
    narration = vivid_results[0] if vivid_results[0] else mechanical_narration

    # ── 专注中断检定（敌方命中友方角色时）────────────────
    conc_log = None
    if result_obj and result_obj.attack_roll.get("hit") and is_enemy and target_id:
        tchar_conc = await db.get(Character, target_id)
        if tchar_conc:
            conc_log = await _do_concentration_check(tchar_conc, total_damage, session_id)

    # ── 回合结束：条件倒计时（5e标准：在实体回合结束时tick）──
    if is_enemy and e:
        removed = _tick_conditions_enemy(e)
        for c in removed:
            ai_tick_logs.append(GameLog(
                session_id=session_id, role="system",
                content=f"🟢 {actor_name} 的【{c}】状态到期解除", log_type="system",
            ))
        state["enemies"] = enemies
        session.game_state = dict(state); flag_modified(session, "game_state")
    elif not is_enemy and achar:
        removed = _tick_conditions_char(achar)
        for c in removed:
            ai_tick_logs.append(GameLog(
                session_id=session_id, role="system",
                content=f"🟢 {actor_name} 的【{c}】状态到期解除", log_type="system",
            ))

    # ── 写日志 & 推进回合 ────────────────────────────────
    role_key = "enemy" if is_enemy else f"companion_{actor_name}"
    db.add(GameLog(
        session_id  = session_id,
        role        = role_key,
        content     = narration,
        log_type    = "combat",
        dice_result = {"attack": result_obj.attack_roll, "damage": total_damage} if result_obj else None,
    ))

    for tl in ai_tick_logs:
        db.add(tl)
    if conc_log:
        db.add(conc_log)

    next_index = (combat.current_turn_index + 1) % max(len(turn_order), 1)
    combat.current_turn_index = next_index
    if next_index == 0:
        combat.round_number += 1

    # 重置下一实体的回合状态（根据角色实际数据）
    if turn_order:
        next_entity_id = turn_order[next_index]["character_id"]
        next_atk_max, next_move_max = await _calc_entity_turn_limits(db, session, next_entity_id)
        _reset_ts(combat, next_entity_id, attacks_max=next_atk_max, movement_max=next_move_max)

    player_check         = await db.get(Character, session.player_character_id)
    combat_over, outcome = svc.check_combat_over(enemies, player_check.hp_current if player_check else 0)
    if combat_over:
        session.combat_active = False
        # 清理战斗状态记录，防止下次战斗残留旧数据
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs: await db.delete(_old_cs)
        except Exception: pass

    # ── Reaction info (P0-6): check if player was targeted and can react ──
    player_targeted = (is_enemy and target_id == session.player_character_id)
    player_can_react = False
    reaction_prompt = None
    if player_targeted and player_check:
        p_ts = _get_ts(combat, session.player_character_id)
        if not p_ts.get("reaction_used"):
            player_can_react = True
            p_derived_r = player_check.derived or {}
            p_cls = _normalize_class(player_check.char_class)
            p_level = player_check.level or 1
            # Build reaction prompt for frontend — enhanced with class/spell details
            known_spells = set(player_check.known_spells or []) | set(player_check.prepared_spells or [])
            p_slots = dict(player_check.spell_slots or {})
            available_reactions = []

            # Shield spell (Wizard/Sorcerer/Hexblade — costs 1st-level slot, +5 AC until next turn)
            if ("Shield" in known_spells or "shield" in known_spells) and p_slots.get("1st", 0) > 0:
                available_reactions.append({
                    "id": "shield",
                    "name": "Shield",
                    "type": "spell",
                    "cost": "1st-level spell slot",
                    "slot_level": "1st",
                    "slots_remaining": p_slots.get("1st", 0),
                    "effect": "+5 AC（持续到你的下个回合开始）",
                    "resulting_ac": p_derived_r.get("ac", 10) + 5,
                })

            # Uncanny Dodge (Rogue 5+, halve incoming damage)
            if p_cls == "Rogue" and p_level >= 5:
                available_reactions.append({
                    "id": "uncanny_dodge",
                    "name": "Uncanny Dodge",
                    "type": "class_feature",
                    "cost": "reaction",
                    "effect": f"将此次攻击的伤害减半（{total_damage} → {total_damage // 2}）",
                    "reduced_damage": total_damage // 2,
                })

            # Hellish Rebuke (Tiefling/Warlock — costs 1st-level slot, 2d10 fire)
            if ("Hellish Rebuke" in known_spells or "hellish_rebuke" in known_spells) and p_slots.get("1st", 0) > 0:
                available_reactions.append({
                    "id": "hellish_rebuke",
                    "name": "Hellish Rebuke",
                    "type": "spell",
                    "cost": "1st-level spell slot",
                    "slot_level": "1st",
                    "slots_remaining": p_slots.get("1st", 0),
                    "effect": "对攻击者造成 2d10 火焰伤害（DEX豁免成功减半）",
                    "damage_dice": "2d10",
                })

            # Absorb Elements (Ranger/Wizard/Sorcerer/Druid — 1st-level, elemental resistance)
            if ("Absorb Elements" in known_spells or "absorb_elements" in known_spells) and p_slots.get("1st", 0) > 0:
                available_reactions.append({
                    "id": "absorb_elements",
                    "name": "Absorb Elements",
                    "type": "spell",
                    "cost": "1st-level spell slot",
                    "slot_level": "1st",
                    "slots_remaining": p_slots.get("1st", 0),
                    "effect": "获得触发元素的伤害抗性（持续到下回合开始），下次近战+1d6该元素伤害",
                })

            # Counterspell (if the enemy action was a spell — basic support)
            if ("Counterspell" in known_spells or "counterspell" in known_spells) and p_slots.get("3rd", 0) > 0:
                available_reactions.append({
                    "id": "counterspell",
                    "name": "Counterspell",
                    "type": "spell",
                    "cost": "3rd-level spell slot",
                    "slot_level": "3rd",
                    "slots_remaining": p_slots.get("3rd", 0),
                    "effect": "反制敌人施放的法术（3环或以下自动成功，更高需检定）",
                })

            if available_reactions:
                reaction_prompt = {
                    "can_react": True,
                    "reaction_used": p_ts.get("reaction_used", False),
                    "attack_roll": result_obj.attack_roll.get("attack_total", 0) if result_obj else 0,
                    "player_ac": p_derived_r.get("ac", 10),
                    "incoming_damage": total_damage,
                    "attacker_name": actor_name,
                    "attacker_id": actor_id,
                    "spell_slots": p_slots,
                    "available_reactions": available_reactions,
                }

    await db.commit()
    return {
        "actor_name":           actor_name,
        "actor_id":             actor_id,
        "narration":            narration,
        "attack_result":        result_obj.attack_roll if result_obj else {},
        "damage":               total_damage,
        "target_id":            target_id,
        "target_new_hp":        target_new_hp,
        "concentration_check":  conc_log.dice_result if conc_log else None,
        "player_targeted":      player_targeted,
        "player_can_react":     player_can_react,
        "reaction_prompt":      reaction_prompt,
        "next_turn_index":      next_index,
        "round_number":         combat.round_number,
        "combat_over":          combat_over,
        "outcome":              outcome,
        "entity_positions":     dict(combat.entity_positions or {}),
    }


# ── 结束战斗 ──────────────────────────────────────────────

@router.post("/combat/{session_id}/end", response_model=EndTurnResult)
async def end_combat(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await get_session_or_404(session_id, db)
    session.combat_active = False
    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if combat:
        await db.delete(combat)
    db.add(GameLog(session_id=session_id, role="system",
                   content="⚔️ 战斗结束，队伍继续前进。", log_type="system"))
    await db.commit()
    return {"ok": True}


# ── 移动 ─────────────────────────────────────────────────

