from typing import Any

from models import CombatState, GameLog, Session
from services.game_combat_action_context import (
    build_combat_parser_state,
    build_combat_update,
    build_player_parser_data,
    resolve_combat_end_state,
)
from services.game_combat_action_executor import (
    _apply_creative_damage,
    _execute_attack_action,
    _execute_creative_action,
    _execute_move_action,
    _find_closest_alive_enemy_id,
    choose_narration_action_type as _choose_narration_action_type,
    execute_parsed_combat_actions,
)


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
    from api.combat import _ai_move_toward, _check_attack_range, _chebyshev_dist, _get_ts, _save_ts
    from services.action_parser import parse_combat_action
    from services.combat_narrator import narrate_action
    from services.combat_service import CombatService

    combat_service = CombatService()
    positions = dict(combat_state.entity_positions or {})
    state = session.game_state or {}
    enemies = list(state.get("enemies", []))
    player_derived = player.derived or {}
    player_id = str(player.id)

    turn_state = _get_ts(combat_state, player_id)
    move_remaining = turn_state["movement_max"] - turn_state["movement_used"]

    parsed = await parse_combat_action(
        player_input=action_text,
        game_state=build_combat_parser_state(characters=characters, enemies=enemies),
        player_id=player_id,
        player_data=build_player_parser_data(player=player),
        positions=positions,
        move_remaining=move_remaining,
    )

    execution = execute_parsed_combat_actions(
        parsed_actions=parsed["actions"],
        session=session,
        combat_state=combat_state,
        positions=positions,
        state=state,
        enemies=enemies,
        player=player,
        player_id=player_id,
        player_derived=player_derived,
        turn_state=turn_state,
        move_remaining=move_remaining,
        combat_service=combat_service,
        move_toward=_ai_move_toward,
        save_turn_state=_save_ts,
        check_attack_range=_check_attack_range,
        distance=_chebyshev_dist,
    )

    mechanical_summary = " | ".join(execution.action_results) if execution.action_results else "未执行有效行动"
    narration_action_type = _choose_narration_action_type(
        executed_action_types=execution.executed_action_types,
        parsed_actions=parsed["actions"],
    )
    if execution.errors:
        narrative = mechanical_summary
    else:
        narrative = await narrate_action(
            actor_name=player.name,
            actor_class=player.char_class,
            target_name="",
            action_type=narration_action_type,
            extra_details=f"玩家行动: {action_text}\n结果: {mechanical_summary}",
            damage=execution.total_damage,
        )
        if not narrative:
            narrative = mechanical_summary

    combat_over, outcome = resolve_combat_end_state(session=session, enemies=enemies)

    db.add(GameLog(
        session_id=session.id,
        role="dm",
        content=narrative,
        log_type="combat",
        dice_result=execution.dice_display if execution.dice_display else None,
    ))
    combat_update = build_combat_update(combat_state)

    await db.commit()
    return {
        "type": "combat_action",
        "narrative": narrative,
        "companion_reactions": "",
        "dice_display": execution.dice_display,
        "player_choices": [],
        "needs_check": {"required": False},
        "combat_triggered": False,
        "combat_ended": combat_over,
        "combat_end_result": outcome,
        "combat_update": combat_update,
        "action_results": execution.action_results,
        "errors": execution.errors,
        "hazard_results": execution.hazard_results,
    }


__all__ = [
    "execute_natural_language_combat_action",
    "_apply_creative_damage",
    "_choose_narration_action_type",
    "_execute_attack_action",
    "_execute_creative_action",
    "_execute_move_action",
    "_find_closest_alive_enemy_id",
]
