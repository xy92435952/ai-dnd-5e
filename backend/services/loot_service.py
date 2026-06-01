"""Session loot pool helpers.

The first loot slice stores deterministic reward state inside
``Session.game_state``. Parsed module ``key_rewards`` and ``magic_items`` seed a
hidden pool until the adventure explicitly discovers them, while character
inventory remains the source of truth after an item is claimed.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Callable

from services.dnd_rules import ARMOR, SHOP_GEAR, WEAPONS, roll_dice
from services.inventory_models import copy_equipment, shop_item_data


LOOT_POOL_VERSION = 1
SUPPORTED_CLAIM_MODES = {"claim", "split_party", "party_stash", "roll_party"}
MODULE_LOOT_SOURCES = {"key_rewards", "magic_items"}

RARITY_VALUE_HINT_GP = {
    "common": 100,
    "uncommon": 500,
    "rare": 5_000,
    "very rare": 50_000,
    "very_rare": 50_000,
    "legendary": 250_000,
    "artifact": 500_000,
    "普通": 100,
    "非凡": 500,
    "稀有": 5_000,
    "珍稀": 50_000,
    "传说": 250_000,
}


class LootError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def build_loot_pool_from_module(parsed: dict[str, Any] | None) -> dict[str, Any]:
    parsed = parsed or {}
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for reward in _as_list(parsed.get("key_rewards")):
        item = _loot_item_from_reward(reward, len(items), parsed)
        if not item:
            continue
        key = _dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        items.append(item)

    magic_items = parsed.get("magic_items") if isinstance(parsed.get("magic_items"), list) else []
    for magic_item in magic_items:
        if not isinstance(magic_item, dict):
            continue
        item = _loot_item_from_magic_item(magic_item, len(items))
        if not item:
            continue
        key = _dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        items.append(item)

    return {
        "version": LOOT_POOL_VERSION,
        "items": items,
    }


def ensure_loot_state(
    game_state: dict[str, Any] | None,
    parsed: dict[str, Any] | None,
) -> dict[str, Any]:
    state = deepcopy(game_state or {})
    existing = state.get("loot_pool")
    generated = build_loot_pool_from_module(parsed)
    if not _is_valid_loot_pool(existing):
        state["loot_pool"] = generated
        return state

    state["loot_pool"] = _preserve_claims(existing, generated)
    return state


def discover_loot_item(
    game_state: dict[str, Any] | None,
    parsed: dict[str, Any] | None,
    *,
    loot_id: str,
) -> dict[str, Any]:
    state = ensure_loot_state(game_state, parsed)
    pool = state.get("loot_pool") or {"items": []}
    items = list(pool.get("items") or [])
    for item in items:
        if str(item.get("id")) != str(loot_id):
            continue
        if item.get("status") == "claimed":
            return state
        item["status"] = "available"
        item["discovered"] = True
        pool["items"] = items
        state["loot_pool"] = pool
        return state
    raise LootError(404, "Loot item not found")


def public_loot_pool(pool: dict[str, Any] | None) -> dict[str, Any]:
    if not _is_valid_loot_pool(pool):
        return {"version": LOOT_POOL_VERSION, "items": []}
    return {
        "version": pool.get("version", LOOT_POOL_VERSION),
        "items": [
            deepcopy(item)
            for item in list(pool.get("items") or [])
            if isinstance(item, dict) and is_public_loot_item(item)
        ],
    }


def is_public_loot_item(item: dict[str, Any]) -> bool:
    status = str(item.get("status") or "hidden")
    if status == "claimed":
        return True
    if status != "available":
        return False
    if item.get("discovered") or item.get("revealed") or item.get("public"):
        return True
    return str(item.get("source") or "") not in MODULE_LOOT_SOURCES


def claim_loot_item(
    game_state: dict[str, Any] | None,
    parsed: dict[str, Any] | None,
    *,
    loot_id: str,
    character_id: str,
    character_name: str,
    equipment: dict[str, Any] | None,
    claim_mode: str = "claim",
    split_targets: list[dict[str, Any]] | None = None,
    roll_dice_func: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state = ensure_loot_state(game_state, parsed)
    pool = state.get("loot_pool") or {"items": []}
    items = list(pool.get("items") or [])
    item = next((entry for entry in items if str(entry.get("id")) == str(loot_id)), None)
    if not item:
        raise LootError(404, "Loot item not found")
    if item.get("status") == "claimed":
        raise LootError(409, "Loot item already claimed")
    if not is_public_loot_item(item):
        raise LootError(404, "Loot item not found")

    if claim_mode not in SUPPORTED_CLAIM_MODES:
        raise LootError(400, "Unsupported loot claim mode")

    split_allocations: list[dict[str, Any]] = []
    roll_allocations: list[dict[str, Any]] = []
    equipment_updates: dict[str, dict[str, Any]] = {}
    if claim_mode == "split_party":
        if item.get("category") != "gold":
            raise LootError(400, "Only gold loot can be split")
        split_result = split_gold_loot(item, split_targets or [])
        equipment_updates = split_result["equipment_updates"]
        split_allocations = split_result["split_allocations"]
        updated_equipment = equipment_updates.get(character_id, copy_equipment(equipment))
    elif claim_mode == "party_stash":
        if item.get("category") == "gold":
            raise LootError(400, "Gold loot should be claimed or split")
        updated_equipment = copy_equipment(equipment)
    elif claim_mode == "roll_party":
        if item.get("category") == "gold":
            raise LootError(400, "Gold loot should be claimed or split")
        roll_result = roll_item_loot(
            item,
            split_targets or [],
            roll_dice_func=roll_dice_func,
        )
        equipment_updates = roll_result["equipment_updates"]
        roll_allocations = roll_result["roll_allocations"]
        winner = roll_result["winner"]
        character_id = winner["character_id"]
        character_name = winner["character_name"]
        updated_equipment = equipment_updates.get(character_id, copy_equipment(equipment))
    else:
        updated_equipment = grant_loot_to_equipment(equipment, item)

    for entry in items:
        if str(entry.get("id")) == str(loot_id):
            entry["status"] = "claimed"
            entry["claimed_by_character_id"] = character_id
            entry["claimed_by_name"] = character_name
            entry["claim_mode"] = claim_mode
            if split_allocations:
                entry["split_allocations"] = split_allocations
            if roll_allocations:
                entry["roll_allocations"] = roll_allocations
            if claim_mode == "party_stash":
                entry["shared_with_party"] = True

    pool["items"] = items
    state["loot_pool"] = pool
    return {
        "loot": item,
        "equipment": updated_equipment,
        "equipment_updates": equipment_updates,
        "split_allocations": split_allocations,
        "roll_allocations": roll_allocations,
        "game_state": state,
    }


def split_gold_loot(
    loot_item: dict[str, Any],
    split_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    targets = [
        target for target in split_targets
        if target.get("character_id")
    ]
    if not targets:
        raise LootError(400, "No party members available for split")
    amount = int(loot_item.get("amount", 0) or 0)
    share, remainder = divmod(amount, len(targets))
    equipment_updates: dict[str, dict[str, Any]] = {}
    split_allocations: list[dict[str, Any]] = []

    for index, target in enumerate(targets):
        character_id = str(target["character_id"])
        allocation = share + (1 if index < remainder else 0)
        updated = copy_equipment(target.get("equipment"))
        updated["gold"] = int(updated.get("gold", 0) or 0) + allocation
        equipment_updates[character_id] = updated
        split_allocations.append({
            "character_id": character_id,
            "character_name": target.get("character_name") or character_id,
            "amount": allocation,
        })

    return {
        "equipment_updates": equipment_updates,
        "split_allocations": split_allocations,
    }


def roll_item_loot(
    loot_item: dict[str, Any],
    split_targets: list[dict[str, Any]],
    *,
    roll_dice_func: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    targets = [
        target for target in split_targets
        if target.get("character_id")
    ]
    if not targets:
        raise LootError(400, "No party members available for loot roll")

    roller = roll_dice_func or roll_dice
    winner_index = 0
    winner_roll = -1
    roll_allocations: list[dict[str, Any]] = []

    for index, target in enumerate(targets):
        d20 = int((roller("1d20").get("rolls") or [0])[0] or 0)
        if d20 > winner_roll:
            winner_index = index
            winner_roll = d20
        roll_allocations.append({
            "character_id": str(target["character_id"]),
            "character_name": target.get("character_name") or str(target["character_id"]),
            "d20": d20,
            "winner": False,
        })

    roll_allocations[winner_index]["winner"] = True
    winner = roll_allocations[winner_index]
    winner_target = targets[winner_index]
    updated = grant_loot_to_equipment(winner_target.get("equipment"), loot_item)

    return {
        "equipment_updates": {
            winner["character_id"]: updated,
        },
        "roll_allocations": roll_allocations,
        "winner": winner,
    }


def grant_loot_to_equipment(equipment: dict[str, Any] | None, loot_item: dict[str, Any]) -> dict[str, Any]:
    updated = copy_equipment(equipment)
    category = loot_item.get("category")
    name = loot_item.get("name")

    if category == "gold":
        updated["gold"] = int(updated.get("gold", 0) or 0) + int(loot_item.get("amount", 0) or 0)
        return updated

    payload = _inventory_payload_for_loot(loot_item)
    if category == "weapon":
        updated["weapons"] = list(updated.get("weapons", [])) + [{**payload, "equipped": False}]
    elif category == "armor":
        updated["armor"] = list(updated.get("armor", [])) + [{**payload, "equipped": False}]
    elif category == "shield":
        if updated.get("shield"):
            updated["gear"] = list(updated.get("gear", [])) + [payload]
        else:
            updated["shield"] = {**payload, "equipped": False}
    else:
        updated["gear"] = list(updated.get("gear", [])) + [payload]

    if name and not payload.get("name"):
        updated["gear"] = list(updated.get("gear", [])) + [{"name": name}]
    return updated


def _loot_item_from_reward(
    reward: Any,
    index: int,
    parsed: dict[str, Any],
) -> dict[str, Any] | None:
    if isinstance(reward, dict):
        name = reward.get("name") or reward.get("item") or reward.get("reward")
        if not name:
            return None
        raw = reward
    else:
        name = str(reward or "").strip()
        if not name:
            return None
        raw = _find_magic_item(parsed, name) or {}

    gold_amount = _parse_gold_amount(name)
    if gold_amount is not None:
        return {
            "id": f"loot_gold_{index}",
            "name": f"{gold_amount} gp",
            "category": "gold",
            "amount": gold_amount,
            "status": "hidden",
            "discovered": False,
            "source": "key_rewards",
        }

    return _build_item_loot(
        name=str(name),
        raw=raw,
        index=index,
        source="key_rewards",
    )


def _loot_item_from_magic_item(raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    name = raw.get("name")
    if not name:
        return None
    return _build_item_loot(name=str(name), raw=raw, index=index, source="magic_items")


def _build_item_loot(
    *,
    name: str,
    raw: dict[str, Any],
    index: int,
    source: str,
) -> dict[str, Any]:
    category = _item_category(name, raw)
    item_data = _inventory_payload_for_name(name, category)
    cost = raw.get("cost", item_data.get("cost"))
    if cost is None:
        cost = _rarity_value_hint(raw.get("rarity"))
    return {
        "id": f"loot_{_slug(category)}_{_slug(name)}_{index}",
        "name": name,
        "category": category,
        "status": "hidden",
        "discovered": False,
        "source": source,
        "rarity": raw.get("rarity"),
        "description": raw.get("description") or item_data.get("description"),
        "cost": cost,
        "item": {**item_data, **{k: v for k, v in raw.items() if k not in {"type", "category"}}},
    }


def _inventory_payload_for_loot(loot_item: dict[str, Any]) -> dict[str, Any]:
    name = loot_item.get("name")
    category = loot_item.get("category")
    payload = _inventory_payload_for_name(name, category)
    payload.update(dict(loot_item.get("item") or {}))
    if name:
        payload.setdefault("name", name)
    payload.setdefault("name", name)
    if loot_item.get("rarity"):
        payload["rarity"] = loot_item["rarity"]
    if loot_item.get("description"):
        payload["description"] = loot_item["description"]
    if loot_item.get("cost") is not None:
        payload["cost"] = loot_item["cost"]
    return payload


def _inventory_payload_for_name(name: str | None, category: str | None) -> dict[str, Any]:
    if not name:
        return {}
    if category == "weapon":
        return {"name": name, **(WEAPONS.get(name) or {})}
    if category == "armor":
        return {"name": name, **(ARMOR.get(name) or {})}
    if category == "shield":
        return {"name": name, **(ARMOR.get("Shield") or {})}
    if category == "gear":
        return {"name": name, **(SHOP_GEAR.get(name) or shop_item_data(name, "gear") or {})}
    return {"name": name}


def _item_category(name: str, raw: dict[str, Any]) -> str:
    explicit = str(raw.get("category") or raw.get("item_category") or raw.get("type") or "").lower()
    if explicit in {"weapon", "weapons"}:
        return "weapon"
    if explicit in {"armor", "armour"}:
        return "armor"
    if explicit == "shield":
        return "shield"
    if name == "Shield":
        return "shield"
    if name in WEAPONS:
        return "weapon"
    if name in ARMOR:
        return "armor"
    return "gear"


def _preserve_claims(existing: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    existing_by_id = {
        str(item.get("id")): item
        for item in existing.get("items", [])
        if isinstance(item, dict) and item.get("id")
    }
    for item in generated.get("items", []):
        previous = existing_by_id.get(str(item.get("id")))
        if not previous:
            continue
        if previous.get("status") == "claimed":
            item["status"] = "claimed"
        elif is_public_loot_item(previous):
            item["status"] = "available"
            item["discovered"] = True
        for key in (
            "discovered",
            "discovered_at",
            "discovery_reason",
            "discovery_source",
            "revealed",
            "public",
            "claimed_by_character_id",
            "claimed_by_name",
            "claim_mode",
            "split_allocations",
            "roll_allocations",
            "shared_with_party",
        ):
            if key in previous:
                item[key] = previous[key]
    return generated


def _is_valid_loot_pool(pool: Any) -> bool:
    return isinstance(pool, dict) and isinstance(pool.get("items"), list)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _find_magic_item(parsed: dict[str, Any], name: str) -> dict[str, Any] | None:
    magic_items = parsed.get("magic_items") if isinstance(parsed.get("magic_items"), list) else []
    normalized = _normalize(name)
    for item in magic_items:
        if isinstance(item, dict) and _normalize(item.get("name")) == normalized:
            return item
    return None


def _parse_gold_amount(value: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:gp|gold|金币)", value, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _rarity_value_hint(rarity: Any) -> int | None:
    if rarity is None:
        return None
    key = re.sub(r"[\s-]+", " ", str(rarity).strip().lower()).replace(" ", "_")
    if key == "very_rare":
        return RARITY_VALUE_HINT_GP["very rare"]
    return RARITY_VALUE_HINT_GP.get(key) or RARITY_VALUE_HINT_GP.get(str(rarity).strip())


def _dedupe_key(item: dict[str, Any]) -> str:
    if item.get("category") == "gold":
        return f"gold:{item.get('amount')}"
    return f"{item.get('category')}:{_normalize(item.get('name'))}"


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _slug(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", str(value or "").lower()).strip("_") or "item"
