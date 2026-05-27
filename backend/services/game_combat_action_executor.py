from dataclasses import dataclass
from typing import Any

from models import Session
from services.combat_action_rules_service import validate_can_take_action
from services.game_combat_action_steps import (
    execute_attack_action as _execute_attack_action,
    execute_move_action as _execute_move_action,
    find_closest_alive_enemy_id as _find_closest_alive_enemy_id,
)
from services.game_combat_creative_service import (
    apply_creative_damage as _apply_creative_damage,
    execute_creative_action as _execute_creative_action,
)


@dataclass
class ParsedCombatExecutionResult:
    action_results: list[str]
    dice_display: list[dict[str, Any]]
    total_damage: int
    executed_action_types: list[str]


def execute_parsed_combat_actions(
    *,
    parsed_actions: list[dict[str, Any]],
    session: Session,
    combat_state,
    positions: dict[str, Any],
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    player,
    player_id: str,
    player_derived: dict[str, Any],
    turn_state: dict[str, Any],
    move_remaining: int,
    combat_service,
    move_toward,
    save_turn_state,
    check_attack_range,
    distance,
) -> ParsedCombatExecutionResult:
    action_results: list[str] = []
    dice_display: list[dict[str, Any]] = []
    total_damage = 0
    action_used = False
    executed_action_types: list[str] = []

    for action in parsed_actions:
        action_type = action.get("type", "")

        if action_type == "move" and not action_used:
            move_remaining = _execute_move_action(
                combat_state=combat_state,
                positions=positions,
                player_id=player_id,
                turn_state=turn_state,
                move_remaining=move_remaining,
                action=action,
                actor_conditions=list(getattr(player, "conditions", None) or []),
                action_results=action_results,
                executed_action_types=executed_action_types,
                move_toward=move_toward,
                save_turn_state=save_turn_state,
            )

        elif action_type == "attack" and not action_used:
            validate_can_take_action(player)
            action_used = True
            damage_done = _execute_attack_action(
                session=session,
                combat_state=combat_state,
                positions=positions,
                state=state,
                enemies=enemies,
                player=player,
                player_id=player_id,
                player_derived=player_derived,
                player_conditions=list(getattr(player, "conditions", None) or []),
                player_concentration=getattr(player, "concentration", None),
                action=action,
                action_results=action_results,
                dice_display=dice_display,
                executed_action_types=executed_action_types,
                combat_service=combat_service,
                check_attack_range=check_attack_range,
                distance=distance,
            )
            total_damage += damage_done

        elif action_type == "creative" and not action_used:
            validate_can_take_action(player)
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
            validate_can_take_action(player)
            turn_state["dodging"] = True
            save_turn_state(combat_state, player_id, turn_state)
            action_results.append("采取闪避动作，攻击你的敌人获得劣势")
            executed_action_types.append("dodge")
            action_used = True

        elif action_type == "dash" and not action_used:
            validate_can_take_action(player)
            turn_state["movement_max"] = (
                turn_state["movement_max"]
                + turn_state.get("base_movement_max", turn_state["movement_max"])
            )
            save_turn_state(combat_state, player_id, turn_state)
            action_results.append("冲刺！移动力翻倍")
            executed_action_types.append("dash")
            action_used = True

        elif action_type == "disengage" and not action_used:
            validate_can_take_action(player)
            turn_state["disengaged"] = True
            save_turn_state(combat_state, player_id, turn_state)
            action_results.append("脱离接战，移动不触发借机攻击")
            executed_action_types.append("disengage")
            action_used = True

    if action_used:
        turn_state["action_used"] = True
        save_turn_state(combat_state, player_id, turn_state)

    return ParsedCombatExecutionResult(
        action_results=action_results,
        dice_display=dice_display,
        total_damage=total_damage,
        executed_action_types=executed_action_types,
    )


def choose_narration_action_type(
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
