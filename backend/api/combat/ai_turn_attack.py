"""
api.combat.ai_turn_attack — AI combat attack branch.
"""
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from models import Character, GameLog, CombatState
from api.combat._shared import (
    _get_ts, _save_ts, _ai_move_toward,
    _check_attack_range, _has_ally_adjacent_to,
    _do_concentration_check, _tick_conditions_char, _tick_conditions_enemy,
    svc,
)
from api.combat.ai_turn_utils import advance_ai_turn, build_reaction_prompt
from services.combat_narrator import narrate_batch
from services.dnd_rules import roll_dice, _normalize_class


async def handle_ai_attack_action(
    session_id: str,
    db,
    session,
    combat,
    turn_order,
    next_index: int,
    actor_id: str,
    actor_name: str,
    is_enemy: bool,
    e,
    achar,
    actor_derived: dict,
    player,
    companions_alive: list,
    enemies: list,
    enemies_alive: list,
    all_characters: list,
    positions: dict,
    decided_target_id: str | None,
    decided_reason: str,
    decision: dict,
):
    """Resolve the remaining AI turn as an attack/default action."""
    target_data = None
    if decided_target_id:
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
        target_data = svc.choose_ai_target(
            actor_is_enemy=is_enemy,
            player={"id": player.id, "hp_current": player.hp_current, "derived": player.derived or {}} if player else None,
            allies=companions_alive,
            enemies_alive=enemies_alive,
        )

    target_id = None
    target_name = ""
    target_new_hp = None
    total_damage = 0
    all_narrations = []

    ai_class = ""
    ai_level = 1
    ai_class_res = {}
    if achar:
        ai_class = _normalize_class(achar.char_class)
        ai_level = achar.level
        ai_class_res = dict(achar.class_resources or {})

    if achar and ai_class == "Barbarian" and not ai_class_res.get("raging", False):
        rage_rem = ai_class_res.get("rage_remaining", svc.get_rage_uses(ai_level))
        if rage_rem > 0:
            ai_class_res["raging"] = True
            ai_class_res["rage_remaining"] = rage_rem - 1
            achar.class_resources = ai_class_res
            all_narrations.append(f"🔥 {actor_name} 进入狂暴！")

    num_attacks = 1
    if achar:
        num_attacks = svc.get_attack_count(actor_derived, ai_level, ai_class)

    result_obj = None
    first_attack_roll = None

    if target_data:
        target_id = target_data["id"]
        target_derived = target_data.get("derived", {})

        ai_grid = dict(combat.grid_data or {})
        ai_atk_pos = positions.get(str(actor_id))
        ai_tgt_pos = positions.get(str(target_id))
        ai_cover = 0
        if ai_atk_pos and ai_tgt_pos:
            ai_cover = svc.get_cover_bonus(ai_grid, ai_atk_pos, ai_tgt_pos)
        ai_target_derived = dict(target_derived)
        if ai_cover > 0:
            ai_target_derived["ac"] = target_derived.get("ac", 10) + ai_cover

        target_char_for_shield = await db.get(Character, target_id) if target_id else None
        if target_char_for_shield and "shield_spell" in (target_char_for_shield.conditions or []):
            ai_target_derived["ac"] = ai_target_derived.get("ac", 10) + 5

        ai_is_ranged = False
        if achar and achar.equipment:
            ai_weapons = (achar.equipment or {}).get("weapons", [])
            for w in ai_weapons:
                wp = (w.get("properties") or "")
                if isinstance(wp, list):
                    wp = ",".join(wp)
                if "远程" in wp or "ranged" in wp.lower() or w.get("type", "") in ("简易远程武器", "军用远程武器"):
                    ai_is_ranged = True
                    break
        if not achar:
            for enemy in enemies:
                if str(enemy.get("id")) == str(actor_id):
                    for act in enemy.get("actions", []):
                        if "远程" in act.get("type", "") or "ranged" in act.get("type", "").lower():
                            ai_is_ranged = True
                    break

        in_range, ai_dist, _ = _check_attack_range(ai_atk_pos, ai_tgt_pos, ai_is_ranged)
        if not in_range and ai_atk_pos and ai_tgt_pos:
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
                in_range, ai_dist, _ = _check_attack_range(new_pos, ai_tgt_pos, ai_is_ranged)
                if in_range:
                    ai_cover = svc.get_cover_bonus(ai_grid, new_pos, ai_tgt_pos)
                    if ai_cover > 0:
                        ai_target_derived["ac"] = target_derived.get("ac", 10) + ai_cover

        if not in_range:
            all_narrations.append(f"{actor_name} 无法到达目标（距离 {ai_dist*5}ft）")
            narrate_text = await narrate_batch(
                [{"actor": actor_name, "action": "移动", "target": "", "result": "移动但无法接近目标"}]
            )
            if narrate_text and narrate_text[0]:
                all_narrations.append(narrate_text[0])

            await advance_ai_turn(combat, session, db, turn_order, next_index)
            flag_modified(session, "game_state")
            flag_modified(combat, "entity_positions")
            flag_modified(combat, "turn_states")
            await db.commit()
            return {
                "actor_name": actor_name,
                "actor_id": actor_id,
                "narration": "\n".join(all_narrations),
                "attack_result": {},
                "damage": 0,
                "target_id": str(target_id) if target_id else None,
                "target_new_hp": None,
                "next_turn_index": next_index,
                "round_number": combat.round_number,
                "combat_over": False,
                "outcome": None,
                "entity_positions": dict(combat.entity_positions or {}),
            }

        actor_ts = _get_ts(combat, actor_id)
        extra_adv = actor_ts.get("being_helped", False)
        if extra_adv:
            actor_ts["being_helped"] = False
            _save_ts(combat, actor_id, actor_ts)

        for atk_idx in range(num_attacks):
            result_obj = svc.resolve_melee_attack(
                attacker_derived=actor_derived,
                target_derived=ai_target_derived,
                advantage=extra_adv if atk_idx == 0 else False,
            )
            if first_attack_roll is None:
                first_attack_roll = result_obj

            atk_damage = result_obj.damage

            if result_obj.attack_roll["hit"] and achar and ai_class_res.get("raging", False):
                rage_bonus = svc.get_rage_bonus(ai_level)
                atk_damage += rage_bonus
                ai_sub_effects = actor_derived.get("subclass_effects", {})
                if ai_sub_effects.get("divine_fury") and atk_idx == 0:
                    fury_roll = roll_dice(f"1d6+{ai_level // 2}")
                    atk_damage += fury_roll["total"]

            if result_obj.attack_roll["hit"] and achar and ai_class == "Rogue" and atk_idx == 0:
                if is_enemy:
                    pass
                else:
                    p_data = {"id": player.id, "hp_current": player.hp_current} if player else None
                    ally_list_sa = [p_data] if p_data else []
                    ally_list_sa += [{"id": ca["id"], "hp_current": ca.get("hp_current", 0)} for ca in companions_alive]
                    ally_adj = _has_ally_adjacent_to(target_id, actor_id, ally_list_sa, positions)
                    has_adv = extra_adv if atk_idx == 0 else False
                    ai_sub_sa = actor_derived.get("subclass_effects", {})
                    ai_swash = ai_sub_sa.get("swashbuckler", False)
                    ai_no_other = False
                    if ai_swash:
                        other_enemies_sa = [enemy for enemy in enemies if enemy["id"] != target_id and enemy.get("hp_current", 0) > 0]
                        ai_no_other = not _has_ally_adjacent_to(actor_id, target_id, other_enemies_sa, positions)
                    if svc.check_sneak_attack(ai_class, has_adv, ally_adj, swashbuckler=ai_swash, no_other_enemy_adjacent=ai_no_other):
                        sa_dice = svc.calc_sneak_attack_dice(ai_level)
                        sa_roll = roll_dice(f"{sa_dice}d6")
                        atk_damage += sa_roll["total"]

            if result_obj.attack_roll["hit"]:
                if not is_enemy:
                    for enemy in enemies:
                        if enemy["id"] == target_id:
                            enemy["hp_current"] = svc.apply_damage(enemy.get("hp_current", 0), atk_damage, enemy.get("derived", {}).get("hp_max", 10))
                            target_new_hp = enemy["hp_current"]
                    state["enemies"] = enemies
                    session.game_state = dict(state)
                    flag_modified(session, "game_state")
                    target_name = target_data.get("name", "敌人")
                else:
                    tchar = await db.get(Character, target_id)
                    if tchar:
                        final_dmg = atk_damage
                        if tchar and _normalize_class(tchar.char_class) == "Barbarian":
                            t_res = dict(tchar.class_resources or {})
                            if t_res.get("raging", False):
                                dmg_type = actor_derived.get("damage_type", "钝击")
                                t_sub_effects = (tchar.derived or {}).get("subclass_effects", {})
                                if t_sub_effects.get("bear_totem"):
                                    if dmg_type not in ("心灵", "psychic"):
                                        final_dmg = final_dmg // 2
                                elif dmg_type in ("钝击", "穿刺", "挥砍", "bludgeoning", "piercing", "slashing"):
                                    final_dmg = final_dmg // 2
                        tchar.hp_current = svc.apply_damage(tchar.hp_current, final_dmg, (tchar.derived or {}).get("hp_max", tchar.hp_current))
                        target_new_hp = tchar.hp_current
                        target_name = tchar.name

            total_damage += atk_damage
            all_narrations.append(svc._build_narration(actor_name, target_name or target_data.get("name", "?"), result_obj.attack_roll, atk_damage))

            if target_new_hp is not None and target_new_hp <= 0 and not is_enemy and achar:
                ai_sub_eff = actor_derived.get("subclass_effects", {})
                if ai_sub_eff.get("dark_ones_blessing"):
                    cha_val = actor_derived.get("ability_modifiers", {}).get("cha", 0)
                    _temp_hp = cha_val + ai_level
                    all_narrations.append(f"{actor_name} 获得 {_temp_hp} 临时HP（黑暗祝福）")

            if target_new_hp is not None and target_new_hp <= 0:
                break

    if not all_narrations:
        all_narrations.append(f"{actor_name} 没有找到目标，跳过回合。")

    mechanical_narration = " | ".join(all_narrations) if len(all_narrations) > 1 else all_narrations[0]
    result_obj = first_attack_roll

    ai_actor_class = ai_class if achar else (e.get("name", "怪物") if e else "")
    batch_actions = [{
        "actor_name": actor_name,
        "actor_class": ai_actor_class,
        "target_name": target_name or "目标",
        "mechanical_desc": f"{mechanical_narration}" + (f"（战术：{decided_reason}）" if decided_reason and not decision.get("_fallback") else ""),
    }]
    vivid_results = await narrate_batch(batch_actions)
    narration = vivid_results[0] if vivid_results[0] else mechanical_narration

    conc_log = None
    if result_obj and result_obj.attack_roll.get("hit") and is_enemy and target_id:
        tchar_conc = await db.get(Character, target_id)
        if tchar_conc:
            conc_log = await _do_concentration_check(tchar_conc, total_damage, session_id)

    ai_tick_logs = []
    if is_enemy and e:
        removed = _tick_conditions_enemy(e)
        for c in removed:
            ai_tick_logs.append(GameLog(
                session_id=session_id,
                role="system",
                content=f"🟢 {actor_name} 的【{c}】状态到期解除",
                log_type="system",
            ))
        state["enemies"] = enemies
        session.game_state = dict(state)
        flag_modified(session, "game_state")
    elif not is_enemy and achar:
        removed = _tick_conditions_char(achar)
        for c in removed:
            ai_tick_logs.append(GameLog(
                session_id=session_id,
                role="system",
                content=f"🟢 {actor_name} 的【{c}】状态到期解除",
                log_type="system",
            ))

    role_key = "enemy" if is_enemy else f"companion_{actor_name}"
    db.add(GameLog(
        session_id=session_id,
        role=role_key,
        content=narration,
        log_type="combat",
        dice_result={"attack": result_obj.attack_roll, "damage": total_damage} if result_obj else None,
    ))
    for tl in ai_tick_logs:
        db.add(tl)
    if conc_log:
        db.add(conc_log)

    await advance_ai_turn(combat, session, db, turn_order, next_index)

    player_check = await db.get(Character, session.player_character_id)
    combat_over, outcome = svc.check_combat_over(enemies, player_check.hp_current if player_check else 0)
    if combat_over:
        session.combat_active = False
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs:
                await db.delete(_old_cs)
        except Exception:
            pass

    player_targeted = (is_enemy and target_id == session.player_character_id)
    player_can_react = False
    reaction_prompt = None
    if player_targeted and player_check:
        player_ts = _get_ts(combat, session.player_character_id)
        player_can_react, has_prompt, reaction_prompt = build_reaction_prompt(
            player_check, player_ts, target_id, actor_name, actor_id, total_damage, result_obj
        )
        if not has_prompt:
            reaction_prompt = None

    await db.commit()
    return {
        "actor_name": actor_name,
        "actor_id": actor_id,
        "narration": narration,
        "attack_result": result_obj.attack_roll if result_obj else {},
        "damage": total_damage,
        "target_id": target_id,
        "target_new_hp": target_new_hp,
        "concentration_check": conc_log.dice_result if conc_log else None,
        "player_targeted": player_targeted,
        "player_can_react": player_can_react,
        "reaction_prompt": reaction_prompt,
        "next_turn_index": next_index,
        "round_number": combat.round_number,
        "combat_over": combat_over,
        "outcome": outcome,
        "entity_positions": dict(combat.entity_positions or {}),
    }
