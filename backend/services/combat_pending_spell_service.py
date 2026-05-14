from typing import Any
import uuid

from services.combat_turn_state_service import get_turn_state, save_turn_state


def build_pending_spell(
    *,
    caster_id: str,
    spell_name: str,
    spell_level: int,
    target_ids: list[str],
    is_cantrip: bool,
    is_aoe: bool,
    spell_type: str,
) -> dict[str, Any]:
    return {
        "pending_spell_id": str(uuid.uuid4()),
        "caster_id": caster_id,
        "spell_name": spell_name,
        "spell_level": spell_level,
        "target_ids": target_ids,
        "is_cantrip": is_cantrip,
        "is_aoe": is_aoe,
        "spell_type": spell_type,
    }


def find_pending_spell(turn_states: dict[str, Any], pending_spell_id: str):
    for entity_id, entity_turn_state in (turn_states or {}).items():
        pending_spell = entity_turn_state.get("pending_spell")
        if pending_spell and pending_spell.get("pending_spell_id") == pending_spell_id:
            return entity_id, pending_spell
    return None, None


def store_pending_spell(combat, caster_id: str, turn_state: dict[str, Any], pending_spell: dict[str, Any]) -> dict[str, Any]:
    turn_state["pending_spell"] = pending_spell
    save_turn_state(combat, caster_id, turn_state)
    return turn_state


def complete_pending_spell(combat, caster_entity_id: str, *, is_cantrip: bool) -> dict[str, Any]:
    turn_state = get_turn_state(combat, caster_entity_id)
    turn_state.pop("pending_spell", None)
    if not is_cantrip:
        turn_state["action_used"] = True
    save_turn_state(combat, caster_entity_id, turn_state)
    return turn_state
