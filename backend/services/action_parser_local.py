import re


ATTACK_WORDS = ("攻击", "打", "砍", "劈", "刺", "射", "开火", "attack", "strike", "shoot")
MOVE_WORDS = ("移动", "靠近", "冲", "跑", "走到", "接近", "move", "approach", "charge")
RANGED_WORDS = ("弓", "弩", "射", "远程", "火焰箭", "firebolt", "ray", "shoot")


def dist(a: dict, b: dict) -> int:
    return max(abs(a.get("x", 0) - b.get("x", 0)), abs(a.get("y", 0) - b.get("y", 0)))


def can_reach_melee_after_move(distance: int, move_remaining: int) -> bool:
    return max(distance - max(move_remaining, 0), 0) <= 1


def living_enemies(game_state: dict) -> list[dict]:
    return [e for e in game_state.get("enemies", []) if e.get("hp_current", 0) > 0]


def enemy_name_matches(text: str, enemy: dict) -> bool:
    name = str(enemy.get("name") or "")
    return bool(name and name in text)


def nearest_enemy(game_state: dict, positions: dict, player_id: str) -> dict | None:
    player_pos = positions.get(str(player_id), {})
    enemies = living_enemies(game_state)
    if not enemies:
        return None
    return min(
        enemies,
        key=lambda e: dist(player_pos, positions.get(str(e.get("id")), {"x": 999, "y": 999})),
    )


def target_enemy_from_text(text: str, game_state: dict, positions: dict, player_id: str) -> dict | None:
    enemies = living_enemies(game_state)
    for enemy in enemies:
        if enemy_name_matches(text, enemy):
            return enemy
    if re.search(r"(最近|身旁|旁边|面前|nearest|closest)", text, re.IGNORECASE):
        return nearest_enemy(game_state, positions, player_id)
    return nearest_enemy(game_state, positions, player_id) if len(enemies) == 1 else None


def parse_local_combat_action(
    player_input: str,
    game_state: dict,
    player_id: str,
    positions: dict,
    move_remaining: int,
) -> dict | None:
    text = (player_input or "").strip()
    lowered = text.lower()
    wants_attack = any(word in lowered or word in text for word in ATTACK_WORDS)
    if not wants_attack:
        return None

    target = target_enemy_from_text(text, game_state, positions, player_id)
    if not target:
        return None

    target_id = str(target.get("id"))
    player_pos = positions.get(str(player_id), {})
    target_pos = positions.get(target_id, {})
    distance = dist(player_pos, target_pos) if player_pos and target_pos else 999
    is_ranged = any(word in lowered or word in text for word in RANGED_WORDS)
    wants_move = any(word in lowered or word in text for word in MOVE_WORDS)

    actions = []
    if not is_ranged and distance > 1 and wants_move and move_remaining > 0:
        actions.append({
            "type": "move",
            "target_id": target_id,
            "target_pos": None,
            "reason": "靠近目标",
        })
        if not can_reach_melee_after_move(distance, move_remaining):
            return {
                "actions": actions,
                "narrative_hint": text,
                "_fallback": False,
            }
    actions.append({
        "type": "attack",
        "target_id": target_id,
        "is_ranged": is_ranged,
        "reason": "远程攻击" if is_ranged else "近战攻击",
    })
    return {
        "actions": actions,
        "narrative_hint": text,
        "_fallback": False,
    }
