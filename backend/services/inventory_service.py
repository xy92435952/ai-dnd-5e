"""Inventory service compatibility facade."""

from services.inventory_equipment_service import update_ammo, update_equipment, update_gold
from services.inventory_item_service import consume_gear_item_use, prepare_gear_item_use
from services.inventory_models import (
    GearItemUse,
    InventoryError,
    copy_equipment,
    find_named_item as _find_named_item,
    shop_item_data as _shop_item_data,
)
from services.inventory_trade_service import buy_item, sell_item, transfer_item


__all__ = [
    "GearItemUse",
    "InventoryError",
    "_find_named_item",
    "_shop_item_data",
    "buy_item",
    "consume_gear_item_use",
    "copy_equipment",
    "prepare_gear_item_use",
    "sell_item",
    "transfer_item",
    "update_ammo",
    "update_equipment",
    "update_gold",
]
