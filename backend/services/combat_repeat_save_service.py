from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from services.combat_concentration_effect_service import discard_condition_sources
from services.combat_tactical_service import get_cover_analysis
from services.bardic_inspiration_service import (
    apply_bardic_inspiration_to_saving_throw,
    spend_bardic_inspiration,
)
from services.dnd_character_rules import normalize_condition
from services.dnd_rules import roll_saving_throw


REPEAT_SAVE_CONDITIONS: dict[str, dict[str, Any]] = {
    "confused": {
        "save_ability": "wis",
        "timing": "end_of_turn",
        "spell_label": "Confusion",
        "handled_by_confusion_service": True,
    },
    "paralyzed": {
        "save_ability": "wis",
        "timing": "end_of_turn",
        "spell_label": "Hold Person",
    },
    "blinded": {
        "save_ability": "con",
        "timing": "end_of_turn",
        "spell_label": "Blindness/Deafness",
    },
    "slowed": {
        "save_ability": "wis",
        "timing": "end_of_turn",
        "spell_label": "Slow",
    },
    "frightened": {
        "save_ability": "wis",
        "timing": "end_of_turn",
        "spell_label": "Fear",
        "requires": "no_line_of_sight_to_source",
    },
}


def build_repeat_save_condition_metadata(
    condition_name: str,
    *,
    save_ability: str | None,
    spell_save_dc: int,
    caster_id: str | None,
    spell_name: str | None,
) -> dict[str, Any] | None:
    condition_key = normalize_condition(condition_name)
    config = REPEAT_SAVE_CONDITIONS.get(condition_key)
    if not config:
        return None

    metadata: dict[str, Any] = {
        "repeat_save": config.get("timing", "end_of_turn"),
        "save_ability": str(save_ability or config.get("save_ability") or "wis").lower(),
        "save_dc": _read_int(spell_save_dc, 13),
        "spell_name": spell_name or config.get("spell_label"),
    }
    if caster_id:
        metadata["caster_id"] = str(caster_id)
        metadata["source_id"] = str(caster_id)
        if condition_key == "frightened":
            metadata["frightened_source_id"] = str(caster_id)
    if config.get("requires"):
        metadata["repeat_save_requires"] = config["requires"]
    return metadata


