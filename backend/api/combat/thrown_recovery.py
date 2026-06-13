from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.combat.schemas import RecoverThrownWeaponsRequest
from api.deps import assert_character_write_access, assert_session_access, get_session_or_404, get_user_id
from database import get_db
from models import Character, GameLog
from services.combat_thrown_recovery_service import recover_thrown_weapons
from services.session_access_service import assert_character_in_session


router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/recover-thrown-weapons")
async def recover_combat_thrown_weapons(
    session_id: str,
    req: RecoverThrownWeaponsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    if session.combat_active:
        raise HTTPException(400, "Thrown weapons can be recovered after combat")

    character = await db.get(Character, req.character_id)
    if not character:
        raise HTTPException(404, "Character not found")
    await assert_character_in_session(character, session, db)
    await _assert_thrown_recovery_authority(character, session, user_id, db)

    result = recover_thrown_weapons(
        session.game_state or {},
        character_id=character.id,
        character_name=character.name,
        equipment=character.equipment,
    )
    character.equipment = result["equipment"]
    session.game_state = result["game_state"]
    flag_modified(character, "equipment")
    flag_modified(session, "game_state")

    if result["recovered"]:
        db.add(GameLog(
            session_id=session.id,
            role="system",
            content=_recovery_log_content(character.name, result["recovered"]),
            log_type="system",
        ))

    await db.commit()
    await db.refresh(character)
    return {
        "character_id": character.id,
        "equipment": character.equipment,
        "recovered": result["recovered"],
        "recovery_pool": result["recovery_pool"],
    }


def _recovery_log_content(character_name: str, recovered: list[dict]) -> str:
    summary = ", ".join(
        f"{item.get('weapon') or 'Thrown weapon'} x{item.get('quantity') or 1}"
        for item in recovered
    )
    return f"[Combat] {character_name} recovered thrown weapons: {summary}"


async def _assert_thrown_recovery_authority(
    character: Character,
    session,
    user_id: str,
    db: AsyncSession,
) -> None:
    await assert_character_write_access(character, user_id, db)
