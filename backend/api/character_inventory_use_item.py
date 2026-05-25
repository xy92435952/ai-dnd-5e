from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_character_access
from api.combat._shared import _get_ts, _save_ts
from api.character_inventory_equipment import load_character_or_404
from models import Character
from services.combat_item_service import (
    CombatItemAction,
    CombatItemActionError,
    consume_combat_item_action,
    prepare_combat_item_action,
)
from services.inventory_service import InventoryError, consume_gear_item_use, prepare_gear_item_use
from services.item_effects import ItemEffectError, apply_item_effect, get_direct_use_effect


async def use_character_item(
    *,
    db: AsyncSession,
    character_id: str,
    item_name: str,
    target_character_id: str | None = None,
    session_id: str | None = None,
    use_in_combat: bool = False,
    user_id: str | None = None,
) -> dict:
    char = await load_character_or_404(db, character_id, user_id=user_id)

    combat_action: CombatItemAction | None = None
    if use_in_combat:
        try:
            combat_action = await prepare_combat_item_action(
                db=db,
                character_id=character_id,
                session_id=session_id,
                get_turn_state=_get_ts,
            )
        except CombatItemActionError as exc:
            raise HTTPException(exc.status_code, exc.detail) from exc

    try:
        prepared_item = prepare_gear_item_use(char.equipment, item_name=item_name)
    except InventoryError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    item_data = prepared_item.item_data

    try:
        effect = get_direct_use_effect(item_name, item_data)
    except ItemEffectError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    target = None
    if effect == "stabilize":
        target_id = target_character_id or character_id
        target = char if str(target_id) == str(character_id) else await db.get(Character, target_id)
        if not target:
            raise HTTPException(404, "目标角色不存在")

    if target is not None and target.id != char.id and user_id is not None:
        if not target.session_id or target.session_id != char.session_id:
            raise HTTPException(400, "Target character is not in the same party")
        await assert_character_access(target, user_id, db)

    try:
        result = apply_item_effect(
            actor=char,
            item_name=item_name,
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
