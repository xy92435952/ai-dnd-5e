"""
api.combat.ai_turn_actions — AI simple action branch handlers.
"""
from api.combat._shared import _get_ts, _save_ts, _ai_move_toward
from api.combat.ai_turn_utils import advance_ai_turn


async def handle_ai_simple_action(
    combat,
    session,
    db,
    turn_order,
    next_index: int,
    actor_id: str,
    actor_name: str,
    decided_action: str,
    decided_target_id: str | None,
    decided_reason: str,
    positions: dict,
):
    """Handle dodge / dash / disengage actions and return a response dict when handled."""
    if decided_action == "dodge":
        ts_dodge = _get_ts(combat, actor_id)
        ts_dodge["dodging"] = True
        _save_ts(combat, actor_id, ts_dodge)
        await advance_ai_turn(combat, session, db, turn_order, next_index)
        await db.commit()
        return {
            "actor_name": actor_name,
            "actor_id": actor_id,
            "narration": f"🛡️ {actor_name} 采取闪避动作。{decided_reason}",
            "attack_result": {},
            "damage": 0,
            "target_id": None,
            "target_new_hp": None,
            "next_turn_index": next_index,
            "round_number": combat.round_number,
            "combat_over": False,
            "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        }

    if decided_action == "dash":
        if decided_target_id:
            dash_tgt_pos = positions.get(str(decided_target_id))
            dash_ts = _get_ts(combat, actor_id)
            dash_budget = (dash_ts["movement_max"] - dash_ts["movement_used"]) + dash_ts["movement_max"]
            dash_result = _ai_move_toward(positions.get(str(actor_id)), dash_tgt_pos, dash_budget, positions, actor_id)
            if dash_result:
                positions[str(actor_id)] = {"x": dash_result["x"], "y": dash_result["y"]}
                combat.entity_positions = positions
        await advance_ai_turn(combat, session, db, turn_order, next_index)
        await db.commit()
        return {
            "actor_name": actor_name,
            "actor_id": actor_id,
            "narration": f"🏃 {actor_name} 全力冲刺！{decided_reason}",
            "attack_result": {},
            "damage": 0,
            "target_id": None,
            "target_new_hp": None,
            "next_turn_index": next_index,
            "round_number": combat.round_number,
            "combat_over": False,
            "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        }

    if decided_action == "disengage":
        ts_dis = _get_ts(combat, actor_id)
        ts_dis["disengaged"] = True
        _save_ts(combat, actor_id, ts_dis)
        await advance_ai_turn(combat, session, db, turn_order, next_index)
        await db.commit()
        return {
            "actor_name": actor_name,
            "actor_id": actor_id,
            "narration": f"🚪 {actor_name} 脱离战斗！{decided_reason}",
            "attack_result": {},
            "damage": 0,
            "target_id": None,
            "target_new_hp": None,
            "next_turn_index": next_index,
            "round_number": combat.round_number,
            "combat_over": False,
            "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        }

    return None
