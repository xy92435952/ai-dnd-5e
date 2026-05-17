from services.inventory_models import InventoryError, copy_equipment


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
