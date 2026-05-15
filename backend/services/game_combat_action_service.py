from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from models import CombatState, GameLog, Session
from services.dnd_rules import roll_dice, roll_skill_check


async def execute_natural_language_combat_action(
    *,
    db,
    session: Session,
    combat_state: CombatState,
    player,
    characters: list,
    action_text: str,
) -> dict[str, Any]:
    """Parse and execute the legacy natural-language combat branch from /game/action."""
    from services.action_parser import parse_combat_action
    from api.combat import _get_ts, _save_ts, _check_attack_range, _ai_move_toward, _chebyshev_dist
    from services.combat_service import CombatService
    from services.combat_narrator import narrate_action

    combat_service = CombatService()
    positions = dict(combat_state.entity_positions or {})
    state = session.game_state or {}
    enemies = list(state.get("enemies", []))
    player_derived = player.derived or {}
    player_id = str(player.id)

    turn_state = _get_ts(combat_state, player_id)
    move_remaining = turn_state["movement_max"] - turn_state["movement_used"]
    parser_state = {
        "characters": [
            {
                "id": character.id,
                "name": character.name,
                "hp_current": character.hp_current,
                "hp_max": (character.derived or {}).get("hp_max", character.hp_current),
                "is_player": character.is_player,
            }
            for character in characters
            if character.hp_current > 0
        ],
        "enemies": [
            {
                "id": enemy["id"],
                "name": enemy.get("name", "?"),
                "hp_current": enemy.get("hp_current", 0),
                "hp_max": enemy.get("hp_max", 0),
            }
            for enemy in enemies
            if enemy.get("hp_current", 0) > 0
        ],
    }

    parsed = await parse_combat_action(
        player_input=action_text,
        game_state=parser_state,
        player_id=player_id,
        player_data={
            "name": player.name,
            "hp_current": player.hp_current,
            "hp_max": player_derived.get("hp_max", player.hp_current),
            "ac": player_derived.get("ac", 10),
        },
        positions=positions,
        move_remaining=move_remaining,
    )

    action_results: list[str] = []
    dice_display: list[dict[str, Any]] = []
    total_damage = 0
    action_used = False
    executed_action_types: list[str] = []

    for action in parsed["actions"]:
        action_type = action.get("type", "")

        if action_type == "move" and not action_used:
            move_remaining = _execute_move_action(
                combat_state=combat_state,
                positions=positions,
                player_id=player_id,
                turn_state=turn_state,
                move_remaining=move_remaining,
                action=action,
                action_results=action_results,
                executed_action_types=executed_action_types,
                move_toward=_ai_move_toward,
                save_turn_state=_save_ts,
            )

        elif action_type == "attack" and not action_used:
            action_used = True
            damage_done = _execute_attack_action(
                session=session,
                combat_state=combat_state,
                positions=positions,
                state=state,
                enemies=enemies,
                player_id=player_id,
                player_derived=player_derived,
                action=action,
                action_results=action_results,
                dice_display=dice_display,
                executed_action_types=executed_action_types,
                combat_service=combat_service,
                check_attack_range=_check_attack_range,
                distance=_chebyshev_dist,
            )
            total_damage += damage_done

        elif action_type == "creative" and not action_used:
            action_used = True
            damage_done = _execute_creative_action(
                session=session,
                state=state,
                enemies=enemies,
                player=player,
                player_derived=player_derived,
                action=action,
                action_results=action_results,
                dice_display=dice_display,
                executed_action_types=executed_action_types,
                combat_service=combat_service,
            )
            total_damage += damage_done

        elif action_type == "dodge" and not action_used:
            turn_state["dodging"] = True
            _save_ts(combat_state, player_id, turn_state)
            action_results.append("采取闪避动作，攻击你的敌人获得劣势")
            executed_action_types.append("dodge")
            action_used = True

        elif action_type == "dash" and not action_used:
            turn_state["movement_max"] *= 2
            _save_ts(combat_state, player_id, turn_state)
            action_results.append("冲刺！移动力翻倍")
            executed_action_types.append("dash")
            action_used = True

        elif action_type == "disengage" and not action_used:
            turn_state["disengaged"] = True
            _save_ts(combat_state, player_id, turn_state)
            action_results.append("脱离接战，移动不触发借机攻击")
            executed_action_types.append("disengage")
            action_used = True

    if action_used:
        turn_state["action_used"] = True
        _save_ts(combat_state, player_id, turn_state)

    mechanical_summary = " | ".join(action_results) if action_results else "未执行有效行动"
    narration_action_type = _choose_narration_action_type(
        executed_action_types=executed_action_types,
        parsed_actions=parsed["actions"],
    )
    narrative = await narrate_action(
        actor_name=player.name,
        actor_class=player.char_class,
        target_name="",
        action_type=narration_action_type,
        extra_details=f"玩家行动: {action_text}\n结果: {mechanical_summary}",
        damage=total_damage,
    )
    if not narrative:
        narrative = mechanical_summary

    combat_over = False
    outcome = None
    alive_enemies = [enemy for enemy in enemies if enemy.get("hp_current", 0) > 0]
    if not alive_enemies:
        combat_over = True
        outcome = "victory"
        session.combat_active = False

    db.add(GameLog(
        session_id=session.id,
        role="dm",
        content=narrative,
        log_type="combat",
        dice_result=dice_display if dice_display else None,
    ))
    combat_update = {
        "entity_positions": dict(combat_state.entity_positions or {}),
        "turn_states": dict(combat_state.turn_states or {}),
        "current_turn_index": combat_state.current_turn_index,
        "round_number": combat_state.round_number,
    }

    await db.commit()
    return {
        "type": "combat_action",
        "narrative": narrative,
        "companion_reactions": "",
        "dice_display": dice_display,
        "player_choices": [],
        "needs_check": {"required": False},
        "combat_triggered": False,
        "combat_ended": combat_over,
        "combat_end_result": outcome,
        "combat_update": combat_update,
        "action_results": action_results,
        "errors": [],
    }


