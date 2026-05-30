"""Location-aware shop pricing helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from services.dnd_rules import ARMOR, SHOP_GEAR, WEAPONS


DEFAULT_PRICING = {
    "profile": "standard",
    "label": "标准价格",
    "stock_profile": "full",
    "buy_multiplier": 1.0,
    "sell_rate": 0.5,
    "location_id": None,
    "location_name": None,
}

PRICE_PROFILES = [
    {
        "profile": "market",
        "label": "市集价格",
        "stock_profile": "full",
        "keywords": {
            "market", "bazaar", "shop", "store", "town", "city", "village",
            "trading post", "merchant", "tavern", "inn", "市场", "集市", "商店",
            "城镇", "村庄", "酒馆", "旅店", "商人",
        },
        "buy_multiplier": 0.9,
        "sell_rate": 0.55,
    },
    {
        "profile": "scarce",
        "label": "补给稀缺",
        "stock_profile": "field",
        "keywords": {
            "dungeon", "cave", "mine", "ruin", "wilderness", "forest", "swamp",
            "camp", "outpost", "crypt", "地牢", "洞穴", "矿洞", "遗迹", "荒野",
            "森林", "沼泽", "营地", "前哨",
        },
        "buy_multiplier": 1.25,
        "sell_rate": 0.4,
    },
]

FIELD_STOCK = {
    "weapon": {"Club", "Dagger", "Quarterstaff", "Shortbow", "Light Crossbow"},
    "armor": {"Leather Armor", "Shield"},
    "gear": {
        "Arrows (20)",
        "Bolts (20)",
        "Healing Potion",
        "Healer's Kit",
        "Rations (1 day)",
        "Rope",
        "Torch",
    },
}


def build_shop_inventory(pricing: dict[str, Any] | None = None) -> dict[str, Any]:
    context = normalize_pricing(pricing)
    return {
        "pricing": context,
        "weapons": _price_category(WEAPONS, "weapon", context),
        "armor": _price_category(ARMOR, "armor", context),
        "gear": _price_category(SHOP_GEAR, "gear", context),
    }


def build_shop_pricing_context(game_state: dict[str, Any] | None) -> dict[str, Any]:
    state = game_state or {}
    location_id, location_name = _current_location(state)
    haystack = f"{location_id or ''} {location_name or ''}".lower()

    context = dict(DEFAULT_PRICING)
    context["location_id"] = location_id
    context["location_name"] = location_name

    for profile in PRICE_PROFILES:
        if any(keyword.lower() in haystack for keyword in profile["keywords"]):
            context.update({
                "profile": profile["profile"],
                "label": profile["label"],
                "stock_profile": profile["stock_profile"],
                "buy_multiplier": profile["buy_multiplier"],
                "sell_rate": profile["sell_rate"],
            })
            return context
    return context


def normalize_pricing(pricing: dict[str, Any] | None = None) -> dict[str, Any]:
    context = {**DEFAULT_PRICING, **(pricing or {})}
    context["buy_multiplier"] = _as_float(context.get("buy_multiplier"), 1.0)
    context["sell_rate"] = _as_float(context.get("sell_rate"), 0.5)
    return context


def priced_buy_cost(base_cost: Any, quantity: int = 1, pricing: dict[str, Any] | None = None) -> int | float:
    context = normalize_pricing(pricing)
    return _money(_as_float(base_cost, 0.0) * max(1, quantity) * context["buy_multiplier"])


def priced_sell_value(base_cost: Any, pricing: dict[str, Any] | None = None) -> int:
    context = normalize_pricing(pricing)
    return int(_as_float(base_cost, 0.0) * context["sell_rate"])


def is_item_in_stock(item_name: str, item_category: str, pricing: dict[str, Any] | None = None) -> bool:
    context = normalize_pricing(pricing)
    allowed = _stock_for_category(item_category, context)
    return allowed is None or item_name in allowed


def _price_category(
    source: dict[str, dict[str, Any]],
    category: str,
    pricing: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result = {}
    allowed_stock = _stock_for_category(category, pricing)
    for name, data in source.items():
        if allowed_stock is not None and name not in allowed_stock:
            continue
        entry = deepcopy(data)
        base_cost = entry.get("cost", 0)
        entry["category"] = category
        entry["base_cost"] = base_cost
        entry["cost"] = priced_buy_cost(base_cost, 1, pricing)
        entry["price_modifier"] = pricing["buy_multiplier"]
        entry["sell_rate"] = pricing["sell_rate"]
        result[name] = entry
    return result


def _stock_for_category(category: str, pricing: dict[str, Any]) -> set[str] | None:
    if pricing.get("stock_profile") == "field":
        return FIELD_STOCK.get(category, set())
    return None


def _current_location(state: dict[str, Any]) -> tuple[str | None, str | None]:
    graph = state.get("location_graph") if isinstance(state.get("location_graph"), dict) else {}
    current_id = graph.get("current_location_id")
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    for node in nodes:
        if isinstance(node, dict) and node.get("id") == current_id:
            return str(current_id or "") or None, str(node.get("name") or current_id or "") or None

    scene_vibe = state.get("scene_vibe") if isinstance(state.get("scene_vibe"), dict) else {}
    location = scene_vibe.get("location")
    if location:
        return str(current_id or "") or None, str(location)
    return str(current_id or "") or None, None


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _money(value: float) -> int | float:
    rounded = round(value + 1e-9, 2)
    return int(rounded) if rounded.is_integer() else rounded
