"""Enemy defender interception rules."""

from __future__ import annotations

from typing import Any, Callable

from services.combat_action_rules_service import can_take_reaction
from services.combat_grid_service import chebyshev_distance
from services.combat_turn_state_service import get_turn_state, save_turn_state
from services.encounter_template_service import normalize_tactical_role


TurnStateGetter = Callable[[Any, str], dict[str, Any]]
TurnStateSaver = Callable[[Any, str, dict[str, Any]], None]


def apply_defender_interception(
    *,
    combat,
    attacker_id: str,
    target_id: str,
    enemies: list[dict[str, Any]],
    positions: dict[str, Any],
    get_turn_state_func: TurnStateGetter = get_turn_state,
    save_turn_state_func: TurnStateSaver = save_turn_state,
) -> dict[str, Any] | None:
    """Spend an adjacent enemy defender reaction to impose disadvantage on an attack."""
    defender = choose_defender_interceptor(
        attacker_id=attacker_id,
        target_id=target_id,
        enemies=enemies,
        positions=positions,
        get_turn_state_func=get_turn_state_func,
        combat=combat,
    )
    if not defender:
        return None

    defender_id = str(defender.get("id"))
    defender_ts = get_turn_state_func(combat, defender_id)
    interception = {
        "type": "defender_interception",
        "defender_id": defender_id,
        "defender_name": defender.get("name", "Defender"),
        "protected_target_id": str(target_id),
        "attacker_id": str(attacker_id),
        "effect": "disadvantage",
    }
    defender_ts["reaction_used"] = True
    defender_ts["defender_interception"] = interception
    save_turn_state_func(combat, defender_id, defender_ts)
    return interception


def choose_defender_interceptor(
    *,
    attacker_id: str,
    target_id: str,
    enemies: list[dict[str, Any]],
    positions: dict[str, Any],
    combat=None,
    get_turn_state_func: TurnStateGetter = get_turn_state,
) -> dict[str, Any] | None:
    target_pos = positions.get(str(target_id))
    if not target_pos:
        return None

    candidates = []
    for enemy in enemies:
        defender_id = str(enemy.get("id") or "")
        if not defender_id or defender_id == str(target_id):
            continue
        if defender_id == str(attacker_id):
            continue
        if int(enemy.get("hp_current", 0) or 0) <= 0:
            continue
        if normalize_tactical_role(enemy.get("tactical_role"), "striker") != "defender":
            continue
        if not can_take_reaction(enemy):
            continue

        turn_state = get_turn_state_func(combat, defender_id) if combat is not None else {}
        if turn_state.get("reaction_used"):
            continue

        defender_pos = positions.get(defender_id)
        if not defender_pos:
            continue
        target_distance = chebyshev_distance(defender_pos, target_pos)
        if target_distance > 1:
            continue
        candidates.append((
            target_distance,
            -int(enemy.get("hp_current", 0) or 0),
            defender_id,
            enemy,
        ))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[:3])
    return candidates[0][3]
