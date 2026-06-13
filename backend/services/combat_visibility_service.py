from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from services.dnd_rules import normalize_condition, normalize_conditions


HIDDEN_TARGET_ERROR = "目标仍处于隐藏状态，不能直接指定攻击"


def is_hidden_target(conditions: list[str] | tuple[str, ...] | set[str] | None) -> bool:
    """Return true when a target is hidden enough that direct targeting is not trusted."""
    return "hidden" in normalize_conditions(conditions)


def hidden_target_blocked_reason(conditions: list[str] | tuple[str, ...] | set[str] | None) -> str | None:
    if is_hidden_target(conditions):
        return HIDDEN_TARGET_ERROR
    return None


def reveal_hidden_character(character: Any) -> bool:
    """Remove hidden from a character after it gives away its position by attacking."""
    if character is None:
        return False

    old_conditions = list(getattr(character, "conditions", None) or [])
    new_conditions = _without_hidden(old_conditions)
    if len(new_conditions) == len(old_conditions):
        return False

    character.conditions = new_conditions
    durations = _durations_without_hidden(getattr(character, "condition_durations", None) or {})
    character.condition_durations = durations
    return True


def reveal_hidden_enemy(
    *,
    enemy_id: str,
    enemies: list[dict[str, Any]],
    session=None,
) -> bool:
    enemy = next((item for item in enemies if str(item.get("id")) == str(enemy_id)), None)
    if not enemy:
        return False

    old_conditions = list(enemy.get("conditions") or [])
    new_conditions = _without_hidden(old_conditions)
    if len(new_conditions) == len(old_conditions):
        return False

    enemy["conditions"] = new_conditions
    enemy["condition_durations"] = _durations_without_hidden(enemy.get("condition_durations") or {})
    if session is not None:
        state = dict(getattr(session, "game_state", None) or {})
        state["enemies"] = enemies
        session.game_state = state
        try:
            flag_modified(session, "game_state")
        except Exception:
            pass
    return True


def _without_hidden(conditions: list[Any]) -> list[Any]:
    return [
        condition
        for condition in conditions
        if normalize_condition(_condition_token(condition)) != "hidden"
    ]


def _durations_without_hidden(durations: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in dict(durations or {}).items()
        if normalize_condition(str(key)) != "hidden"
    }


def _condition_token(condition: Any) -> str:
    if isinstance(condition, str):
        return condition
    if isinstance(condition, dict):
        return str(
            condition.get("name")
            or condition.get("condition")
            or condition.get("type")
            or condition.get("id")
            or ""
        )
    return str(condition or "")
