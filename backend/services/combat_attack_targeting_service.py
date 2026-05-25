from dataclasses import dataclass
from typing import Any

from models import Character
from services.session_access_service import assert_character_in_session


@dataclass(frozen=True)
class AttackTarget:
    id: str
    name: str
    derived: dict[str, Any]
    is_enemy: bool


async def resolve_attack_target(
    db,
    target_id: str | None,
    enemies: list[dict[str, Any]],
    *,
    allow_auto_enemy: bool,
    session=None,
) -> AttackTarget | None:
    """Resolve a target id against characters, then enemies, with optional enemy fallback."""
    if target_id:
        target_character = await db.get(Character, target_id)
        if target_character:
            if session is not None:
                await assert_character_in_session(target_character, session, db)
            return AttackTarget(
                id=target_character.id,
                name=target_character.name,
                derived=target_character.derived or {},
                is_enemy=False,
            )

        enemy = next((item for item in enemies if item.get("id") == target_id), None)
        if enemy:
            return AttackTarget(
                id=enemy["id"],
                name=enemy.get("name", "敌人"),
                derived=enemy.get("derived", {}),
                is_enemy=True,
            )

    if allow_auto_enemy:
        alive = [enemy for enemy in enemies if enemy.get("hp_current", 0) > 0]
        if alive:
            enemy = alive[0]
            return AttackTarget(
                id=enemy["id"],
                name=enemy.get("name", "敌人"),
                derived=enemy.get("derived", {}),
                is_enemy=True,
            )

    return None


async def get_target_conditions(
    db,
    target: AttackTarget,
    enemies: list[dict[str, Any]],
) -> list[str]:
    """Return active conditions for a resolved target."""
    if target.is_enemy:
        enemy = next((item for item in enemies if item.get("id") == target.id), {})
        return list(enemy.get("conditions", []))

    target_character = await db.get(Character, target.id)
    return list(target_character.conditions or []) if target_character else []
