from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from services.inventory_models import copy_equipment


THROWN_RECOVERY_POOL_KEY = "thrown_weapon_recovery_pool"
THROWN_RECOVERY_POOL_VERSION = 1


def is_recoverable_thrown_resource(resource: dict[str, Any] | None) -> bool:
    return bool(
        resource
        and resource.get("resource_type") == "thrown_weapon"
        and resource.get("consumed")
        and resource.get("recoverable")
    )


def record_recoverable_thrown_weapon(
    game_state: dict[str, Any] | None,
    *,
    character_id: str,
    character_name: str,
    weapon_resource: dict[str, Any] | None,
    source: str = "attack",
) -> dict[str, Any] | None:
    if not is_recoverable_thrown_resource(weapon_resource):
        return None

    item_snapshot = deepcopy(weapon_resource.get("recoverable_weapon") or {})
    weapon_name = weapon_resource.get("weapon") or item_snapshot.get("name")
    if not weapon_name:
        return None

    item_snapshot.setdefault("name", weapon_name)
    item_snapshot["quantity"] = _positive_int(item_snapshot.get("quantity"), 1)
    item_snapshot["equipped"] = False

    state = ensure_thrown_recovery_state(game_state)
    pool = state[THROWN_RECOVERY_POOL_KEY]
    items = list(pool.get("items") or [])
    items.append({
        "id": f"thrown_{uuid4().hex}",
        "status": "available",
        "character_id": str(character_id),
        "character_name": character_name or str(character_id),
        "weapon": weapon_name,
        "quantity": item_snapshot["quantity"],
        "item": item_snapshot,
        "source": source,
        "recovery_timing": weapon_resource.get("recovery_timing") or "after_combat_search",
        "public": True,
    })
    pool["items"] = items
    state[THROWN_RECOVERY_POOL_KEY] = pool
    return state


def recover_thrown_weapons(
    game_state: dict[str, Any] | None,
    *,
    character_id: str,
    character_name: str,
    equipment: dict[str, Any] | None,
) -> dict[str, Any]:
    state = ensure_thrown_recovery_state(game_state)
    pool = state[THROWN_RECOVERY_POOL_KEY]
    items = list(pool.get("items") or [])
    updated_equipment = copy_equipment(equipment)
    recovered: list[dict[str, Any]] = []

    for entry in items:
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "available":
            continue
        if str(entry.get("character_id")) != str(character_id):
            continue

        item = _recovery_item_snapshot(entry)
        quantity = _positive_int(entry.get("quantity") or item.get("quantity"), 1)
        item["quantity"] = quantity
        item["equipped"] = False
        updated_equipment = grant_recovered_thrown_weapon(updated_equipment, item)
        entry["status"] = "recovered"
        entry["recovered_by_character_id"] = str(character_id)
        entry["recovered_by_name"] = character_name or str(character_id)
        recovered.append({
            "id": entry.get("id"),
            "weapon": entry.get("weapon") or item.get("name"),
            "quantity": quantity,
            "item": deepcopy(item),
        })

    pool["items"] = items
    state[THROWN_RECOVERY_POOL_KEY] = pool
    return {
        "game_state": state,
        "equipment": updated_equipment,
        "recovered": recovered,
        "recovery_pool": public_thrown_recovery_pool(pool),
    }


def grant_recovered_thrown_weapon(
    equipment: dict[str, Any] | None,
    item: dict[str, Any],
) -> dict[str, Any]:
    updated = copy_equipment(equipment)
    weapon_name = item.get("name")
    if not weapon_name:
        return updated

    quantity = _positive_int(item.get("quantity"), 1)
    weapons = list(updated.get("weapons") or [])
    for index, weapon in enumerate(weapons):
        if not isinstance(weapon, dict) or weapon.get("name") != weapon_name:
            continue
        current_quantity = _positive_int(weapon.get("quantity"), 1)
        weapons[index] = {
            **weapon,
            "quantity": current_quantity + quantity,
        }
        updated["weapons"] = weapons
        return updated

    weapons.append({
        **deepcopy(item),
        "quantity": quantity,
        "equipped": False,
    })
    updated["weapons"] = weapons
    return updated


def ensure_thrown_recovery_state(game_state: dict[str, Any] | None) -> dict[str, Any]:
    state = deepcopy(game_state or {})
    pool = state.get(THROWN_RECOVERY_POOL_KEY)
    if not isinstance(pool, dict) or not isinstance(pool.get("items"), list):
        pool = {"version": THROWN_RECOVERY_POOL_VERSION, "items": []}
    else:
        pool = {
            "version": pool.get("version", THROWN_RECOVERY_POOL_VERSION),
            "items": list(pool.get("items") or []),
        }
    state[THROWN_RECOVERY_POOL_KEY] = pool
    return state


def public_thrown_recovery_pool(pool: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(pool, dict) or not isinstance(pool.get("items"), list):
        return {"version": THROWN_RECOVERY_POOL_VERSION, "items": []}
    return {
        "version": pool.get("version", THROWN_RECOVERY_POOL_VERSION),
        "items": [
            deepcopy(item)
            for item in pool.get("items") or []
            if isinstance(item, dict) and item.get("public") is not False
        ],
    }


def _recovery_item_snapshot(entry: dict[str, Any]) -> dict[str, Any]:
    item = deepcopy(entry.get("item") or {})
    weapon_name = entry.get("weapon") or item.get("name")
    if weapon_name:
        item.setdefault("name", weapon_name)
    return item


def _positive_int(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default
