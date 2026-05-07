"""
api.combat.ai_turn_spell — AI spell-casting branch for combat turns.
"""
from sqlalchemy.orm.attributes import flag_modified

from api.combat._shared import svc
from api.combat.ai_turn_utils import advance_ai_turn
from models import Character, GameLog
from services.combat_narrator import narrate_action
from services.dnd_rules import _normalize_class
from services.spell_service import spell_service


async def handle_ai_spell_action(
    session_id: str,
    db,
    session,
    combat,
    turn_order,
    next_index: int,
    actor_id: str,
    actor_name: str,
    is_enemy: bool,
    achar,
    actor_derived: dict,
    decided_target_id: str | None,
    decided_reason: str,
    decision: dict,
    state: dict,
    enemies: list,
    enemies_alive: list,
    all_characters: list,
):
    """Handle AI spell casting and return a response dict when resolved."""
    if not (decision.get("action_type") == "spell" and decision.get("action_name")):
        return None

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

        if not is_cantrip and achar:
            slots = dict(achar.spell_slots or {})
            slot_key = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th"][min(spell_level - 1, 8)]
            if slots.get(slot_key, 0) > 0:
                slots[slot_key] = slots[slot_key] - 1
                achar.spell_slots = slots
            else:
                spell_data = None

    if not spell_data:
        return None

    ai_spell_damage = 0
    ai_spell_heal = 0
    ai_spell_narration_parts = []
    target_new_hp = None
    target_name = ""

    if spell_type == "damage":
        total_dmg, dice_detail = spell_service.resolve_damage(spell_name, spell_level, spell_mod)
        if is_aoe:
            targets_list = []
            if is_enemy:
                for c in all_characters:
                    if c.get("hp_current", 0) > 0:
                        targets_list.append(c)
            else:
                for en in enemies_alive:
                    targets_list.append(en)

            save_ability = spell_data.get("save")
            half_on_save = spell_data.get("half_on_save", True)

            for tgt in targets_list[:4]:
                dmg_this = total_dmg
                if save_ability:
                    t_derived = tgt.get("derived", {})
                    t_save_mod = t_derived.get("saving_throws", {}).get(
                        save_ability,
                        t_derived.get("ability_modifiers", {}).get(save_ability, 0),
                    )
                    save_roll = _ai_roll("1d20")["rolls"][0]
                    if save_roll + t_save_mod >= spell_save_dc:
                        if half_on_save:
                            dmg_this = dmg_this // 2
                        else:
                            dmg_this = 0

                tid = str(tgt.get("id", ""))
                if not is_enemy:
                    for e2 in enemies:
                        if str(e2.get("id")) == tid:
                            e2["hp_current"] = svc.apply_damage(
                                e2.get("hp_current", 0),
                                dmg_this,
                                e2.get("derived", {}).get("hp_max", 10),
                            )
                else:
                    tc = await db.get(Character, tid)
                    if tc:
                        tc.hp_current = svc.apply_damage(
                            tc.hp_current,
                            dmg_this,
                            (tc.derived or {}).get("hp_max", tc.hp_current),
                        )
                ai_spell_damage += dmg_this

            state["enemies"] = enemies
            session.game_state = dict(state)
            flag_modified(session, "game_state")
        else:
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
                    target_enemy_sp["hp_current"] = svc.apply_damage(
                        target_enemy_sp.get("hp_current", 0),
                        total_dmg,
                        target_enemy_sp.get("derived", {}).get("hp_max", 10),
                    )
                    target_new_hp = target_enemy_sp["hp_current"]
                    target_name = target_enemy_sp.get("name", "敌人")
                    state["enemies"] = enemies
                    session.game_state = dict(state)
                    flag_modified(session, "game_state")
                else:
                    tc = await db.get(Character, spell_target)
                    if tc:
                        tc.hp_current = svc.apply_damage(
                            tc.hp_current,
                            total_dmg,
                            (tc.derived or {}).get("hp_max", tc.hp_current),
                        )
                        target_new_hp = tc.hp_current
                        target_name = tc.name
                ai_spell_damage = total_dmg

    elif spell_type == "heal":
        total_heal, dice_detail = spell_service.resolve_heal(spell_name, spell_level, spell_mod, bonus_healing_ai)
        if spell_target:
            tc = await db.get(Character, spell_target)
            if tc:
                hp_max_t = (tc.derived or {}).get("hp_max", tc.hp_current)
                tc.hp_current = min(hp_max_t, tc.hp_current + total_heal)
                target_new_hp = tc.hp_current
                target_name = tc.name
        ai_spell_heal = total_heal

    elif spell_type in ("control", "utility"):
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

    if spell_data.get("concentration") and achar:
        achar.concentration = spell_name

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

    ai_class_sp = _normalize_class(achar.char_class) if achar else actor_name
    vivid = await narrate_action(
        actor_name=actor_name,
        actor_class=ai_class_sp,
        target_name=target_name or "目标",
        action_type="spell",
        spell_name=spell_name,
        damage=ai_spell_damage,
        heal_amount=ai_spell_heal,
    )
    if vivid:
        spell_narr = vivid

    db.add(GameLog(
        session_id=session_id,
        role="enemy" if is_enemy else f"companion_{actor_name}",
        content=spell_narr,
        log_type="combat",
    ))

    await advance_ai_turn(combat, session, db, turn_order, next_index)
    flag_modified(session, "game_state")
    await db.commit()
    return {
        "actor_name": actor_name,
        "actor_id": actor_id,
        "narration": spell_narr,
        "attack_result": {},
        "damage": ai_spell_damage,
        "target_id": str(spell_target) if spell_target else None,
        "target_new_hp": target_new_hp,
        "next_turn_index": next_index,
        "round_number": combat.round_number,
        "combat_over": False,
        "outcome": None,
        "entity_positions": dict(combat.entity_positions or {}),
    }
