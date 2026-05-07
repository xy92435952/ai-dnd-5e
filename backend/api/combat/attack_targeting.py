"""
api.combat.attack_targeting — shared target lookup helpers for attack endpoints.
"""
from dataclasses import dataclass
from typing import Any

from models import Character


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
) -> AttackTarget | None:
    """Resolve a target id against characters, then enemies, with optional enemy fallback."""
    if target_id:
        tchar = await db.get(Character, target_id)
        if tchar:
            return AttackTarget(
                id=tchar.id,
                name=tchar.name,
                derived=tchar.derived or {},
                is_enemy=False,
            )

        enemy = next((e for e in enemies if e.get("id") == target_id), None)
        if enemy:
            return AttackTarget(
                id=enemy["id"],
                name=enemy.get("name", "敌人"),
                derived=enemy.get("derived", {}),
                is_enemy=True,
            )

    if allow_auto_enemy:
        alive = [e for e in enemies if e.get("hp_current", 0) > 0]
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
        enemy = next((e for e in enemies if e.get("id") == target.id), {})
        return list(enemy.get("conditions", []))

    tchar = await db.get(Character, target.id)
    return list(tchar.conditions or []) if tchar else []