def _execute_move_action(
    *,
    combat_state,
    positions: dict[str, Any],
    player_id: str,
    turn_state: dict[str, Any],
    move_remaining: int,
    action: dict[str, Any],
    action_results: list[str],
    executed_action_types: list[str],
    move_toward,
    save_turn_state,
) -> int:
    move_target_id = action.get("target_id")
    move_target_pos = action.get("target_pos")
    destination = positions.get(str(move_target_id)) if move_target_id else move_target_pos
    if not destination:
        return move_remaining

    current_position = positions.get(player_id)
    if not current_position:
        return move_remaining

    result = move_toward(current_position, destination, move_remaining, positions, player_id)
    if not result:
        return move_remaining

    positions[player_id] = {"x": result["x"], "y": result["y"]}
    combat_state.entity_positions = positions
    turn_state["movement_used"] += result["steps"]
    move_remaining -= result["steps"]
    save_turn_state(combat_state, player_id, turn_state)
    action_results.append(f"移动了 {result['steps'] * 5}ft")
    executed_action_types.append("move")
    return move_remaining


def _execute_attack_action(
    *,
    session: Session,
    combat_state,
    positions: dict[str, Any],
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    player_id: str,
    player_derived: dict[str, Any],
    action: dict[str, Any],
    action_results: list[str],
    dice_display: list[dict[str, Any]],
    executed_action_types: list[str],
    combat_service,
    check_attack_range,
    distance,
) -> int:
    target_id = action.get("target_id")
    is_ranged = action.get("is_ranged", False)
    if not target_id:
        target_id = _find_closest_alive_enemy_id(
            enemies=enemies,
            positions=positions,
            player_position=positions.get(player_id, {}),
            distance=distance,
        )
    if not target_id:
        return 0

    attacker_position = positions.get(player_id)
    target_position = positions.get(str(target_id))
    in_range, dist, _ = check_attack_range(attacker_position, target_position, is_ranged)
    if not in_range:
        action_results.append(f"目标不在攻击范围内（距离{dist * 5}ft）")
        executed_action_types.append("out_of_range")
        return 0

    target_enemy = next((enemy for enemy in enemies if str(enemy["id"]) == str(target_id)), None)
    if not target_enemy:
        return 0

    target_derived = target_enemy.get("derived", {})
    if not target_derived.get("ac"):
        target_derived["ac"] = target_enemy.get("ac", 13)

    attack_result = combat_service.resolve_melee_attack(
        attacker_derived=player_derived,
        target_derived=target_derived,
        is_ranged=is_ranged,
    )
    d20 = attack_result.attack_roll.get("d20", 0)
    hit = attack_result.attack_roll.get("hit", False)
    is_crit = attack_result.attack_roll.get("is_crit", False)
    damage = attack_result.damage
    dice_display.append({
        "label": "攻击检定",
        "dice_face": 20,
        "raw": d20,
        "total": attack_result.attack_roll.get("attack_total", d20),
        "against": f"AC {target_derived.get('ac', 13)}",
        "outcome": "暴击" if is_crit else ("命中" if hit else "未命中"),
    })

    total_damage = 0
    if hit:
        target_enemy["hp_current"] = combat_service.apply_damage(
            target_enemy.get("hp_current", 0),
            damage,
            target_enemy.get("derived", {}).get("hp_max", 10),
        )
        total_damage += damage
        dice_display.append({
            "label": "伤害",
            "dice_face": player_derived.get("hit_die", 8),
            "raw": damage,
            "total": damage,
        })
        crit_str = "暴击！" if is_crit else ""
        action_results.append(f"{crit_str}攻击命中 {target_enemy.get('name', '敌人')}，造成 {damage} 点伤害")
        if target_enemy["hp_current"] <= 0:
            target_enemy["dead"] = True
            action_results.append(f"{target_enemy.get('name', '敌人')} 被击倒！")
    else:
        action_results.append(f"攻击 {target_enemy.get('name', '敌人')} 未命中（d20={d20}）")

    state["enemies"] = enemies
    session.game_state = dict(state)
    flag_modified(session, "game_state")
    executed_action_types.append("attack")
    return total_damage


