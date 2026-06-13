from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from services.character_roster import CharacterRoster

CONDITION_SOURCES_KEY = "condition_sources"
CONCENTRATION_SOURCE_TYPE = "concentration"


def _target_id(target: Any) -> str | None:
    if isinstance(target, dict):
        value = target.get("id")
    else:
        value = getattr(target, "id", None)
    return str(value) if value is not None else None


def _target_name(target: Any) -> str | None:
    if isinstance(target, dict):
        return target.get("name") or target.get("target_name")
    return getattr(target, "name", None)


def _conditions(target: Any) -> list[str]:
    if isinstance(target, dict):
        return list(target.get("conditions") or [])
    return list(getattr(target, "conditions", None) or [])


def _set_conditions(target: Any, conditions: list[str]) -> None:
    if isinstance(target, dict):
        target["conditions"] = conditions
    else:
        target.conditions = conditions


def _durations(target: Any) -> dict[str, Any]:
    if isinstance(target, dict):
        return dict(target.get("condition_durations") or {})
    return dict(getattr(target, "condition_durations", None) or {})


def _set_durations(target: Any, durations: dict[str, Any]) -> None:
    if isinstance(target, dict):
        target["condition_durations"] = durations
    else:
        target.condition_durations = durations


def _source_map(target: Any) -> dict[str, list[dict[str, Any]]]:
    if isinstance(target, dict):
        raw = dict(target.get(CONDITION_SOURCES_KEY) or {})
    else:
        resources = dict(getattr(target, "class_resources", None) or {})
        raw = dict(resources.get(CONDITION_SOURCES_KEY) or {})

    normalized: dict[str, list[dict[str, Any]]] = {}
    for condition, records in raw.items():
        if isinstance(records, dict):
            records = [records]
        if not isinstance(records, list):
            continue
        clean_records = [dict(record) for record in records if isinstance(record, dict)]
        if clean_records:
            normalized[str(condition)] = clean_records
    return normalized


def _set_source_map(target: Any, sources: dict[str, list[dict[str, Any]]]) -> None:
    clean_sources = {condition: records for condition, records in sources.items() if records}
    if isinstance(target, dict):
        if clean_sources:
            target[CONDITION_SOURCES_KEY] = clean_sources
        else:
            target.pop(CONDITION_SOURCES_KEY, None)
        return

    resources = dict(getattr(target, "class_resources", None) or {})
    if clean_sources:
        resources[CONDITION_SOURCES_KEY] = clean_sources
    else:
        resources.pop(CONDITION_SOURCES_KEY, None)
    target.class_resources = resources


def _same_source(record: dict[str, Any], *, caster_id: str, spell_name: str | None) -> bool:
    if str(record.get("caster_id")) != str(caster_id):
        return False
    if record.get("source_type") != CONCENTRATION_SOURCE_TYPE:
        return False
    return spell_name is None or _spell_matches(record.get("spell_name"), spell_name)


def _normalized_spell(value: str | None) -> str:
    return str(value or "").strip().lower()


def _spell_matches(left: str | None, right: str | None) -> bool:
    left_key = _normalized_spell(left)
    right_key = _normalized_spell(right)
    return bool(left_key and right_key and left_key == right_key)


def track_concentration_condition(
    target: Any,
    condition: str,
    *,
    caster_id: str | None,
    spell_name: str | None,
    condition_preexisting: bool,
    previous_duration: Any = None,
    had_previous_duration: bool = False,
) -> None:
    """Remember that a concentration spell is responsible for a condition."""
    if not caster_id or not spell_name or not condition:
        return

    sources = _source_map(target)
    records = [
        record
        for record in sources.get(condition, [])
        if not _same_source(record, caster_id=str(caster_id), spell_name=spell_name)
    ]
    records.append({
        "source_type": CONCENTRATION_SOURCE_TYPE,
        "caster_id": str(caster_id),
        "spell_name": spell_name,
        "target_id": _target_id(target),
        "added_condition": not condition_preexisting,
        "had_previous_duration": had_previous_duration,
        "previous_duration": previous_duration,
    })
    sources[condition] = records
    _set_source_map(target, sources)


