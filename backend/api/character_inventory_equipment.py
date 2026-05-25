from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_character_access
from models import Character
from services.dnd_rules import calc_derived
from services.inventory_service import (
    InventoryError,
    update_ammo as update_inventory_ammo,
    update_equipment as update_inventory_equipment,
    update_gold as update_inventory_gold,
)


def recalculate_character_derived(char: Character, equipment: Optional[dict] = None) -> dict:
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


async def load_character_or_404(
    db: AsyncSession,
    character_id: str,
    *,
    user_id: str | None = None,
) -> Character:
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")
    if user_id is not None:
        await assert_character_access(char, user_id, db)
    return char


async def update_character_gold(
    *,
    db: AsyncSession,
    character_id: str,
    amount: int,
    reason: str,
    user_id: str | None = None,
) -> dict:
    char = await load_character_or_404(db, character_id, user_id=user_id)
    try:
        result = update_inventory_gold(char.equipment, amount=amount, reason=reason)
    except InventoryError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    char.equipment = result["equipment"]
    await db.commit()
    return {
        "gold": result["gold"],
        "change": result["change"],
        "reason": result["reason"],
    }


async def update_character_ammo(
    *,
    db: AsyncSession,
    character_id: str,
    weapon_name: str,
    change: int,
    user_id: str | None = None,
) -> dict:
    char = await load_character_or_404(db, character_id, user_id=user_id)
    try:
        result = update_inventory_ammo(
            char.equipment,
            weapon_name=weapon_name,
            change=change,
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


async def update_character_equipment(
    *,
    db: AsyncSession,
    character_id: str,
    item_name: str,
    item_category: str,
    equip: bool,
    user_id: str | None = None,
) -> dict:
    char = await load_character_or_404(db, character_id, user_id=user_id)
    try:
        result = update_inventory_equipment(
            char.equipment,
            item_name=item_name,
            item_category=item_category,
            equip=equip,
        )
    except InventoryError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    equipment = result["equipment"]
    char.equipment = equipment
    derived = recalculate_character_derived(char, equipment)

    await db.commit()
    await db.refresh(char)
    return {
        "equipment": char.equipment,
        "derived": derived,
        "ac": derived.get("ac", 10),
    }


async def update_character_equipment_bulk(
    *,
    db: AsyncSession,
    character_id: str,
    equipment: dict,
    user_id: str | None = None,
) -> dict:
    char = await load_character_or_404(db, character_id, user_id=user_id)
    char.equipment = equipment
    derived = recalculate_character_derived(char, equipment)

    await db.commit()
    await db.refresh(char)
    return {
        "ok": True,
        "equipment": char.equipment,
        "derived": derived,
    }
