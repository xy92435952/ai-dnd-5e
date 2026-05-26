from typing import Any

from sqlalchemy.orm.attributes import flag_modified


DEFAULT_TURN_STATE: dict[str, Any] = {
    "action_used": False,
    "bonus_action_used": False,
    "reaction_used": False,
    "movement_used": 0,
    "movement_max": 6,
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
    save_turn_state(combat, entity_id, turn_state)
