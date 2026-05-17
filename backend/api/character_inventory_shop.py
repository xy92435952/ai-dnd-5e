from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character
from services.inventory_service import (
    InventoryError,
    buy_item as buy_inventory_item,
    sell_item as sell_inventory_item,
    transfer_item as transfer_inventory_item,
)

from api.character_inventory_equipment import load_character_or_404, recalculate_character_derived


async def buy_character_item(
    *,
    db: AsyncSession,
    character_id: str,
    item_name: str,
    item_category: str,
    quantity: int,
) -> dict:
    char = await load_character_or_404(db, character_id)
    try:
        result = buy_inventory_item(
            char.equipment,
            item_name=item_name,
            item_category=item_category,
            quantity=quantity,
        )
    except InventoryError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    char.equipment = result["equipment"]
    await db.commit()
    return result


async def sell_character_item(
    *,
    db: AsyncSession,
    character_id: str,
    item_name: str,
    item_category: str,
    item_index: int,
) -> dict:
    char = await load_character_or_404(db, character_id)
    try:
        result = sell_inventory_item(
            char.equipment,
            item_name=item_name,
            item_category=item_category,
            item_index=item_index,
        )
    except InventoryError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    equipment = result["equipment"]
    char.equipment = equipment
    if item_category == "armor":
        recalculate_character_derived(char, equipment)

    await db.commit()
    return result


async def transfer_character_item(
    *,
    db: AsyncSession,
    character_id: str,
    target_character_id: str,
    item_name: str,
    item_category: str,
    item_index: int,
) -> dict:
    source = await db.get(Character, character_id)
    target = await db.get(Character, target_character_id)
    if not source:
        raise HTTPException(404, "来源角色不存在")
    if not target:
        raise HTTPException(404, "目标角色不存在")
    if source.id == target.id:
        raise HTTPException(400, "不能把物品转交给自己")
    if not source.session_id or not target.session_id or source.session_id != target.session_id:
        raise HTTPException(400, "只能在同一队伍内转交物品")

    try:
        result = transfer_inventory_item(
            source.equipment,
            target.equipment,
            item_name=item_name,
            item_category=item_category,
            item_index=item_index,
        )
    except InventoryError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    source.equipment = result["source_equipment"]
    target.equipment = result["target_equipment"]
    await db.commit()
    return {
        "transferred": result["transferred"],
        "target_character_id": target.id,
        "source_equipment": result["source_equipment"],
        "target_equipment": result["target_equipment"],
    }