def _execute_creative_action(
    *,
    session: Session,
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    player,
    player_derived: dict[str, Any],
    action: dict[str, Any],
    action_results: list[str],
    dice_display: list[dict[str, Any]],
    executed_action_types: list[str],
    combat_service,
) -> int:
    check_type = action.get("check_type", "str")
    dc = action.get("dc", 15)
    description = action.get("description", "创意行动")
    check_result = roll_skill_check(
        character={"derived": player_derived, "proficient_skills": player.proficient_skills or []},
        skill=check_type,
        dc=dc,
    )
    d20 = check_result.get("d20", 10)
    total = check_result.get("total", 10)
    success = check_result.get("success", False)
    dice_display.append({
        "label": f"{description} 检定",
        "dice_face": 20,
        "raw": d20,
        "modifier": f"+{check_result.get('modifier', 0)}",
        "total": total,
        "against": f"DC {dc}",
        "outcome": "成功" if success else "失败",
    })

    total_damage = 0
    if success:
        total_damage = _apply_creative_damage(
            session=session,
            state=state,
            enemies=enemies,
            action=action,
            dice_display=dice_display,
            combat_service=combat_service,
        )
        action_results.append(
            f"{description} — 成功！（d20={d20}+{check_result.get('modifier', 0)}={total} vs DC{dc}）"
            + (f" {action.get('effect_on_success', '')}" if action.get("effect_on_success") else "")
        )
    else:
        action_results.append(
            f"{description} — 失败（d20={d20}+{check_result.get('modifier', 0)}={total} vs DC{dc}）"
            + (f" {action.get('effect_on_fail', '')}" if action.get("effect_on_fail") else "")
        )
    executed_action_types.append("creative")
    return total_damage


def _apply_creative_damage(
    *,
    session: Session,
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    action: dict[str, Any],
    dice_display: list[dict[str, Any]],
    combat_service,
) -> int:
    damage_dice = action.get("damage_dice")
    if not damage_dice:
        return 0

    damage_roll = roll_dice(damage_dice)
    creative_damage = damage_roll["total"]
    target_id = action.get("target_id")
    if target_id:
        target_enemy = next((enemy for enemy in enemies if str(enemy["id"]) == str(target_id)), None)
        if target_enemy:
            target_enemy["hp_current"] = combat_service.apply_damage(
                target_enemy.get("hp_current", 0),
                creative_damage,
                target_enemy.get("derived", {}).get("hp_max", 10),
            )
            state["enemies"] = enemies
            session.game_state = dict(state)
            flag_modified(session, "game_state")
    dice_display.append({"label": "伤害", "raw": creative_damage, "total": creative_damage})
    return creative_damage


def _find_closest_alive_enemy_id(
    *,
    enemies: list[dict[str, Any]],
    positions: dict[str, Any],
    player_position: dict[str, Any],
    distance,
) -> str | None:
    target_id = None
    closest_distance = 999
    for enemy in enemies:
        if enemy.get("hp_current", 0) <= 0:
            continue
        enemy_position = positions.get(str(enemy["id"]), {})
        current_distance = distance(player_position, enemy_position)
        if current_distance < closest_distance:
            closest_distance = current_distance
            target_id = enemy["id"]
    return target_id


def _choose_narration_action_type(
    *,
    executed_action_types: list[str],
    parsed_actions: list[dict[str, Any]],
) -> str:
    if "creative" in executed_action_types:
        return "creative"
    if "attack" in executed_action_types:
        return "attack"
    if "out_of_range" in executed_action_types:
        return "out_of_range"
    if executed_action_types:
        return executed_action_types[-1]
    if any(action.get("type") == "creative" for action in parsed_actions):
        return "creative"
    return "move"
