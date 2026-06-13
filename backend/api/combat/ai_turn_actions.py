"""
api.combat.ai_turn_actions — AI simple action branch handlers.
"""
from api.combat._shared import _get_ts, _save_ts, _ai_move_toward
from api.combat.ai_turn_utils import advance_ai_turn, tick_ai_actor_conditions
from services.combat_ai_role_decision_service import tactical_decision_metadata
from services.combat_movement_rules_service import (
    MovementRuleError,
    apply_stand_up_from_prone,
    validate_displacement_allowed,
    validate_frightened_movement,
)


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
    is_enemy: bool,
    enemy=None,
    character=None,
    enemies: list | None = None,
    session_id: str | None = None,
    decision: dict | None = None,
):
    """Handle dodge / dash / disengage actions and return a response dict when handled."""
    tactical_decision = tactical_decision_metadata(decision)
    if decided_action == "dodge":
        ts_dodge = _get_ts(combat, actor_id)
        ts_dodge["action_used"] = True
        ts_dodge["dodging"] = True
        _save_ts(combat, actor_id, ts_dodge)
        tick_logs = tick_ai_actor_conditions(
            session_id=session_id,
            session=session,
            combat=combat,
            actor_name=actor_name,
            is_enemy=is_enemy,
            enemy=enemy,
            character=character,
            enemies=enemies,
        )
        confusion_end_save = _first_tick_log_result(tick_logs, "confusion_end_save")
        condition_end_saves = _tick_log_results(tick_logs, "condition_end_save")
        for log in tick_logs:
            db.add(log)
        advance_result = await advance_ai_turn(combat, session, db, turn_order, next_index)
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
            "confusion_end_save": confusion_end_save,
            "condition_end_saves": condition_end_saves,
            "tactical_decision": tactical_decision,
            **advance_result,
        }

    if decided_action == "dash":
        dash_ts = _get_ts(combat, actor_id)
        dash_ts["action_used"] = True
        if decided_target_id:
            dash_tgt_pos = positions.get(str(decided_target_id))
            actor_conditions = (
                enemy.get("conditions", [])
                if is_enemy and enemy
                else getattr(character, "conditions", None) or []
            )
            try:
                stand_result = apply_stand_up_from_prone(
                    dash_ts,
                    actor_conditions,
                )
            except MovementRuleError:
                stand_result = None
            if stand_result:
                dash_ts = stand_result.turn_state
                if stand_result.stood_up:
                    if is_enemy and enemy:
                        enemy["conditions"] = stand_result.conditions
                    elif character:
                        character.conditions = stand_result.conditions
            dash_budget = (
                (dash_ts["movement_max"] - dash_ts["movement_used"]) + dash_ts["movement_max"]
                if stand_result is not None
                else 0
            )
            movement_conditions = stand_result.conditions if stand_result else actor_conditions
            actor_pos = positions.get(str(actor_id))
            desired_distance = (
                max(
                    abs(actor_pos["x"] - dash_tgt_pos["x"]),
                    abs(actor_pos["y"] - dash_tgt_pos["y"]),
                )
                if actor_pos and dash_tgt_pos
                else 0
            )
            try:
                validate_displacement_allowed(movement_conditions, desired_distance)
                dash_result = _ai_move_toward(actor_pos, dash_tgt_pos, dash_budget, positions, actor_id)
            except MovementRuleError:
                dash_result = None
            if dash_result:
                actor_condition_durations = (
                    dict(enemy.get("condition_durations", {}) or {})
                    if is_enemy and enemy
                    else dict(getattr(character, "condition_durations", None) or {})
                )
                try:
                    validate_frightened_movement(
                        movement_conditions,
                        actor_condition_durations,
                        actor_pos,
                        {"x": dash_result["x"], "y": dash_result["y"]},
                        positions,
                    )
                except MovementRuleError:
                    dash_result = None
            if dash_result:
                positions[str(actor_id)] = {"x": dash_result["x"], "y": dash_result["y"]}
                combat.entity_positions = positions
                dash_ts["movement_used"] += dash_result["steps"]
        _save_ts(combat, actor_id, dash_ts)
        tick_logs = tick_ai_actor_conditions(
            session_id=session_id,
            session=session,
            combat=combat,
            actor_name=actor_name,
            is_enemy=is_enemy,
            enemy=enemy,
            character=character,
            enemies=enemies,
        )
        confusion_end_save = _first_tick_log_result(tick_logs, "confusion_end_save")
        condition_end_saves = _tick_log_results(tick_logs, "condition_end_save")
        for log in tick_logs:
            db.add(log)
        advance_result = await advance_ai_turn(combat, session, db, turn_order, next_index)
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
            "confusion_end_save": confusion_end_save,
            "condition_end_saves": condition_end_saves,
            "tactical_decision": tactical_decision,
            **advance_result,
        }

    if decided_action == "disengage":
        ts_dis = _get_ts(combat, actor_id)
        ts_dis["action_used"] = True
        ts_dis["disengaged"] = True
        _save_ts(combat, actor_id, ts_dis)
        tick_logs = tick_ai_actor_conditions(
            session_id=session_id,
            session=session,
            combat=combat,
            actor_name=actor_name,
            is_enemy=is_enemy,
            enemy=enemy,
            character=character,
            enemies=enemies,
        )
        confusion_end_save = _first_tick_log_result(tick_logs, "confusion_end_save")
        condition_end_saves = _tick_log_results(tick_logs, "condition_end_save")
        for log in tick_logs:
            db.add(log)
        advance_result = await advance_ai_turn(combat, session, db, turn_order, next_index)
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
            "confusion_end_save": confusion_end_save,
            "condition_end_saves": condition_end_saves,
            "tactical_decision": tactical_decision,
            **advance_result,
        }

    return None


def _tick_log_results(tick_logs, result_type: str) -> list[dict]:
    return [
        log.dice_result for log in tick_logs
        if isinstance(getattr(log, "dice_result", None), dict)
        and log.dice_result.get("type") == result_type
    ]


def _first_tick_log_result(tick_logs, result_type: str) -> dict | None:
    return next(iter(_tick_log_results(tick_logs, result_type)), None)
