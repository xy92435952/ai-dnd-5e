from services.action_parser_local import can_reach_melee_after_move, dist, nearest_enemy


def fallback_combat_action(
    player_input: str,
    game_state: dict,
    player_id: str,
    positions: dict,
    move_remaining: int,
) -> dict:
    target = nearest_enemy(game_state, positions, player_id)
    target_id = str(target.get("id")) if target else None
    actions = []
    if target_id:
        player_pos = positions.get(str(player_id), {})
        target_pos = positions.get(target_id, {})
        distance = dist(player_pos, target_pos) if player_pos and target_pos else 999
        if distance > 1 and move_remaining > 0:
            actions.append({
                "type": "move",
                "target_id": target_id,
                "target_pos": None,
                "reason": "靠近最近敌人",
            })
            if not can_reach_melee_after_move(distance, move_remaining):
                return {
                    "actions": actions,
                    "narrative_hint": player_input,
                    "_fallback": True,
                }
        actions.append({
            "type": "attack",
            "target_id": target_id,
            "is_ranged": False,
            "reason": player_input,
        })
    else:
        actions.append({
            "type": "attack",
            "target_id": None,
            "is_ranged": False,
            "reason": player_input,
        })

    return {
        "actions": actions,
        "narrative_hint": player_input,
        "_fallback": True,
    }
