from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_character_access
from models import Character, Session
from services.inventory_service import (
    InventoryError,
    buy_item as buy_inventory_item,
    sell_item as sell_inventory_item,
    transfer_item as transfer_inventory_item,
)
from services.shop_pricing_service import build_shop_pricing_context, is_item_in_stock

from api.character_inventory_equipment import load_character_or_404, recalculate_character_derived


async def shop_pricing_for_character(db: AsyncSession, char: Character) -> dict:
    session = await db.get(Session, char.session_id) if char.session_id else None
    return build_shop_pricing_context(session.game_state if session else {})


async def buy_character_item(
    *,
    db: AsyncSession,
    character_id: str,
    item_name: str,
    item_category: str,
    quantity: int,
    user_id: str | None = None,
) -> dict:
    char = await load_character_or_404(db, character_id, user_id=user_id)
    price_context = await shop_pricing_for_character(db, char)
    if not is_item_in_stock(item_name, item_category, price_context):
        raise HTTPException(404, "当前地点商人不出售该物品")
    try:
        result = buy_inventory_item(
            char.equipment,
            item_name=item_name,
            item_category=item_category,
            quantity=quantity,
            price_context=price_context,
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
    user_id: str | None = None,
) -> dict:
    char = await load_character_or_404(db, character_id, user_id=user_id)
    price_context = await shop_pricing_for_character(db, char)
    try:
        result = sell_inventory_item(
            char.equipment,
            item_name=item_name,
            item_category=item_category,
            item_index=item_index,
            price_context=price_context,
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
    user_id: str | None = None,
) -> dict:
    source = await db.get(Character, character_id)
    target = await db.get(Character, target_character_id)
    if not source:
        raise HTTPException(404, "来源角色不存在")
    if not target:
        raise HTTPException(404, "目标角色不存在")
    if source.id == target.id:
        raise HTTPException(400, "不能把物品转交给自己")
    if user_id is not None:
        await assert_character_access(source, user_id, db)
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
