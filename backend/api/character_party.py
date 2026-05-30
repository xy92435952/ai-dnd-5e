from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_character_access, assert_module_access
from models import Character, Module
from schemas.character_requests import GeneratePartyRequest
from services.character_companion_service import build_companion_character
from services.character_serializer import serialize_character
from services.langgraph_client import langgraph_client
from services.module_content import get_module_content


async def generate_ai_party(
    *,
    db: AsyncSession,
    req: GeneratePartyRequest,
    user_id: str | None = None,
) -> dict:
    result = await db.execute(select(Character).where(Character.id == req.player_character_id))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    if user_id is not None:
        await assert_character_access(player, user_id, db, allow_room_ai=False)

    mod_result = await db.execute(select(Module).where(Module.id == req.module_id))
    module = mod_result.scalar_one_or_none()
    if not module:
        raise HTTPException(404, "模组不存在")

    if user_id is not None:
        assert_module_access(module, user_id)

    companions_data = await langgraph_client.generate_party(
        player_class=player.char_class,
        player_race=player.race,
        player_level=player.level,
        party_size=req.party_size,
        module_data=get_module_content(module),
    )

    companions = []
    for data in companions_data:
        companion = build_companion_character(data, fallback_level=player.level)
        db.add(companion)
        await db.flush()
        companions.append(serialize_character(companion))

    await db.commit()
    return {"companions": companions}