def resolve_repeat_save_end_of_turn_saves(
    actor: dict | object | None,
    *,
    entity_id: str | None = None,
    actor_name: str | None = None,
    combat=None,
    d20_value: int | None = None,
    use_bardic_inspiration: bool = False,
    bardic_inspiration_roll: int | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not actor:
        return results

    bardic_spent = False
    for condition in list(_actor_conditions(actor)):
        condition_key = normalize_condition(condition)
        config = REPEAT_SAVE_CONDITIONS.get(condition_key)
        if not config or config.get("handled_by_confusion_service"):
            continue
        metadata = _repeat_save_metadata(actor, condition_key)
        if not _has_repeat_save_metadata(metadata):
            continue

        eligible, eligibility = _repeat_save_eligible(
            condition_key,
            metadata,
            combat=combat,
            entity_id=entity_id,
        )
        if not eligible:
            continue

        resolved_ability = str(
            metadata.get("save_ability") or config.get("save_ability") or "wis"
        ).strip().lower()
        resolved_dc = _read_int(metadata.get("save_dc", metadata.get("dc", 13)), 13)
        d20_override = d20_value if d20_value is not None else metadata.get("end_save_d20")
        save_detail = roll_saving_throw(
            _saving_throw_actor(actor),
            resolved_ability or "wis",
            resolved_dc,
            d20_roller=_fixed_d20_roller(d20_override),
        )
        if use_bardic_inspiration and not bardic_spent:
            bardic_inspiration = spend_bardic_inspiration(
                actor,
                bardic_roll=bardic_inspiration_roll,
                context="condition_end_save",
            )
            save_detail = apply_bardic_inspiration_to_saving_throw(
                save_detail,
                bardic_inspiration=bardic_inspiration,
                dc=resolved_dc,
            )
            bardic_spent = True
        ended = bool(save_detail.get("success"))
        if ended:
            _remove_condition(actor, condition_key)

        resolved_entity_id = str(entity_id) if entity_id is not None else _actor_id(actor)
        resolved_actor_name = actor_name or _actor_name(actor, resolved_entity_id or "actor")
        result = {
            "type": "condition_end_save",
            "condition": condition_key,
            "actor_id": resolved_entity_id,
            "actor_name": resolved_actor_name,
            "spell_name": metadata.get("spell_name") or config.get("spell_label"),
            "save": save_detail,
            "ended": ended,
            "removed_conditions": [condition_key] if ended else [],
            "conditions": _actor_conditions(actor),
            "condition_durations": _condition_durations(actor),
            "repeat_save": {
                "timing": config.get("timing", "end_of_turn"),
                **({"requires": config["requires"]} if config.get("requires") else {}),
                **({"eligibility": eligibility} if eligibility else {}),
            },
            "target_state": {
                "target_id": resolved_entity_id,
                "target_name": resolved_actor_name,
                "conditions": _actor_conditions(actor),
                "condition_durations": _condition_durations(actor),
                "save": save_detail,
            },
        }
        results.append(result)
    return results


def build_condition_end_save_log(actor_name: str, result: dict[str, Any] | None) -> str:
    if not result:
        return ""
    save = result.get("save") or {}
    total = save.get("total")
    dc = save.get("dc")
    ability = str(save.get("ability") or "").upper()
    spell_name = result.get("spell_name") or result.get("condition") or "condition"
    condition = result.get("condition") or "condition"
    outcome = "succeeds" if result.get("ended") else "fails"
    suffix = f"and is no longer {condition}" if result.get("ended") else f"and remains {condition}"
    return f"{actor_name} {outcome} the {spell_name} end-of-turn {ability} save ({total} vs DC {dc}) {suffix}."


def _repeat_save_metadata(actor: dict | object | None, condition_key: str) -> dict[str, Any]:
    durations = _condition_durations(actor)
    metadata: dict[str, Any] = {}
    for key, value in durations.items():
        if normalize_condition(str(key)) == condition_key and isinstance(value, dict):
            metadata.update(value)
            break

    prefix = condition_key.replace("-", "_").replace(" ", "_")
    for source_key, target_key in (
        (f"{prefix}_save_dc", "save_dc"),
        (f"{prefix}_save_ability", "save_ability"),
        (f"{prefix}_end_save_d20", "end_save_d20"),
        (f"{prefix}_repeat_save_d20", "end_save_d20"),
        (f"{prefix}_source_id", "source_id"),
        (f"{prefix}_source_position", "source_position"),
        ("repeat_save_d20", "end_save_d20"),
        ("repeat_save_eligible", "repeat_save_eligible"),
        ("source_visible", "source_visible"),
    ):
        if source_key in durations:
            metadata[target_key] = durations[source_key]
    return metadata


def _has_repeat_save_metadata(metadata: dict[str, Any]) -> bool:
    return (
        metadata.get("repeat_save") == "end_of_turn"
        or metadata.get("save_dc") is not None
        or metadata.get("dc") is not None
    )


def _repeat_save_eligible(
    condition_key: str,
    metadata: dict[str, Any],
    *,
    combat=None,
    entity_id: str | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    config = REPEAT_SAVE_CONDITIONS.get(condition_key) or {}
    explicit = _read_bool(metadata.get("repeat_save_eligible"))
    if explicit is not None:
        return explicit, {"reason": "metadata_override", "eligible": explicit}

    requires = config.get("requires") or metadata.get("repeat_save_requires")
    if requires != "no_line_of_sight_to_source":
        return True, None

    source_visible = _read_bool(metadata.get("source_visible"))
    if source_visible is not None:
        return (not source_visible), {"reason": "source_visibility_metadata", "source_visible": source_visible}

    blocked = _source_line_of_sight_blocked(metadata, combat=combat, entity_id=entity_id)
    if blocked is None:
        return False, {"reason": "source_visibility_unknown", "eligible": False}
    return blocked, {"reason": "source_not_visible" if blocked else "source_visible", "eligible": blocked}


def _source_line_of_sight_blocked(
    metadata: dict[str, Any],
    *,
    combat=None,
    entity_id: str | None = None,
) -> bool | None:
    if combat is None:
        return None
    grid_data = dict(getattr(combat, "grid_data", None) or {})
    positions = dict(getattr(combat, "entity_positions", None) or {})
    if not grid_data or not positions:
        return None

    actor_position = _parse_position(positions.get(str(entity_id))) if entity_id is not None else None
    if not actor_position:
        return None

    sources = _source_positions(metadata, positions)
    if not sources:
        return None
    return any(bool(get_cover_analysis(grid_data, source, actor_position).get("blocks_target")) for source in sources)


def _source_positions(metadata: dict[str, Any], positions: dict[str, Any]) -> list[dict[str, int]]:
    raw_sources = [
        metadata.get("source_position"),
        metadata.get("sourcePosition"),
    ]
    source_ids = metadata.get("source_ids") or metadata.get("sourceIds")
    if not isinstance(source_ids, list):
        source_ids = [
            metadata.get("source_id"),
            metadata.get("sourceId"),
            metadata.get("caster_id"),
            metadata.get("casterId"),
            metadata.get("frightened_source_id"),
            metadata.get("frightenedSourceId"),
        ]
    for source_id in source_ids:
        if source_id is not None:
            raw_sources.append(positions.get(str(source_id)))

    sources: list[dict[str, int]] = []
    seen: set[tuple[int, int]] = set()
    for raw in raw_sources:
        parsed = _parse_position(raw)
        if not parsed:
            continue
        key = (parsed["x"], parsed["y"])
        if key in seen:
            continue
        seen.add(key)
        sources.append(parsed)
    return sources


def _parse_position(value: Any) -> dict[str, int] | None:
    if isinstance(value, dict):
        try:
            return {"x": int(value["x"]), "y": int(value["y"])}
        except (KeyError, TypeError, ValueError):
            return None
    if isinstance(value, str) and "_" in value:
        x, y = value.split("_", 1)
        try:
            return {"x": int(x), "y": int(y)}
        except ValueError:
            return None
    return None


def _actor_conditions(actor: dict | object | None) -> list[str]:
    if not actor:
        return []
    if isinstance(actor, dict):
        return list(actor.get("conditions") or [])
    return list(getattr(actor, "conditions", None) or [])


def _condition_durations(actor: dict | object | None) -> dict[str, Any]:
    if not actor:
        return {}
    if isinstance(actor, dict):
        return dict(actor.get("condition_durations") or {})
    return dict(getattr(actor, "condition_durations", None) or {})


def _set_actor_conditions(actor: dict | object | None, conditions: list[str]) -> None:
    if not actor:
        return
    if isinstance(actor, dict):
        actor["conditions"] = conditions
        return
    actor.conditions = conditions
    _flag_modified(actor, "conditions")


def _set_condition_durations(actor: dict | object | None, durations: dict[str, Any]) -> None:
    if not actor:
        return
    if isinstance(actor, dict):
        actor["condition_durations"] = durations
        return
    actor.condition_durations = durations
    _flag_modified(actor, "condition_durations")


def _saving_throw_actor(actor: dict | object | None) -> dict[str, Any]:
    if isinstance(actor, dict):
        return dict(actor)
    return {
        "derived": dict(getattr(actor, "derived", None) or {}),
        "ability_scores": dict(getattr(actor, "ability_scores", None) or {}),
        "conditions": list(getattr(actor, "conditions", None) or []),
        "condition_durations": dict(getattr(actor, "condition_durations", None) or {}),
    }


def _remove_condition(actor: dict | object | None, condition_key: str) -> None:
    conditions = [
        condition for condition in _actor_conditions(actor)
        if normalize_condition(condition) != condition_key
    ]
    durations = _condition_durations(actor)
    for key in list(durations.keys()):
        normalized = normalize_condition(str(key))
        if normalized == condition_key or _is_condition_metadata_key(str(key), condition_key):
            durations.pop(key, None)
    _set_actor_conditions(actor, conditions)
    _set_condition_durations(actor, durations)
    discard_condition_sources(actor, condition_key)


def _is_condition_metadata_key(key: str, condition_key: str) -> bool:
    prefix = condition_key.replace("-", "_").replace(" ", "_")
    return key in {
        f"{prefix}_save_dc",
        f"{prefix}_save_ability",
        f"{prefix}_end_save_d20",
        f"{prefix}_repeat_save_d20",
        f"{prefix}_source_id",
        f"{prefix}_source_position",
        f"{prefix}_source",
        "repeat_save_d20",
        "repeat_save_eligible",
        "source_visible",
    }


def _actor_id(actor: dict | object | None) -> str:
    if isinstance(actor, dict):
        return str(actor.get("id") or "")
    return str(getattr(actor, "id", "") or "")


def _actor_name(actor: dict | object | None, fallback: str) -> str:
    if isinstance(actor, dict):
        return str(actor.get("name") or fallback)
    return str(getattr(actor, "name", None) or fallback)


def _fixed_d20_roller(value: Any):
    if value is None:
        return None
    try:
        d20 = min(20, max(1, int(value)))
    except (TypeError, ValueError):
        return None

    def roller(_dice: str) -> dict[str, Any]:
        return {"rolls": [d20], "total": d20}

    return roller


def _read_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return None


def _flag_modified(model: Any, key: str) -> None:
    try:
        flag_modified(model, key)
    except Exception:
        pass
