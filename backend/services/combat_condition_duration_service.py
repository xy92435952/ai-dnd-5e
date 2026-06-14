from typing import Any

from services.combat_concentration_effect_service import discard_condition_sources


def tick_character_conditions(char) -> list[str]:
    """Decrease active character condition durations and remove expired conditions."""
    durations = dict(char.condition_durations or {})
    conditions = list(char.conditions or [])
    removed = []

    active_conditions = set(conditions)
    for condition in list(durations.keys()):
        if condition not in active_conditions:
            continue
        remaining = _decrement_duration_value(durations[condition])
        if remaining is None:
            continue
        if _duration_expired(remaining):
            durations.pop(condition)
            _cleanup_duration_metadata(durations, condition)
            conditions = [current for current in conditions if current != condition]
            discard_condition_sources(char, condition)
            removed.append(condition)
        else:
            durations[condition] = remaining

    char.condition_durations = durations
    char.conditions = conditions
    return removed


def tick_enemy_conditions(enemy: dict[str, Any]) -> list[str]:
    """Decrease active enemy condition durations and remove expired conditions."""
    durations = dict(enemy.get("condition_durations", {}))
    conditions = list(enemy.get("conditions", []))
    removed = []

    active_conditions = set(conditions)
    for condition in list(durations.keys()):
        if condition not in active_conditions:
            continue
        remaining = _decrement_duration_value(durations[condition])
        if remaining is None:
            continue
        if _duration_expired(remaining):
            durations.pop(condition)
            _cleanup_duration_metadata(durations, condition)
            conditions = [current for current in conditions if current != condition]
            discard_condition_sources(enemy, condition)
            removed.append(condition)
        else:
            durations[condition] = remaining

    enemy["condition_durations"] = durations
    enemy["conditions"] = conditions
    return removed


def _decrement_duration_value(value: Any) -> Any | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value - 1
    if isinstance(value, float):
        return value - 1
    if isinstance(value, dict):
        for key in ("duration", "duration_rounds", "durationRounds", "rounds", "turns"):
            if key not in value or isinstance(value.get(key), bool):
                continue
            try:
                updated = dict(value)
                updated[key] = int(value[key]) - 1
                return updated
            except (TypeError, ValueError):
                continue
    return None


def _duration_expired(value: Any) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value <= 0
    if isinstance(value, dict):
        for key in ("duration", "duration_rounds", "durationRounds", "rounds", "turns"):
            if key not in value:
                continue
            try:
                return int(value[key]) <= 0
            except (TypeError, ValueError):
                return False
    return False


def _cleanup_duration_metadata(durations: dict[str, Any], condition: str) -> None:
    if condition != "confused":
        return
    for key in (
        "confusion_next_roll",
        "confusion_roll",
        "confusion_direction_index",
        "confusion_target_id",
        "confusion_target_index",
        "confusion_attack_d20",
        "confusion_save_dc",
        "confusion_save_ability",
        "confusion_end_save_d20",
    ):
        durations.pop(key, None)
