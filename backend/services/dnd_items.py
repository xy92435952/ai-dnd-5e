"""Item display helpers for DnD gear tables."""

from services.dnd_data import ARMOR, GEAR_PACK_ZH, SHOP_GEAR, WEAPONS


def get_item_zh(name: str) -> str:
    """根据英文物品名获取中文名，优先查 WEAPONS/ARMOR/SHOP_GEAR 的 zh 字段，再查 GEAR_PACK_ZH"""
    for table in (WEAPONS, ARMOR, SHOP_GEAR):
        entry = table.get(name)
        if entry and "zh" in entry:
            return entry["zh"]
    return GEAR_PACK_ZH.get(name, name)
