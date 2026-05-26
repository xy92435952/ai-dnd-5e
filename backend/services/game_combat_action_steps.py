from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from models import Session
from services.combat_damage_bonus_service import apply_sustained_damage_effects


def execute_move_action(
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


def execute_attack_action(
    *,
    session: Session,
    combat_state,
    positions: dict[str, Any],
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    player_id: str,
    player_derived: dict[str, Any],
    player_conditions: list[str] | None,
    player_concentration: str | None = None,
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
        target_id = find_closest_alive_enemy_id(
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

    target_conditions = list(target_enemy.get("conditions", []))
    advantage = "guiding_bolt" in target_conditions
    if advantage:
        target_conditions = [
            condition for condition in target_conditions
            if condition != "guiding_bolt"
        ]
        target_enemy["conditions"] = target_conditions
        durations = dict(target_enemy.get("condition_durations", {}))
        durations.pop("guiding_bolt", None)
        target_enemy["condition_durations"] = durations

    target_derived = target_enemy.get("derived", {})
    if not target_derived.get("ac"):
        target_derived["ac"] = target_enemy.get("ac", 13)

    attack_result = combat_service.resolve_melee_attack(
        attacker_derived=player_derived,
        target_derived=target_derived,
        advantage=advantage,
        is_ranged=is_ranged,
        attacker_conditions=player_conditions or [],
        target_conditions=target_conditions,
        distance=dist,
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
        extra_damage_notes: list[str] = []
        damage_type = player_derived.get("damage_type", "piercing")
        resistance_func = getattr(
            combat_service,
            "apply_damage_with_resistance",
            lambda value, *_args: value,
        )
        damage = resistance_func(
            damage,
            damage_type,
            target_enemy.get("resistances", []),
            target_enemy.get("immunities", []),
            target_enemy.get("vulnerabilities", []),
        )
        sustained = apply_sustained_damage_effects(
            damage=damage,
            extra_damage_notes=extra_damage_notes,
            attacker_concentration=player_concentration,
            target_conditions=target_conditions,
            target_id=target_enemy["id"],
            target_is_enemy=True,
            enemies=enemies,
            weapon_damage_type=damage_type,
            apply_damage_with_resistance=resistance_func,
        )
        damage = sustained.damage
        extra_damage_notes = sustained.extra_damage_notes
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
        if extra_damage_notes:
            action_results.append(f"额外伤害：{', '.join(extra_damage_notes)}")
        if target_enemy["hp_current"] <= 0:
            target_enemy["dead"] = True
            action_results.append(f"{target_enemy.get('name', '敌人')} 被击倒！")
    else:
        action_results.append(f"攻击 {target_enemy.get('name', '敌人')} 未命中（d20={d20}）")

    state["enemies"] = enemies
    session.game_state = dict(state)
    try:
        flag_modified(session, "game_state")
    except Exception:
        pass
    executed_action_types.append("attack")
    return total_damage


def find_closest_alive_enemy_id(
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
