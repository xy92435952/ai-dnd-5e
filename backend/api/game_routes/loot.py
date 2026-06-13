from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.deps import (
    assert_character_write_access,
    assert_session_access,
    get_session_or_404,
    get_user_id,
)
from database import get_db
from models import Character, GameLog, Module
from schemas.game_requests import ClaimLootRequest
from services.character_roster import CharacterRoster
from services.loot_service import LootError, claim_loot_item, ensure_loot_state, public_loot_pool
from services.module_content import get_module_content
from services.session_access_service import assert_character_in_session


router = APIRouter(prefix="/game", tags=["game"])


@router.get("/sessions/{session_id}/loot")
async def get_session_loot(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    module = await db.get(Module, session.module_id) if session.module_id else None
    state = ensure_loot_state(session.game_state or {}, get_module_content(module))
    return public_loot_pool(state.get("loot_pool"))


@router.post("/sessions/{session_id}/loot/claim")
async def claim_session_loot(
    session_id: str,
    req: ClaimLootRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)

    character = await db.get(Character, req.character_id)
    if not character:
        raise HTTPException(404, "Character not found")
    await assert_character_write_access(character, user_id, db)
    await assert_character_in_session(character, session, db)

    module = await db.get(Module, session.module_id) if session.module_id else None
    party = (
        await CharacterRoster(db, session).party()
        if req.claim_mode in {"split_party", "roll_party"}
        else []
    )
    try:
        result = claim_loot_item(
            session.game_state or {},
            get_module_content(module),
            loot_id=req.loot_id,
            character_id=character.id,
            character_name=character.name,
            equipment=character.equipment,
            claim_mode=req.claim_mode,
            split_targets=[
                {
                    "character_id": member.id,
                    "character_name": member.name,
                    "equipment": member.equipment,
                }
                for member in party
            ],
        )
    except LootError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc

    equipment_updates = result.get("equipment_updates") or {}
    if equipment_updates:
        for member in party:
            updated_equipment = equipment_updates.get(member.id)
            if updated_equipment is not None:
                member.equipment = updated_equipment
    else:
        character.equipment = result["equipment"]
    session.game_state = result["game_state"]
    flag_modified(session, "game_state")
    claimed = result["loot"]
    db.add(GameLog(
        session_id=session.id,
        role="system",
        content=_loot_log_content(character.name, claimed, req.claim_mode),
        log_type="system",
    ))
    await db.commit()
    await db.refresh(character)

    return {
        "claimed": claimed,
        "character_id": claimed.get("claimed_by_character_id") or character.id,
        "equipment": result.get("equipment") or character.equipment,
        "equipment_updates": equipment_updates,
        "split_allocations": result.get("split_allocations") or [],
        "roll_allocations": result.get("roll_allocations") or [],
        "loot_pool": public_loot_pool(session.game_state.get("loot_pool")),
    }


def _loot_log_content(actor_name: str, claimed: dict, claim_mode: str) -> str:
    loot_name = claimed.get("name") or "loot"
    if claim_mode == "split_party":
        return f"[Loot] {actor_name} split {loot_name} with the party"
    if claim_mode == "party_stash":
        return f"[Loot] {actor_name} marked {loot_name} as shared party loot"
    if claim_mode == "roll_party":
        winner_name = claimed.get("claimed_by_name") or "a party member"
        return f"[Loot] {actor_name} rolled {loot_name} with the party; {winner_name} received it"
    return f"[Loot] {actor_name} claimed {loot_name}"
