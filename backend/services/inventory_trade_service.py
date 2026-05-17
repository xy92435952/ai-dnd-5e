import math

from services.dnd_rules import ARMOR, SHOP_GEAR, WEAPONS
from services.inventory_models import InventoryError, copy_equipment, find_named_item, shop_item_data


def buy_item(equipment: dict | None, *, item_name: str, item_category: str, quantity: int = 1) -> dict:
    if quantity <= 0:
        raise InventoryError(400, "购买数量必须大于 0")

    item_data = shop_item_data(item_name, item_category)
    if not item_data:
        raise InventoryError(404, f"商店中未找到物品：{item_name}")

    updated = copy_equipment(equipment)
    cost = item_data.get("cost", 0) * quantity
    current_gold = updated.get("gold", 0)
    if current_gold < cost:
        raise InventoryError(400, f"金币不足：当前 {current_gold} gp，需要 {cost} gp")

    updated["gold"] = current_gold - cost

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
        gear = list(updated.get("gear", []))
        for _ in range(quantity):
            gear.append({"name": item_name, **item_data})
        updated["gear"] = gear

    return {
        "bought": item_name,
        "quantity": quantity,
        "cost": cost,
        "gold_remaining": updated["gold"],
        "equipment": updated,
    }


def sell_item(equipment: dict | None, *, item_name: str, item_category: str, item_index: int = 0) -> dict:
    updated = copy_equipment(equipment)
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
        sell_price = item.get("cost", WEAPONS.get(item_name, {}).get("cost", 0)) / 2
        weapons.pop(actual_idx)
        updated["weapons"] = weapons

    elif item_category == "armor":
        if item_name == "Shield":
            shield = updated.get("shield")
            if not shield:
                raise InventoryError(404, "背包中没有盾牌")
            if isinstance(shield, dict) and shield.get("equipped"):
                raise InventoryError(400, "不能出售装备中的盾牌，请先卸下")
            sell_price = ARMOR.get("Shield", {}).get("cost", 10) / 2
            updated["shield"] = None
        else:
            armor_list = list(updated.get("armor", []))
            found = find_named_item(armor_list, item_name, item_index)
            if not found:
                raise InventoryError(404, f"背包中未找到护甲：{item_name}")
            actual_idx, item = found
            if isinstance(item, dict) and item.get("equipped"):
                raise InventoryError(400, "不能出售装备中的护甲，请先卸下")
            sell_price = item.get("cost", ARMOR.get(item_name, {}).get("cost", 0)) / 2
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
        sell_price = item_cost / 2
        gear.pop(actual_idx)
        updated["gear"] = gear

    else:
        raise InventoryError(400, f"无效的物品类别：{item_category}")

    updated["gold"] = updated.get("gold", 0) + math.floor(sell_price)
    return {
        "sold": removed_name,
        "sell_price": math.floor(sell_price),
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
