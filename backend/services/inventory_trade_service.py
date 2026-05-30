import math

from services.dnd_rules import ARMOR, SHOP_GEAR, WEAPONS
from services.inventory_models import InventoryError, copy_equipment, find_named_item, shop_item_data
from services.shop_pricing_service import normalize_pricing, priced_buy_cost, priced_sell_value


AMMO_BUNDLES = {
    "Arrows (20)": {
        "amount": 20,
        "compatible_weapons": {"Longbow", "Shortbow"},
    },
    "Bolts (20)": {
        "amount": 20,
        "compatible_weapons": {"Light Crossbow", "Hand Crossbow", "Heavy Crossbow"},
    },
}


def buy_item(
    equipment: dict | None,
    *,
    item_name: str,
    item_category: str,
    quantity: int = 1,
    price_context: dict | None = None,
) -> dict:
    if quantity <= 0:
        raise InventoryError(400, "购买数量必须大于 0")

    item_data = shop_item_data(item_name, item_category)
    if not item_data:
        raise InventoryError(404, f"商店中未找到物品：{item_name}")

    updated = copy_equipment(equipment)
    pricing = normalize_pricing(price_context)
    base_cost = item_data.get("cost", 0)
    cost = priced_buy_cost(base_cost, quantity, pricing)
    current_gold = updated.get("gold", 0)
    if current_gold < cost:
        raise InventoryError(400, f"金币不足：当前 {current_gold} gp，需要 {cost} gp")

    updated["gold"] = current_gold - cost

    ammo_result = {}
    if item_category == "weapon":
        weapons = list(updated.get("weapons", []))
        for _ in range(quantity):
            weapons.append({**item_data, "name": item_name, "equipped": False})
        updated["weapons"] = weapons
    elif item_category == "armor":
        if item_name == "Shield":
            updated["shield"] = {"name": "Shield", "ac": 2, "equipped": False}
        else:
            armor_list = list(updated.get("armor", []))
            armor_list.append({**item_data, "name": item_name, "equipped": False})
            updated["armor"] = armor_list
    elif item_category == "gear":
        ammo_result = _apply_ammo_bundle_purchase(
            updated,
            item_name=item_name,
            quantity=quantity,
        )
        if not ammo_result:
            gear = list(updated.get("gear", []))
            for _ in range(quantity):
                gear.append({"name": item_name, **item_data})
            updated["gear"] = gear

    result = {
        "bought": item_name,
        "quantity": quantity,
        "cost": cost,
        "base_cost": base_cost,
        "price_modifier": pricing["buy_multiplier"],
        "pricing": pricing,
        "gold_remaining": updated["gold"],
        "equipment": updated,
    }
    if ammo_result:
        result["ammo_added"] = ammo_result
    return result


def sell_item(
    equipment: dict | None,
    *,
    item_name: str,
    item_category: str,
    item_index: int = 0,
    price_context: dict | None = None,
) -> dict:
    updated = copy_equipment(equipment)
    pricing = normalize_pricing(price_context)
    sell_price = 0
    removed_name = item_name

    if item_category == "weapon":
        weapons = list(updated.get("weapons", []))
        found = find_named_item(weapons, item_name, item_index)
        if not found:
            raise InventoryError(404, f"背包中未找到武器：{item_name}")
        actual_idx, item = found
        if isinstance(item, dict) and item.get("equipped"):
            raise InventoryError(400, "不能出售装备中的武器，请先卸下")
        sell_price = priced_sell_value(item.get("cost", WEAPONS.get(item_name, {}).get("cost", 0)), pricing)
        weapons.pop(actual_idx)
        updated["weapons"] = weapons

    elif item_category == "armor":
        if item_name == "Shield":
            shield = updated.get("shield")
            if not shield:
                raise InventoryError(404, "背包中没有盾牌")
            if isinstance(shield, dict) and shield.get("equipped"):
                raise InventoryError(400, "不能出售装备中的盾牌，请先卸下")
            sell_price = priced_sell_value(ARMOR.get("Shield", {}).get("cost", 10), pricing)
            updated["shield"] = None
        else:
            armor_list = list(updated.get("armor", []))
            found = find_named_item(armor_list, item_name, item_index)
            if not found:
                raise InventoryError(404, f"背包中未找到护甲：{item_name}")
            actual_idx, item = found
            if isinstance(item, dict) and item.get("equipped"):
                raise InventoryError(400, "不能出售装备中的护甲，请先卸下")
            sell_price = priced_sell_value(item.get("cost", ARMOR.get(item_name, {}).get("cost", 0)), pricing)
            armor_list.pop(actual_idx)
            updated["armor"] = armor_list

    elif item_category == "gear":
        gear = list(updated.get("gear", []))
        found = find_named_item(gear, item_name, item_index)
        if not found:
            raise InventoryError(404, f"背包中未找到物品：{item_name}")
        actual_idx, item = found
        item_cost = (
            item.get("cost", 0)
            if isinstance(item, dict)
            else SHOP_GEAR.get(item_name, {}).get("cost", 0)
        )
        sell_price = priced_sell_value(item_cost, pricing)
        gear.pop(actual_idx)
        updated["gear"] = gear

    else:
        raise InventoryError(400, f"无效的物品类别：{item_category}")

    updated["gold"] = updated.get("gold", 0) + math.floor(sell_price)
    return {
        "sold": removed_name,
        "sell_price": math.floor(sell_price),
        "sell_rate": pricing["sell_rate"],
        "pricing": pricing,
        "gold_remaining": updated["gold"],
        "equipment": updated,
    }


