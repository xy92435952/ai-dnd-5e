from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_user_id
from api.character_inventory_equipment import (
    recalculate_character_derived as _recalculate_character_derived,
    update_character_ammo as _update_character_ammo,
    update_character_equipment as _update_character_equipment,
    update_character_equipment_bulk as _update_character_equipment_bulk,
    update_character_gold as _update_character_gold,
)
from api.character_inventory_shop import (
    buy_character_item as _buy_character_item,
    sell_character_item as _sell_character_item,
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
from services.dnd_rules import ARMOR, SHOP_GEAR, WEAPONS

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("/shop/inventory")
async def get_shop_inventory():
    """Return all available items for purchase (weapons, armor, gear)."""
    return {
        "weapons": {name: {**data, "category": "weapon"} for name, data in WEAPONS.items()},
        "armor": {name: {**data, "category": "armor"} for name, data in ARMOR.items()},
        "gear": {name: {**data, "category": "gear"} for name, data in SHOP_GEAR.items()},
    }


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