def clear_concentration_sources_from_target(
    target: Any,
    *,
    caster_id: str,
    spell_name: str | None = None,
) -> list[str]:
    """Clear conditions that were introduced by one caster's concentration."""
    sources = _source_map(target)
    if not sources:
        return []

    conditions = _conditions(target)
    durations = _durations(target)
    removed_conditions: list[str] = []
    changed = False

    for condition, records in list(sources.items()):
        matching = [
            record
            for record in records
            if _same_source(record, caster_id=str(caster_id), spell_name=spell_name)
        ]
        if not matching:
            continue

        remaining = [
            record
            for record in records
            if not _same_source(record, caster_id=str(caster_id), spell_name=spell_name)
        ]
        changed = True

        if remaining:
            if any(record.get("added_condition") for record in matching):
                remaining[0]["added_condition"] = True
                remaining[0]["had_previous_duration"] = matching[0].get("had_previous_duration", False)
                remaining[0]["previous_duration"] = matching[0].get("previous_duration")
            sources[condition] = remaining
            continue

        sources.pop(condition, None)
        if any(record.get("added_condition") for record in matching):
            conditions = [current for current in conditions if current != condition]
            durations.pop(condition, None)
            removed_conditions.append(condition)
            continue

        restore_record = next(
            (record for record in reversed(matching) if record.get("had_previous_duration")),
            None,
        )
        if restore_record:
            durations[condition] = restore_record.get("previous_duration")
        else:
            durations.pop(condition, None)

    if changed:
        _set_conditions(target, conditions)
        _set_durations(target, durations)
        _set_source_map(target, sources)
    return removed_conditions


def discard_condition_sources(target: Any, condition: str) -> None:
    """Remove source metadata when a condition is manually or temporally removed."""
    sources = _source_map(target)
    if not sources or condition not in sources:
        return
    sources.pop(condition, None)
    _set_source_map(target, sources)


def _concentration_effect_update(target: Any, removed_conditions: list[str], *, is_enemy: bool) -> dict[str, Any]:
    return {
        "target_id": _target_id(target),
        "target_name": _target_name(target),
        "is_enemy": is_enemy,
        "removed_conditions": removed_conditions,
        "conditions": _conditions(target),
        "condition_durations": _durations(target),
    }


async def _session_characters(db, session) -> list[Any]:
    if not hasattr(session, "is_multiplayer"):
        return []
    try:
        return await CharacterRoster(db, session).party()
    except Exception:
        return []


async def clear_concentration_effects_for_caster(
    db,
    session,
    caster_id: str | None,
    *,
    spell_name: str | None = None,
    characters: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Remove tracked concentration spell conditions for a caster across the session."""
    if not caster_id or session is None:
        return []

    removed: list[dict[str, Any]] = []
    state = dict(getattr(session, "game_state", None) or {})
    enemies = list(state.get("enemies") or [])
    enemies_changed = False

    for enemy in enemies:
        target_removed = clear_concentration_sources_from_target(
            enemy,
            caster_id=str(caster_id),
            spell_name=spell_name,
        )
        if target_removed:
            enemies_changed = True
            removed.append(_concentration_effect_update(enemy, target_removed, is_enemy=True))

    if enemies_changed:
        state["enemies"] = enemies
        session.game_state = dict(state)
        try:
            flag_modified(session, "game_state")
        except Exception:
            pass

    for character in characters if characters is not None else await _session_characters(db, session):
        target_removed = clear_concentration_sources_from_target(
            character,
            caster_id=str(caster_id),
            spell_name=spell_name,
        )
        if target_removed:
            removed.append(_concentration_effect_update(character, target_removed, is_enemy=False))

    return removed


async def set_concentration_with_cleanup(
    db,
    session,
    caster,
    spell_name: str,
    *,
    caster_id: str | None = None,
) -> list[dict[str, Any]]:
    """Replace a caster's concentration and clear effects from the previous spell."""
    resolved_caster_id = caster_id or _target_id(caster)
    previous_spell = (
        caster.get("concentration")
        if isinstance(caster, dict)
        else getattr(caster, "concentration", None)
    )
    removed = []
    if previous_spell:
        removed = await clear_concentration_effects_for_caster(
            db,
            session,
            resolved_caster_id,
            spell_name=previous_spell,
        )

    if isinstance(caster, dict):
        caster["concentration"] = spell_name
    else:
        caster.concentration = spell_name
    return removed
