from services.inventory_models import GearItemUse, InventoryError, copy_equipment
from services.dnd_rules import SHOP_GEAR


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
