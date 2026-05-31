from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from models import Character, CombatState, Session
from services.combat_resistance_service import apply_character_damage_resistance
from services.combat_service import CombatService
from services.dnd_rules import apply_character_damage, roll_dice


DEFAULT_HAZARD_DAMAGE_DICE = "1d6"
DEFAULT_HAZARD_DAMAGE_TYPE = "environmental"


def resolve_movement_hazard(
    grid_data: dict | None,
    position: dict | None,
) -> dict[str, Any] | None:
    """Return rolled hazard damage for a grid cell, without mutating combat state."""
    cell = _cell_key(position)
    if not cell:
        return None

    grid = grid_data or {}
    metadata = _hazard_metadata_for_cell(grid, cell)
    if not metadata:
        return None

    damage_dice = str(metadata.get("damage_dice") or DEFAULT_HAZARD_DAMAGE_DICE)
    damage_type = str(
        metadata.get("damage_type")
        or _infer_damage_type(metadata.get("label"), metadata.get("description"))
        or DEFAULT_HAZARD_DAMAGE_TYPE
    )
    damage_roll = roll_dice(damage_dice)
    rolled_damage = max(0, int(damage_roll.get("total", 0) or 0))
    label = str(metadata.get("label") or metadata.get("name") or "Hazard")

    return {
        "triggered": True,
        "cell": cell,
        "position": dict(position or {}),
        "terrain": "hazard",
        "label": label[:120],
        "damage_dice": damage_dice,
        "damage_type": damage_type,
        "damage_roll": damage_roll,
        "rolled_damage": rolled_damage,
        "damage": rolled_damage,
        "final_damage": rolled_damage,
    }


def apply_movement_hazard_to_known_entity(
    *,
    session: Session | None,
    combat_state: CombatState,
    entity_id: str,
    position: dict | None,
    character: Character | None = None,
    combat_service: CombatService | None = None,
) -> dict[str, Any] | None:
    hazard = resolve_movement_hazard(getattr(combat_state, "grid_data", None) or {}, position)
    if not hazard:
        return None

    service = combat_service or CombatService()
    state = dict(session.game_state or {}) if session is not None else {}
    enemies = list(state.get("enemies") or [])
    enemy = _find_enemy(enemies, entity_id)
    if enemy is not None:
        applied = apply_hazard_damage_to_enemy(
            enemy,
            hazard,
            combat_service=service,
        )
        if session is not None:
            state["enemies"] = enemies
            session.game_state = state
            try:
                flag_modified(session, "game_state")
            except Exception:
                pass
        return applied

    if character is not None and str(getattr(character, "id", "")) == str(entity_id):
        return apply_hazard_damage_to_character(character, hazard)

    return {
        **hazard,
        "applied": False,
        "target_id": str(entity_id),
        "target_type": "unknown",
    }


async def apply_movement_hazard(
    *,
    db,
    session: Session,
    combat_state: CombatState,
    entity_id: str,
    position: dict | None,
    combat_service: CombatService | None = None,
) -> dict[str, Any] | None:
    character = await db.get(Character, entity_id)
    return apply_movement_hazard_to_known_entity(
        session=session,
        combat_state=combat_state,
        entity_id=str(entity_id),
        position=position,
        character=character,
        combat_service=combat_service,
    )


def apply_hazard_damage_to_enemy(
    enemy: dict[str, Any],
    hazard: dict[str, Any],
    *,
    combat_service: CombatService | None = None,
) -> dict[str, Any]:
    service = combat_service or CombatService()
    hp_before = max(0, int(enemy.get("hp_current", 0) or 0))
    rolled_damage = max(0, int(hazard.get("rolled_damage", hazard.get("damage", 0)) or 0))
    damage_type = str(hazard.get("damage_type") or DEFAULT_HAZARD_DAMAGE_TYPE)
    final_damage = service.apply_damage_with_resistance(
        rolled_damage,
        damage_type,
        enemy.get("resistances", []),
        enemy.get("immunities", []),
        enemy.get("vulnerabilities", []),
    )
    hp_max = _enemy_hp_max(enemy, hp_before)
    hp_after = service.apply_damage(hp_before, final_damage, hp_max)
    enemy["hp_current"] = hp_after
    if hp_after <= 0:
        enemy["dead"] = True

    return {
        **hazard,
        "applied": True,
        "target_id": str(enemy.get("id", "")),
        "target_name": enemy.get("name") or "Enemy",
        "target_type": "enemy",
        "hp_before": hp_before,
        "hp_after": hp_after,
        "damage": final_damage,
        "final_damage": final_damage,
        "resistance_applied": final_damage != rolled_damage,
        "dead": bool(enemy.get("dead")),
    }


