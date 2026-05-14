from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.combat._shared import _get_ts, _save_ts
from database import get_db
from models import Character
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
from services.combat_item_service import (
    CombatItemAction,
    CombatItemActionError,
    consume_combat_item_action,
    prepare_combat_item_action,
)
from services.dnd_rules import ARMOR, SHOP_GEAR, WEAPONS, calc_derived
from services.inventory_service import (
    InventoryError,
    buy_item as buy_inventory_item,
    consume_gear_item_use,
    prepare_gear_item_use,
    sell_item as sell_inventory_item,
    transfer_item as transfer_inventory_item,
    update_ammo as update_inventory_ammo,
    update_equipment as update_inventory_equipment,
    update_gold as update_inventory_gold,
)
from services.item_effects import ItemEffectError, apply_item_effect, get_direct_use_effect

router = APIRouter(prefix="/characters", tags=["characters"])


def _recalculate_character_derived(char: Character, equipment: Optional[dict] = None) -> dict:
    derived = calc_derived(
        char.char_class,
        char.level,
        char.ability_scores,
        char.subclass,
        fighting_style=char.fighting_style,
        feats=char.feats or None,
        equipment=char.equipment if equipment is None else equipment,
        race=char.race,
        proficient_skills=char.proficient_skills or [],
    )
    char.derived = derived
    return derived


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
):
    """Add or spend gold. Equipment.gold tracks the character's gold."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    try:
        result = update_inventory_gold(char.equipment, amount=req.amount, reason=req.reason)
    except InventoryError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    char.equipment = result["equipment"]
    await db.commit()

    return {
        "gold": result["gold"],
        "change": result["change"],
        "reason": result["reason"],
    }


@router.patch("/{character_id}/ammo", response_model=AmmoUpdateResult)
async def update_ammo(
    character_id: str,
    req: AmmoRequest,
    db: AsyncSession = Depends(get_db),
):
    """Track ammunition for ranged weapons."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    try:
        result = update_inventory_ammo(
            char.equipment,
            weapon_name=req.weapon_name,
            change=req.change,
        )
    except InventoryError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    char.equipment = result["equipment"]
    await db.commit()

    return {
        "weapon": result["weapon"],
        "ammo": result["ammo"],
        "change": result["change"],
    }


@router.patch("/{character_id}/equipment")
async def update_equipment(
    character_id: str,
    req: EquipmentUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update character equipment (equip/unequip weapons/armor)."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    try:
        result = update_inventory_equipment(
            char.equipment,
            item_name=req.item_name,
            item_category=req.item_category,
            equip=req.equip,
        )
    except InventoryError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    equipment = result["equipment"]
    char.equipment = equipment
    derived = _recalculate_character_derived(char, equipment)

    await db.commit()
    await db.refresh(char)

    return {
        "equipment": char.equipment,
        "derived": derived,
        "ac": derived.get("ac", 10),
    }


@router.patch("/{character_id}/equipment-bulk")
async def update_equipment_bulk(
    character_id: str,
    req: EquipmentBulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Replace full equipment dict and recalculate derived stats."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    char.equipment = req.equipment
    derived = _recalculate_character_derived(char, req.equipment)

    await db.commit()
    await db.refresh(char)

    return {
        "ok": True,
        "equipment": char.equipment,
        "derived": derived,
    }


@router.post("/{character_id}/shop/buy")
async def buy_item(
    character_id: str,
    req: BuyItemRequest,
    db: AsyncSession = Depends(get_db),
):
    """Buy an item from the shop. Deducts gold and adds to equipment."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    try:
        result = buy_inventory_item(
            char.equipment,
            item_name=req.item_name,
            item_category=req.item_category,
            quantity=req.quantity,
        )
    except InventoryError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    char.equipment = result["equipment"]
    await db.commit()
    return result


@router.post("/{character_id}/shop/sell")
async def sell_item(
    character_id: str,
    req: SellItemRequest,
    db: AsyncSession = Depends(get_db),
):
    """Sell an item for half its purchase price. Removes from equipment."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    try:
        result = sell_inventory_item(
            char.equipment,
            item_name=req.item_name,
            item_category=req.item_category,
            item_index=req.item_index,
        )
    except InventoryError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    equipment = result["equipment"]
    char.equipment = equipment
    if req.item_category == "armor":
        _recalculate_character_derived(char, equipment)

    await db.commit()
    return result


@router.post("/{character_id}/transfer-item")
async def transfer_item(
    character_id: str,
    req: TransferItemRequest,
    db: AsyncSession = Depends(get_db),
):
    """Move one inventory item from this character to a party member."""
    source = await db.get(Character, character_id)
    target = await db.get(Character, req.target_character_id)
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
            item_name=req.item_name,
            item_category=req.item_category,
            item_index=req.item_index,
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


@router.post("/{character_id}/use-item")
async def use_item(
    character_id: str,
    req: UseItemRequest,
    db: AsyncSession = Depends(get_db),
):
    """Use a direct-effect consumable item."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    combat_action: CombatItemAction | None = None
    if req.use_in_combat:
        try:
            combat_action = await prepare_combat_item_action(
                db=db,
                character_id=character_id,
                session_id=req.session_id,
                get_turn_state=_get_ts,
            )
        except CombatItemActionError as exc:
            raise HTTPException(exc.status_code, exc.detail) from exc

    try:
        prepared_item = prepare_gear_item_use(char.equipment, item_name=req.item_name)
    except InventoryError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    item_data = prepared_item.item_data

    try:
        effect = get_direct_use_effect(req.item_name, item_data)
    except ItemEffectError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    target = None
    if effect == "stabilize":
        target_id = req.target_character_id or character_id
        target = char if str(target_id) == str(character_id) else await db.get(Character, target_id)
        if not target:
            raise HTTPException(404, "目标角色不存在")

    try:
        result = apply_item_effect(
            actor=char,
            item_name=req.item_name,
            item_data=item_data,
            target=target,
        )
    except ItemEffectError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    consume_result = consume_gear_item_use(prepared_item)
    equipment = consume_result["equipment"]
    if "uses_remaining" in consume_result:
        result["uses_remaining"] = consume_result["uses_remaining"]
    char.equipment = equipment

    if combat_action is not None:
        turn_state = consume_combat_item_action(
            combat_action,
            character_id=character_id,
            save_turn_state=_save_ts,
        )
        result["turn_state"] = turn_state

    await db.commit()

    result["equipment"] = equipment
    result["hp_current"] = char.hp_current
    return result