def transfer_item(
    source_equipment: dict | None,
    target_equipment: dict | None,
    *,
    item_name: str,
    item_category: str,
    item_index: int = 0,
) -> dict:
    source = copy_equipment(source_equipment)
    target = copy_equipment(target_equipment)
    moved_item = None

    if item_category == "weapon":
        weapons = list(source.get("weapons", []))
        found = find_named_item(weapons, item_name, item_index)
        if not found:
            raise InventoryError(404, f"背包中未找到武器：{item_name}")
        actual_idx, moved_item = found
        if isinstance(moved_item, dict) and moved_item.get("equipped"):
            raise InventoryError(400, "不能转交装备中的武器，请先卸下")
        weapons.pop(actual_idx)
        source["weapons"] = weapons
        target["weapons"] = list(target.get("weapons", [])) + [moved_item]

    elif item_category == "armor":
        armor_list = list(source.get("armor", []))
        found = find_named_item(armor_list, item_name, item_index)
        if not found:
            raise InventoryError(404, f"背包中未找到护甲：{item_name}")
        actual_idx, moved_item = found
        if isinstance(moved_item, dict) and moved_item.get("equipped"):
            raise InventoryError(400, "不能转交装备中的护甲，请先卸下")
        armor_list.pop(actual_idx)
        source["armor"] = armor_list
        target["armor"] = list(target.get("armor", [])) + [moved_item]

    elif item_category == "shield":
        shield = source.get("shield")
        if not shield:
            raise InventoryError(404, "背包中没有盾牌")
        if isinstance(shield, dict) and shield.get("equipped"):
            raise InventoryError(400, "不能转交装备中的盾牌，请先卸下")
        if target.get("shield"):
            raise InventoryError(400, "目标角色已经有盾牌")
        moved_item = shield
        source["shield"] = None
        target["shield"] = moved_item

    elif item_category == "gear":
        gear = list(source.get("gear", []))
        found = find_named_item(gear, item_name, item_index)
        if not found:
            raise InventoryError(404, f"背包中未找到物品：{item_name}")
        actual_idx, moved_item = found
        gear.pop(actual_idx)
        source["gear"] = gear
        target["gear"] = list(target.get("gear", [])) + [moved_item]

    else:
        raise InventoryError(400, f"无效的物品类别：{item_category}")

    moved_name = moved_item.get("name") if isinstance(moved_item, dict) else moved_item
    return {
        "transferred": moved_name,
        "source_equipment": source,
        "target_equipment": target,
    }


def _apply_ammo_bundle_purchase(equipment: dict, *, item_name: str, quantity: int) -> dict:
    bundle = AMMO_BUNDLES.get(item_name)
    if not bundle:
        return {}

    weapons = list(equipment.get("weapons", []))
    compatible_names = bundle["compatible_weapons"]
    candidates = [
        (index, weapon)
        for index, weapon in enumerate(weapons)
        if isinstance(weapon, dict) and weapon.get("name") in compatible_names
    ]
    if not candidates:
        return {}

    equipped = [candidate for candidate in candidates if candidate[1].get("equipped")]
    index, weapon = (equipped or candidates)[0]
    amount = int(bundle["amount"]) * quantity
    current_ammo = _as_int(weapon.get("ammo"), 0)
    next_ammo = current_ammo + amount
    weapons[index] = {**weapon, "ammo": next_ammo}
    equipment["weapons"] = weapons
    return {
        "bundle": item_name,
        "weapon": weapon.get("name"),
        "amount": amount,
        "ammo": next_ammo,
    }


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
