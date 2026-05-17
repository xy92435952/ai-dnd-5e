from copy import deepcopy
from dataclasses import dataclass

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


def find_named_item(items: list, item_name: str, item_index: int) -> tuple[int, object] | None:
    matches = []
    for idx, item in enumerate(items):
        name = item.get("name") if isinstance(item, dict) else item
        if name == item_name:
            matches.append((idx, item))
    if not matches:
        return None
    safe_index = item_index if 0 <= item_index < len(matches) else 0
    return matches[safe_index]


def shop_item_data(item_name: str, item_category: str) -> dict | None:
    if item_category == "weapon":
        return WEAPONS.get(item_name)
    if item_category == "armor":
        return ARMOR.get(item_name)
    if item_category == "gear":
        return SHOP_GEAR.get(item_name)
    raise InventoryError(400, f"无效的物品类别：{item_category}")
