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
from api.combat.ai_turn_utils import advance_ai_turn, build_reaction_prompt, tick_ai_actor_conditions
from services.combat_ai_attack_service import (
    apply_character_damage_resistance,
    choose_ai_attack_target,
    infer_ai_is_ranged,
    target_is_dodging,
    target_conditions,
    pack_tactics_advantage,
)
from services.combat_damage_bonus_service import apply_sustained_damage_effects
from services.combat_concentration_effect_service import clear_concentration_effects_for_caster
from services.combat_defender_reaction_service import apply_defender_interception
from services.combat_guiding_bolt_service import consume_guiding_bolt_condition
from services.combat_movement_rules_service import (
    MovementRuleError,
    apply_stand_up_from_prone,
    validate_displacement_allowed,
)
from services.combat_narrator import narrate_batch
from services.combat_reaction_service import build_pending_attack_reaction
from services.combat_temporary_hp_service import (
    apply_generic_temporary_hp_to_character,
    apply_armor_of_agathys_retaliation_to_enemy,
    build_character_target_state,
    get_armor_of_agathys_retaliation_damage,
)
from services.dnd_rules import (
    roll_dice,
    _normalize_class,
    apply_character_damage,
    get_temporary_hp,
    get_wild_shape_hp,
)


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
    target_data = choose_ai_attack_target(
        decided_target_id=decided_target_id,
        enemies_alive=enemies_alive,
        all_characters=all_characters,
        actor_is_enemy=is_enemy,
        player=player,
        companions_alive=companions_alive,
        combat_service=svc,
    )

    target_id = None
    target_name = ""
    target_new_hp = None
    target_state = None
    total_damage = 0
    all_narrations = []
    target_attack_events = []
    state = session.game_state or {}

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
    elif is_enemy and e:
        actor_ts = _get_ts(combat, actor_id)
        num_attacks = max(1, int(actor_ts.get("attacks_max") or e.get("multiattack") or e.get("attacks_max") or 1))

    result_obj = None
    first_attack_roll = None

    if target_data:
        target_id = target_data["id"]
        target_derived = target_data.get("derived", {})
        target_is_enemy = not is_enemy

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

        ai_is_ranged = infer_ai_is_ranged(
            archer=achar,
            enemies=enemies,
            actor_id=actor_id,
        )

        in_range, ai_dist, _ = _check_attack_range(ai_atk_pos, ai_tgt_pos, ai_is_ranged)
        if not in_range and ai_atk_pos and ai_tgt_pos:
            actor_ts_pre = _get_ts(combat, actor_id)
            actor_conditions = (
                list(e.get("conditions", []))
                if is_enemy and e
                else list(getattr(achar, "conditions", None) or [])
            )
            try:
                stand_result = apply_stand_up_from_prone(actor_ts_pre, actor_conditions)
            except MovementRuleError:
                stand_result = None
                all_narrations.append(f"{actor_name} 倒地且移动力不足，无法起身接近目标")
            if stand_result:
                actor_ts_pre = stand_result.turn_state
                if stand_result.stood_up:
                    if is_enemy and e:
                        e["conditions"] = stand_result.conditions
                        state["enemies"] = enemies
                        session.game_state = dict(state)
                        flag_modified(session, "game_state")
                    elif achar:
                        achar.conditions = stand_result.conditions
                    all_narrations.append(f"{actor_name} 起身，消耗 {stand_result.movement_cost * 5}ft 移动力")
            move_remaining = actor_ts_pre["movement_max"] - actor_ts_pre["movement_used"]
            movement_conditions = stand_result.conditions if stand_result else actor_conditions
            desired_distance = max(
                abs(ai_atk_pos["x"] - ai_tgt_pos["x"]),
                abs(ai_atk_pos["y"] - ai_tgt_pos["y"]),
            )
            try:
                validate_displacement_allowed(movement_conditions, desired_distance)
                move_result = _ai_move_toward(ai_atk_pos, ai_tgt_pos, move_remaining, positions, actor_id)
            except MovementRuleError:
                move_result = None
                all_narrations.append(f"{actor_name} 的速度为 0，无法接近目标")
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
        target_dodging = target_is_dodging(
            combat=combat,
            target_id=target_id,
            target_data=target_data,
            target_character=target_char_for_shield,
        )
        ai_target_conditions = target_conditions(
            target_data=target_data,
            target_character=target_char_for_shield,
        )
        if "guiding_bolt" in ai_target_conditions:
            extra_adv = True
        if is_enemy and e and pack_tactics_advantage(
            attacker=e,
            target_id=target_id,
            allies=enemies,
            positions=positions,
            has_ally_adjacent_to=_has_ally_adjacent_to,
        ):
            extra_adv = True
        defender_interception = None
        if target_is_enemy and not target_dodging:
            defender_interception = apply_defender_interception(
                combat=combat,
                attacker_id=actor_id,
                target_id=target_id,
                enemies=enemies,
                positions=positions,
                get_turn_state_func=_get_ts,
                save_turn_state_func=_save_ts,
            )

        for atk_idx in range(num_attacks):
            result_obj = svc.resolve_melee_attack(
                attacker_derived=actor_derived,
                target_derived=ai_target_derived,
                advantage=extra_adv if atk_idx == 0 else False,
                disadvantage=target_dodging or (bool(defender_interception) and atk_idx == 0),
                is_ranged=ai_is_ranged,
                attacker_conditions=(
                    list(e.get("conditions", []))
                    if is_enemy and e
                    else list(getattr(achar, "conditions", None) or [])
                ),
                target_conditions=ai_target_conditions,
                distance=ai_dist,
            )
            if atk_idx == 0 and "guiding_bolt" in ai_target_conditions:
                await consume_guiding_bolt_condition(
                    db,
                    target_id=target_id,
                    target_is_enemy=not bool(target_char_for_shield),
                    enemies=enemies,
                    session=session,
                )
                ai_target_conditions = [
                    condition for condition in ai_target_conditions
                    if condition != "guiding_bolt"
                ]
            if first_attack_roll is None:
                if defender_interception:
                    result_obj.attack_roll = {
                        **result_obj.attack_roll,
                        "defender_interception": defender_interception,
                    }
                first_attack_roll = result_obj

            atk_damage = result_obj.damage
            applied_damage = atk_damage
            extra_damage_notes: list[str] = []

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
                weapon_damage_type = actor_derived.get("damage_type", "piercing")
                if target_is_enemy:
                    target_enemy_data = next((enemy for enemy in enemies if enemy["id"] == target_id), None)
                    if target_enemy_data:
                        weapon_damage_type = (
                            actor_derived.get("damage_type")
                            or target_enemy_data.get("damage_type")
                            or target_enemy_data.get("derived", {}).get("damage_type")
                            or "piercing"
                        )
                        atk_damage = svc.apply_damage_with_resistance(
                            atk_damage,
                            weapon_damage_type,
                            target_enemy_data.get("resistances", []),
                            target_enemy_data.get("immunities", []),
                            target_enemy_data.get("vulnerabilities", []),
                        )
                else:
                    tchar_for_resistance = await db.get(Character, target_id)
                    if tchar_for_resistance:
                        weapon_damage_type = actor_derived.get("damage_type", "bludgeoning")
                        atk_damage, _resistance_applied = apply_character_damage_resistance(
                            tchar_for_resistance,
                            atk_damage,
                            weapon_damage_type,
                        )
                sustained = apply_sustained_damage_effects(
                    damage=atk_damage,
                    extra_damage_notes=extra_damage_notes,
                    attacker_concentration=(e.get("concentration") if is_enemy and e else getattr(achar, "concentration", None)),
                    target_conditions=ai_target_conditions,
                    target_id=target_id,
                    target_is_enemy=target_is_enemy,
                    enemies=enemies,
                    weapon_damage_type=weapon_damage_type,
                    apply_damage_with_resistance=svc.apply_damage_with_resistance,
                )
                atk_damage = sustained.damage
                extra_damage_notes = sustained.extra_damage_notes

                if target_is_enemy:
                    for enemy in enemies:
                        if enemy["id"] == target_id:
                            enemy["hp_current"] = svc.apply_damage(enemy.get("hp_current", 0), atk_damage, enemy.get("derived", {}).get("hp_max", 10))
                            target_new_hp = enemy["hp_current"]
                    applied_damage = atk_damage
                    state["enemies"] = enemies
                    session.game_state = dict(state)
                    flag_modified(session, "game_state")
                    target_name = target_data.get("name", "敌人")
                else:
                    tchar = await db.get(Character, target_id)
                    if tchar:
                        hp_before_damage = tchar.hp_current
                        temporary_hp_before_damage = get_temporary_hp(tchar)
                        wild_shape_hp_before_damage = get_wild_shape_hp(tchar)
                        class_resources_before_damage = dict(tchar.class_resources or {})
                        conditions_before_damage = list(tchar.conditions or [])
                        condition_durations_before_damage = dict(tchar.condition_durations or {})
                        armor_retaliation_damage = (
                            get_armor_of_agathys_retaliation_damage(tchar)
                            if is_enemy and not ai_is_ranged
                            else 0
                        )
                        damage_result = apply_character_damage(
                            tchar,
                            atk_damage,
                            is_critical=result_obj.attack_roll.get("is_crit", False),
                        )
                        retaliation = None
                        if is_enemy and not ai_is_ranged:
                            retaliation = apply_armor_of_agathys_retaliation_to_enemy(
                                defender=tchar,
                                attacker_enemy=e,
                                enemies=enemies,
                                melee_hit=True,
                                retaliation_damage=armor_retaliation_damage,
                            )
                            if retaliation:
                                state["enemies"] = enemies
                                session.game_state = dict(state)
                                flag_modified(session, "game_state")
                        applied_damage = atk_damage
                        target_new_hp = tchar.hp_current
                        target_state = build_character_target_state(tchar)
                        if retaliation:
                            target_state["retaliation"] = retaliation
                        target_name = tchar.name
                        if tchar.is_player and applied_damage > 0:
                            target_attack_events.append({
                                "attack_total": result_obj.attack_roll.get("attack_total", 0),
                                "target_ac": result_obj.attack_roll.get("target_ac", target_derived.get("ac", 10)),
                                "damage": applied_damage,
                                "damage_type": weapon_damage_type,
                                "hp_before": hp_before_damage,
                                "hp_after": target_new_hp,
                                "temporary_hp_before": temporary_hp_before_damage,
                                "temporary_hp_after": damage_result["temporary_hp_after"],
                                "wild_shape_hp_before": wild_shape_hp_before_damage,
                                "wild_shape_hp_after": damage_result["wild_shape_hp_after"],
                                "class_resources_before": class_resources_before_damage,
                                "conditions_before": conditions_before_damage,
                                "condition_durations_before": condition_durations_before_damage,
                                "hit": True,
                            })

            total_damage += applied_damage
            attack_narration = svc._build_narration(actor_name, target_name or target_data.get("name", "?"), result_obj.attack_roll, applied_damage)
            if extra_damage_notes:
                attack_narration += f" ({', '.join(extra_damage_notes)})"
            if defender_interception and atk_idx == 0:
                attack_narration += f"（{defender_interception['defender_name']} 护卫干扰）"
            all_narrations.append(attack_narration)

            if target_new_hp is not None and target_new_hp <= 0 and not is_enemy and achar:
                ai_sub_eff = actor_derived.get("subclass_effects", {})
                if ai_sub_eff.get("dark_ones_blessing"):
                    cha_val = actor_derived.get("ability_modifiers", {}).get("cha", 0)
                    _temp_hp = max(1, cha_val + ai_level)
                    apply_generic_temporary_hp_to_character(
                        achar,
                        amount=_temp_hp,
                        source="dark_ones_blessing",
                    )
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
            if conc_log and conc_log.dice_result and conc_log.dice_result.get("broke"):
                await clear_concentration_effects_for_caster(
                    db,
                    session,
                    tchar_conc.id,
                    spell_name=conc_log.dice_result.get("spell_name"),
                )

    ai_tick_logs = tick_ai_actor_conditions(
        session_id=session_id,
        session=session,
        actor_name=actor_name,
        is_enemy=is_enemy,
        enemy=e,
        character=achar,
        enemies=enemies,
    )

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
    party_characters = [
        await db.get(Character, str(character["id"]))
        for character in all_characters
        if character.get("id")
    ]
    alive_party = [
        character
        for character in party_characters
        if character and character.hp_current > 0
    ]
    player_hp_for_outcome = max(
        [character.hp_current for character in alive_party],
        default=player_check.hp_current if player_check else 0,
    )
    combat_over, outcome = svc.check_combat_over(enemies, player_hp_for_outcome)
    if combat_over:
        session.combat_active = False
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs:
                await db.delete(_old_cs)
        except Exception:
            pass

    target_player = None
    if is_enemy and target_id:
        target_player = await db.get(Character, target_id)
        if target_player and not target_player.is_player:
            target_player = None
    player_targeted = target_player is not None
    player_can_react = False
    reaction_prompt = None
    if player_targeted and target_player:
        player_ts = _get_ts(combat, target_player.id)
        pending_reaction = build_pending_attack_reaction(
            attacker_id=actor_id,
            attacker_name=actor_name,
            target_id=target_player.id,
            attack_events=target_attack_events,
        )
        if pending_reaction:
            player_ts["pending_attack_reaction"] = pending_reaction
            _save_ts(combat, target_player.id, player_ts)
        player_can_react, has_prompt, reaction_prompt = build_reaction_prompt(
            target_player, player_ts, target_id, actor_name, actor_id, total_damage, result_obj
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
        "target_state": target_state,
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
