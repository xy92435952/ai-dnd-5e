from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from services.feat_effect_service import has_feat_effect


DEFAULT_TURN_STATE: dict[str, Any] = {
    "action_used": False,
    "bonus_action_used": False,
    "reaction_used": False,
    "movement_used": 0,
    "movement_max": 6,
    "base_movement_max": 6,
    "disengaged": False,
    "being_helped": False,
    "dodging": False,
    "attacks_made": 0,
    "attacks_max": 1,
}


def get_turn_state(combat, entity_id: str) -> dict[str, Any]:
    states = combat.turn_states or {}
    return dict(states.get(str(entity_id), DEFAULT_TURN_STATE))


def save_turn_state(combat, entity_id: str, turn_state: dict[str, Any]) -> None:
    states = dict(combat.turn_states or {})
    states[str(entity_id)] = turn_state
    combat.turn_states = states
    flag_modified(combat, "turn_states")


def record_mobile_opportunity_safe_target(
    turn_state: dict[str, Any],
    target_id: Any,
    *,
    attacker_derived: dict[str, Any] | None,
    is_ranged: bool,
) -> dict[str, Any]:
    if is_ranged or target_id is None:
        return turn_state
    if not has_feat_effect(attacker_derived, "Mobile", "mobile"):
        return turn_state

    target_key = str(target_id)
    safe_targets = [
        str(existing)
        for existing in (turn_state.get("mobile_opportunity_safe_targets") or [])
        if existing is not None
    ]
    if target_key not in safe_targets:
        safe_targets.append(target_key)
    turn_state["mobile_opportunity_safe_targets"] = safe_targets
    return turn_state


def mobile_blocks_opportunity_from(turn_state: dict[str, Any], attacker_id: Any) -> bool:
    if attacker_id is None:
        return False
    return str(attacker_id) in {
        str(existing)
        for existing in (turn_state.get("mobile_opportunity_safe_targets") or [])
        if existing is not None
    }


def reset_turn_state(
    combat,
    entity_id: str,
    *,
    attacks_max: int = 1,
    movement_max: int = 6,
) -> None:
    turn_state = dict(DEFAULT_TURN_STATE)
    turn_state["attacks_max"] = attacks_max
    turn_state["movement_max"] = movement_max
    turn_state["base_movement_max"] = movement_max
    save_turn_state(combat, entity_id, turn_state)
