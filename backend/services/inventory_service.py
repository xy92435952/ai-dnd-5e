from copy import deepcopy
from dataclasses import dataclass
import math

from services.dnd_rules import ARMOR, SHOP_GEAR, WEAPONS


@dataclass
class InventoryError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass
class GearItemUse:
    equipment: dict
    gear: list
    item_index: int
    item_data: dict


def copy_equipment(equipment: dict | None) -> dict:
    return deepcopy(equipment or {})


def _find_named_item(items: list, item_name: str, item_index: int) -> tuple[int, object] | None:
    matches = []
    for idx, item in enumerate(items):
        name = item.get("name") if isinstance(item, dict) else item
        if name == item_name:
            matches.append((idx, item))
    if not matches:
        return None
    safe_index = item_index if 0 <= item_index < len(matches) else 0
    return matches[safe_index]


def _shop_item_data(item_name: str, item_category: str) -> dict | None:
    if item_category == "weapon":
        return WEAPONS.get(item_name)
    if item_category == "armor":
        return ARMOR.get(item_name)
    if item_category == "gear":
        return SHOP_GEAR.get(item_name)
    raise InventoryError(400, f"无效的物品类别：{item_category}")


def prepare_gear_item_use(equipment: dict | None, *, item_name: str) -> GearItemUse:
    updated = copy_equipment(equipment)
    gear = list(updated.get("gear", []))

    found_idx = None
    found_item = None
    for idx, item in enumerate(gear):
        name = item.get("name") if isinstance(item, dict) else item
        if name == item_name:
            found_idx = idx
            found_item = item
            break

    if found_idx is None:
        raise InventoryError(404, f"背包中未找到物品：{item_name}")

    if isinstance(found_item, dict):
        item_data = {**SHOP_GEAR.get(item_name, {}), **found_item}
    else:
        item_data = {"name": item_name, **SHOP_GEAR.get(item_name, {})}

    return GearItemUse(
        equipment=updated,
        gear=gear,
        item_index=found_idx,
        item_data=item_data,
    )


def consume_gear_item_use(prepared: GearItemUse) -> dict:
    uses = prepared.item_data.get("uses")
    result = {}

    if uses is not None and uses > 1:
        if isinstance(prepared.gear[prepared.item_index], dict):
            prepared.gear[prepared.item_index]["uses"] = uses - 1
            result["uses_remaining"] = uses - 1
        else:
            prepared.gear.pop(prepared.item_index)
    else:
        prepared.gear.pop(prepared.item_index)

    prepared.equipment["gear"] = prepared.gear
    result["equipment"] = prepared.equipment
    return result


def buy_item(equipment: dict | None, *, item_name: str, item_category: str, quantity: int = 1) -> dict:
    if quantity <= 0:
        raise InventoryError(400, "购买数量必须大于 0")

    item_data = _shop_item_data(item_name, item_category)
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


def update_gold(equipment: dict | None, *, amount: int, reason: str = "") -> dict:
    updated = copy_equipment(equipment)
    current_gold = updated.get("gold", 0)
    new_gold = current_gold + amount
    if new_gold < 0:
        raise InventoryError(400, f"金币不足：当前 {current_gold}，需要 {abs(amount)}")

    updated["gold"] = new_gold
    return {
        "gold": new_gold,
        "change": amount,
        "reason": reason,
        "equipment": updated,
    }


def update_ammo(equipment: dict | None, *, weapon_name: str, change: int = -1) -> dict:
    updated = copy_equipment(equipment)
    weapons = list(updated.get("weapons", []))

    new_ammo = None
    for weapon in weapons:
        if weapon.get("name") == weapon_name:
            current_ammo = weapon.get("ammo", 20)
            new_ammo = max(0, current_ammo + change)
            weapon["ammo"] = new_ammo
            break

    if new_ammo is None:
        raise InventoryError(404, f"未找到武器：{weapon_name}")

    updated["weapons"] = weapons
    return {
        "weapon": weapon_name,
        "ammo": new_ammo,
        "change": change,
        "equipment": updated,
    }


def update_equipment(
    equipment: dict | None,
    *,
    item_name: str,
    item_category: str,
    equip: bool = True,
) -> dict:
    updated = copy_equipment(equipment)

    if item_category == "weapon":
        weapons = list(updated.get("weapons", []))
        found = False
        for weapon in weapons:
            if weapon.get("name") == item_name:
                weapon["equipped"] = equip
                found = True
                break
        if not found:
            raise InventoryError(404, f"背包中未找到武器：{item_name}")
        updated["weapons"] = weapons

    elif item_category == "armor":
        armor_list = list(updated.get("armor", []))
        found = False
        for armor in armor_list:
            if armor.get("name") == item_name:
                if equip:
                    for other in armor_list:
                        other["equipped"] = False
                armor["equipped"] = equip
                found = True
                break
        if not found:
            raise InventoryError(404, f"背包中未找到护甲：{item_name}")
        updated["armor"] = armor_list

    elif item_category == "shield":
        shield = updated.get("shield")
        if not shield:
            raise InventoryError(404, "背包中没有盾牌")
        shield["equipped"] = equip
        updated["shield"] = shield

    else:
        raise InventoryError(400, f"无效的物品类别：{item_category}")

    return {"equipment": updated}


def sell_item(equipment: dict | None, *, item_name: str, item_category: str, item_index: int = 0) -> dict:
    updated = copy_equipment(equipment)
    sell_price = 0
    removed_name = item_name

    if item_category == "weapon":
        weapons = list(updated.get("weapons", []))
        found = _find_named_item(weapons, item_name, item_index)
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
            found = _find_named_item(armor_list, item_name, item_index)
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
        found = _find_named_item(gear, item_name, item_index)
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
        found = _find_named_item(weapons, item_name, item_index)
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
        found = _find_named_item(armor_list, item_name, item_index)
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
        found = _find_named_item(gear, item_name, item_index)
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
