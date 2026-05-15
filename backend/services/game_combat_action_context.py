from typing import Any

from models import CombatState, Session


def build_combat_parser_state(
    *,
    characters: list[Any],
    enemies: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Build the compact battlefield state consumed by the combat action parser."""
    return {
        "characters": [
            {
                "id": character.id,
                "name": character.name,
                "hp_current": character.hp_current,
                "hp_max": (character.derived or {}).get("hp_max", character.hp_current),
                "is_player": character.is_player,
            }
            for character in characters
            if character.hp_current > 0
        ],
        "enemies": [
            {
                "id": enemy["id"],
                "name": enemy.get("name", "?"),
                "hp_current": enemy.get("hp_current", 0),
                "hp_max": enemy.get("hp_max", 0),
            }
            for enemy in enemies
            if enemy.get("hp_current", 0) > 0
        ],
    }


def build_player_parser_data(*, player, player_derived: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": player.name,
        "hp_current": player.hp_current,
        "hp_max": player_derived.get("hp_max", player.hp_current),
        "ac": player_derived.get("ac", 10),
    }


def resolve_combat_end_state(
    *,
    session: Session,
    enemies: list[dict[str, Any]],
) -> tuple[bool, str | None]:
    alive_enemies = [enemy for enemy in enemies if enemy.get("hp_current", 0) > 0]
    if alive_enemies:
        return False, None
    session.combat_active = False
    return True, "victory"


def build_combat_update(combat_state: CombatState) -> dict[str, Any]:
    return {
        "entity_positions": dict(combat_state.entity_positions or {}),
        "turn_states": dict(combat_state.turn_states or {}),
        "current_turn_index": combat_state.current_turn_index,
        "round_number": combat_state.round_number,
    }
