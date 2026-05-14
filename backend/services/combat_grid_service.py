from typing import Any


def chebyshev_distance(pos_a: dict[str, Any], pos_b: dict[str, Any]) -> int:
    if not pos_a or not pos_b:
        return 999
    return max(
        abs(pos_a.get("x", 0) - pos_b.get("x", 0)),
        abs(pos_a.get("y", 0) - pos_b.get("y", 0)),
    )


def check_attack_range(
    attacker_position: dict[str, Any],
    target_position: dict[str, Any],
    is_ranged: bool,
    weapon_range: int = 0,
) -> tuple[bool, int, str | None]:
    distance = chebyshev_distance(attacker_position, target_position)
    if is_ranged:
        max_range = max(weapon_range // 5, 24) if weapon_range else 24
        if distance < 1:
            return True, distance, None
        if distance > max_range:
            return False, distance, f"目标超出射程（距离{distance*5}ft，最大{max_range*5}ft）"
        return True, distance, None

    if distance > 1:
        return False, distance, f"目标不在近战范围内（距离{distance*5}ft，需要5ft内）。请先移动到目标旁边"
    return True, distance, None


def ai_move_toward(
    actor_position: dict[str, Any],
    target_position: dict[str, Any],
    move_budget: int,
    positions: dict[str, dict[str, Any]],
    actor_id: str,
) -> dict[str, int] | None:
    if not actor_position or not target_position or move_budget <= 0:
        return None

    occupied = set()
    for entity_id, position in positions.items():
        if str(entity_id) != str(actor_id):
            occupied.add((position.get("x", -1), position.get("y", -1)))

    current_x, current_y = actor_position["x"], actor_position["y"]
    target_x, target_y = target_position["x"], target_position["y"]
    steps_taken = 0

    for _ in range(move_budget):
        if max(abs(current_x - target_x), abs(current_y - target_y)) <= 1:
            break

        step_x = 0 if current_x == target_x else (1 if target_x > current_x else -1)
        step_y = 0 if current_y == target_y else (1 if target_y > current_y else -1)

        candidates = [(current_x + step_x, current_y + step_y)]
        if step_x != 0 and step_y != 0:
            candidates += [(current_x + step_x, current_y), (current_x, current_y + step_y)]
        elif step_x != 0:
            candidates += [(current_x + step_x, current_y + 1), (current_x + step_x, current_y - 1)]
        else:
            candidates += [(current_x + 1, current_y + step_y), (current_x - 1, current_y + step_y)]

        moved = False
        for next_x, next_y in candidates:
            if 0 <= next_x < 20 and 0 <= next_y < 12 and (next_x, next_y) not in occupied:
                current_x, current_y = next_x, next_y
                steps_taken += 1
                moved = True
                break

        if not moved:
            break

    if steps_taken == 0:
        return None
    return {"x": current_x, "y": current_y, "steps": steps_taken}


def has_adjacent_enemy(entity_id: str, enemies: list[dict[str, Any]], positions: dict[str, Any]) -> bool:
    position = positions.get(str(entity_id))
    if not position:
        return False

    x_pos, y_pos = position.get("x", -99), position.get("y", -99)
    for enemy in enemies:
        if enemy.get("hp_current", 0) <= 0:
            continue
        enemy_position = positions.get(str(enemy["id"]))
        if not enemy_position:
            continue
        if max(abs(enemy_position["x"] - x_pos), abs(enemy_position["y"] - y_pos)) <= 1:
            return True
    return False


def has_ally_adjacent_to(
    target_id: str,
    attacker_id: str,
    allies: list[dict[str, Any]],
    positions: dict[str, Any],
) -> bool:
    target_position = positions.get(str(target_id))
    if not target_position:
        return False

    for ally in allies:
        ally_id = str(ally.get("id", ""))
        if ally_id == str(attacker_id):
            continue
        if ally.get("hp_current", 0) <= 0:
            continue
        ally_position = positions.get(ally_id)
        if not ally_position:
            continue
        if max(
            abs(ally_position["x"] - target_position["x"]),
            abs(ally_position["y"] - target_position["y"]),
        ) <= 1:
            return True
    return False
