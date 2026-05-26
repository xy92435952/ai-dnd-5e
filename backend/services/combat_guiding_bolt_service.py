from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from models import Character


async def consume_guiding_bolt_condition(
    db,
    *,
    target_id: str,
    target_is_enemy: bool,
    enemies: list[dict[str, Any]],
    session=None,
) -> bool:
    """Consume Guiding Bolt's one-shot advantage marker from the target."""
    if target_is_enemy:
        enemy = next((item for item in enemies if item.get("id") == target_id), None)
        if not enemy or "guiding_bolt" not in list(enemy.get("conditions", [])):
            return False
        enemy["conditions"] = [
            condition for condition in enemy.get("conditions", [])
            if condition != "guiding_bolt"
        ]
        durations = dict(enemy.get("condition_durations", {}))
        durations.pop("guiding_bolt", None)
        enemy["condition_durations"] = durations
        if session is not None:
            state = dict(getattr(session, "game_state", None) or {})
            state["enemies"] = enemies
            session.game_state = state
            try:
                flag_modified(session, "game_state")
            except Exception:
                pass
        return True

    target_character = await db.get(Character, target_id)
    if not target_character or "guiding_bolt" not in list(target_character.conditions or []):
        return False

    target_character.conditions = [
        condition for condition in (target_character.conditions or [])
        if condition != "guiding_bolt"
    ]
    durations = dict(target_character.condition_durations or {})
    durations.pop("guiding_bolt", None)
    target_character.condition_durations = durations
    return True
