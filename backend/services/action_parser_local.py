import re


ATTACK_WORDS = ("攻击", "打", "砍", "劈", "刺", "射", "开火", "attack", "strike", "shoot")
MOVE_WORDS = ("移动", "靠近", "冲", "跑", "走到", "接近", "move", "approach", "charge")
RANGED_WORDS = ("弓", "弩", "射", "远程", "火焰箭", "firebolt", "ray", "shoot")
DODGE_WORDS = ("闪避", "躲避", "防御姿态", "dodge")
DASH_WORDS = ("冲刺", "疾跑", "dash")
DISENGAGE_WORDS = ("脱离", "撤离", "撤退", "disengage")
HELP_WORDS = ("协助", "帮助", "支援", "help")
COVER_WORDS = ("掩体", "躲到", "躲进", "掩护", "cover")
UNREACHABLE_MELEE_HINT = "已靠近，下一回合可继续攻击"


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


def parse_target_pos(text: str) -> dict | None:
    patterns = (
        r"(?:x\s*[=:：]\s*)?(-?\d{1,2})\s*[,，]\s*(?:y\s*[=:：]\s*)?(-?\d{1,2})",
        r"x\s*[=:：]\s*(-?\d{1,2}).*?y\s*[=:：]\s*(-?\d{1,2})",
        r"坐标\s*(-?\d{1,2})\s+(-?\d{1,2})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return {"x": int(match.group(1)), "y": int(match.group(2))}
    return None


def living_allies(game_state: dict, player_id: str) -> list[dict]:
    return [
        character
        for character in game_state.get("characters", [])
        if str(character.get("id")) != str(player_id) and character.get("hp_current", 0) > 0
    ]


def ally_name_matches(text: str, ally: dict) -> bool:
    name = str(ally.get("name") or "")
    return bool(name and name in text)


def target_ally_from_text(text: str, game_state: dict, player_id: str) -> dict | None:
    allies = living_allies(game_state, player_id)
    for ally in allies:
        if ally_name_matches(text, ally):
            return ally
    return allies[0] if len(allies) == 1 else None


def has_any_word(text: str, lowered: str, words: tuple[str, ...]) -> bool:
    return any(word in lowered or word in text for word in words)


def parse_local_combat_action(
    player_input: str,
    game_state: dict,
    player_id: str,
    positions: dict,
    move_remaining: int,
) -> dict | None:
    text = (player_input or "").strip()
    lowered = text.lower()
    wants_help = has_any_word(text, lowered, HELP_WORDS)
    if wants_help:
        ally = target_ally_from_text(text, game_state, player_id)
        return {
            "actions": [{
                "type": "help",
                "target_id": str(ally.get("id")) if ally else None,
                "reason": "协助盟友",
            }],
            "narrative_hint": text,
            "_fallback": False,
        }

    if has_any_word(text, lowered, DODGE_WORDS):
        return {"actions": [{"type": "dodge"}], "narrative_hint": text, "_fallback": False}
    if has_any_word(text, lowered, DASH_WORDS):
        return {"actions": [{"type": "dash"}], "narrative_hint": text, "_fallback": False}
    if has_any_word(text, lowered, DISENGAGE_WORDS):
        return {"actions": [{"type": "disengage"}], "narrative_hint": text, "_fallback": False}

    target_pos = parse_target_pos(text)
    if target_pos and (has_any_word(text, lowered, MOVE_WORDS) or has_any_word(text, lowered, COVER_WORDS)):
        reason = "移动到掩体后" if has_any_word(text, lowered, COVER_WORDS) else "移动到指定坐标"
        return {
            "actions": [{
                "type": "move",
                "target_id": None,
                "target_pos": target_pos,
                "reason": reason,
            }],
            "narrative_hint": text,
            "_fallback": False,
        }

    wants_attack = has_any_word(text, lowered, ATTACK_WORDS)
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
            actions[-1]["followup_hint"] = UNREACHABLE_MELEE_HINT
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
