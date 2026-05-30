from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_optional_user_id, get_user_id
from api.character_inventory_equipment import (
    load_character_or_404 as _load_character_or_404,
    recalculate_character_derived as _recalculate_character_derived,
    update_character_ammo as _update_character_ammo,
    update_character_equipment as _update_character_equipment,
    update_character_equipment_bulk as _update_character_equipment_bulk,
    update_character_gold as _update_character_gold,
)
from api.character_inventory_shop import (
    buy_character_item as _buy_character_item,
    sell_character_item as _sell_character_item,
    shop_pricing_for_character as _shop_pricing_for_character,
    transfer_character_item as _transfer_character_item,
)
from api.character_inventory_use_item import use_character_item as _use_character_item
from database import get_db
from schemas.character_requests import (
    AmmoRequest,
    BuyItemRequest,
    EquipmentBulkUpdateRequest,
    EquipmentUpdateRequest,
    GoldRequest,
    SellItemRequest,
    TransferItemRequest,
    UseItemRequest,
)
from schemas.game_responses import AmmoUpdateResult, GoldUpdateResult
from services.shop_pricing_service import build_shop_inventory

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("/shop/inventory")
async def get_shop_inventory(
    character_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """Return all available items for purchase (weapons, armor, gear)."""
    if not character_id:
        return build_shop_inventory()
    if user_id is None:
        raise HTTPException(401, "未登录，请先登录")
    char = await _load_character_or_404(db, character_id, user_id=user_id)
    pricing = await _shop_pricing_for_character(db, char)
    return build_shop_inventory(pricing)


@router.patch("/{character_id}/gold", response_model=GoldUpdateResult)
async def update_gold(
    character_id: str,
    req: GoldRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Add or spend gold. Equipment.gold tracks the character's gold."""
    return await _update_character_gold(
        db=db,
        character_id=character_id,
        amount=req.amount,
        reason=req.reason,
        user_id=user_id,
    )


@router.patch("/{character_id}/ammo", response_model=AmmoUpdateResult)
async def update_ammo(
    character_id: str,
    req: AmmoRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Track ammunition for ranged weapons."""
    return await _update_character_ammo(
        db=db,
        character_id=character_id,
        weapon_name=req.weapon_name,
        change=req.change,
        user_id=user_id,
    )


@router.patch("/{character_id}/equipment")
async def update_equipment(
    character_id: str,
    req: EquipmentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Update character equipment (equip/unequip weapons/armor)."""
    return await _update_character_equipment(
        db=db,
        character_id=character_id,
        item_name=req.item_name,
        item_category=req.item_category,
        equip=req.equip,
        user_id=user_id,
    )


@router.patch("/{character_id}/equipment-bulk")
async def update_equipment_bulk(
    character_id: str,
    req: EquipmentBulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Replace full equipment dict and recalculate derived stats."""
    return await _update_character_equipment_bulk(
        db=db,
        character_id=character_id,
        equipment=req.equipment,
        user_id=user_id,
    )


@router.post("/{character_id}/shop/buy")
async def buy_item(
    character_id: str,
    req: BuyItemRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Buy an item from the shop. Deducts gold and adds to equipment."""
    return await _buy_character_item(
        db=db,
        character_id=character_id,
        item_name=req.item_name,
        item_category=req.item_category,
        quantity=req.quantity,
        user_id=user_id,
    )


@router.post("/{character_id}/shop/sell")
async def sell_item(
    character_id: str,
    req: SellItemRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Sell an item for half its purchase price. Removes from equipment."""
    return await _sell_character_item(
        db=db,
        character_id=character_id,
        item_name=req.item_name,
        item_category=req.item_category,
        item_index=req.item_index,
        user_id=user_id,
    )


@router.post("/{character_id}/transfer-item")
async def transfer_item(
    character_id: str,
    req: TransferItemRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Move one inventory item from this character to a party member."""
    return await _transfer_character_item(
        db=db,
        character_id=character_id,
        target_character_id=req.target_character_id,
        item_name=req.item_name,
        item_category=req.item_category,
        item_index=req.item_index,
        user_id=user_id,
    )


@router.post("/{character_id}/use-item")
async def use_item(
    character_id: str,
    req: UseItemRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Use a direct-effect consumable item."""
    return await _use_character_item(
        db=db,
        character_id=character_id,
        item_name=req.item_name,
        target_character_id=req.target_character_id,
        session_id=req.session_id,
        use_in_combat=req.use_in_combat,
        user_id=user_id,
    )
