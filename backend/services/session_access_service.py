"""Session membership checks shared by API endpoints and combat services."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character, Session, SessionMember


async def assert_character_in_session(
    character: Character,
    session: Session,
    db: AsyncSession,
) -> None:
    """Ensure a character id is part of the target game session."""
    if character.session_id and str(character.session_id) == str(session.id):
        return

    if session.player_character_id and str(character.id) == str(session.player_character_id):
        return

    companion_ids = {
        str(companion_id)
        for companion_id in (session.game_state or {}).get("companion_ids", [])
    }
    if str(character.id) in companion_ids:
        return

    if session.is_multiplayer:
        result = await db.execute(
            select(SessionMember.id).where(
                SessionMember.session_id == session.id,
                SessionMember.character_id == character.id,
            )
        )
        if result.scalar_one_or_none():
            return

    raise HTTPException(403, "Character does not belong to this session")