def apply_hazard_damage_to_character(
    character: Character,
    hazard: dict[str, Any],
) -> dict[str, Any]:
    rolled_damage = max(0, int(hazard.get("rolled_damage", hazard.get("damage", 0)) or 0))
    damage_type = str(hazard.get("damage_type") or DEFAULT_HAZARD_DAMAGE_TYPE)
    final_damage, resisted = apply_character_damage_resistance(
        character,
        rolled_damage,
        damage_type,
    )
    damage_result = apply_character_damage(character, final_damage)

    return {
        **hazard,
        "applied": True,
        "target_id": str(character.id),
        "target_name": character.name,
        "target_type": "character",
        "hp_before": damage_result.get("hp_before"),
        "hp_after": damage_result.get("hp_after"),
        "temporary_hp_before": damage_result.get("temporary_hp_before"),
        "temporary_hp_after": damage_result.get("temporary_hp_after"),
        "wild_shape_hp_before": damage_result.get("wild_shape_hp_before"),
        "wild_shape_hp_after": damage_result.get("wild_shape_hp_after"),
        "death_saves": damage_result.get("death_saves"),
        "conditions": damage_result.get("conditions"),
        "damage": final_damage,
        "final_damage": final_damage,
        "resistance_applied": resisted,
        "dead": bool(damage_result.get("dead")),
    }


def hazard_result_to_dice_display(hazard: dict[str, Any] | None) -> dict[str, Any] | None:
    if not hazard:
        return None
    damage_roll = hazard.get("damage_roll") if isinstance(hazard.get("damage_roll"), dict) else {}
    return {
        "label": f"{hazard.get('label') or 'Hazard'} damage",
        "kind": "damage",
        "damage_type": hazard.get("damage_type"),
        "formula": hazard.get("damage_dice"),
        "rolls": damage_roll.get("rolls", []),
        "raw": hazard.get("rolled_damage", damage_roll.get("total", 0)),
        "total": hazard.get("final_damage", hazard.get("damage", 0)),
    }


def hazard_result_to_log_text(hazard: dict[str, Any] | None) -> str:
    if not hazard:
        return ""
    target = hazard.get("target_name") or hazard.get("target_id") or "A creature"
    label = hazard.get("label") or "hazard"
    damage = hazard.get("final_damage", hazard.get("damage", 0))
    damage_type = hazard.get("damage_type") or DEFAULT_HAZARD_DAMAGE_TYPE
    hp_before = hazard.get("hp_before")
    hp_after = hazard.get("hp_after")
    hp_text = f" HP {hp_before}->{hp_after}" if hp_before is not None and hp_after is not None else ""
    return f"{target} triggers {label}, taking {damage} {damage_type} damage.{hp_text}"


def _cell_key(position: dict | None) -> str | None:
    if not position:
        return None
    try:
        return f"{int(position.get('x'))}_{int(position.get('y'))}"
    except (TypeError, ValueError):
        return None


def _hazard_metadata_for_cell(grid_data: dict, cell: str) -> dict[str, Any] | None:
    cell_value = grid_data.get(cell)
    cell_metadata = _coerce_cell_hazard(cell_value)
    if cell_metadata is None:
        return None

    template_metadata = _template_hazard_metadata(grid_data)
    return {
        **template_metadata,
        **cell_metadata,
    }


def _coerce_cell_hazard(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        return {"terrain": "hazard"} if value.lower() == "hazard" else None
    if not isinstance(value, dict):
        return None

    kind = str(
        value.get("type")
        or value.get("kind")
        or value.get("terrain")
        or value.get("category")
        or ""
    ).lower()
    if kind == "hazard" or value.get("hazard") is True or value.get("damage_dice"):
        return dict(value)
    return None


def _template_hazard_metadata(grid_data: dict) -> dict[str, Any]:
    template = grid_data.get("_encounter_template")
    if not isinstance(template, dict):
        return {}

    hazards = [item for item in template.get("hazards") or [] if item]
    if not hazards:
        return {}

    first = hazards[0]
    if isinstance(first, dict):
        return {
            key: value
            for key, value in first.items()
            if key in {"label", "name", "description", "damage_dice", "damage_type"}
        }
    text = str(first)
    return {
        "label": text,
        "description": " ".join(str(item) for item in hazards[:3]),
    }


def _infer_damage_type(*texts: Any) -> str:
    text = " ".join(str(item or "") for item in texts).lower()
    if any(token in text for token in ("fire", "flame", "burn", "lava", "火", "焰")):
        return "fire"
    if any(token in text for token in ("lightning", "electric", "spark", "雷", "电")):
        return "lightning"
    if any(token in text for token in ("poison", "toxic", "venom", "毒")):
        return "poison"
    if any(token in text for token in ("acid", "corrosive", "酸")):
        return "acid"
    if any(token in text for token in ("ice", "cold", "frost", "冰", "寒")):
        return "cold"
    return ""


def _find_enemy(enemies: list[dict[str, Any]], entity_id: str) -> dict[str, Any] | None:
    for enemy in enemies:
        if str(enemy.get("id")) == str(entity_id):
            return enemy
    return None


def _enemy_hp_max(enemy: dict[str, Any], fallback: int) -> int:
    derived = enemy.get("derived") or {}
    for value in (derived.get("hp_max"), enemy.get("hp_max"), enemy.get("max_hp"), fallback):
        try:
            return max(1, int(value or 1))
        except (TypeError, ValueError):
            continue
    return max(1, fallback)
