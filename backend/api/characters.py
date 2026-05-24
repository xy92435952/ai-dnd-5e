from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.character_create import create_player_character as _create_player_character
from api.character_party import generate_ai_party as _generate_ai_party
from api.character_progression import (
    level_up_character as _level_up_character,
    update_character_exhaustion as _update_character_exhaustion,
    update_character_prepared_spells as _update_character_prepared_spells,
)
from api.deps import get_authorized_character, get_authorized_module, get_user_id
from database import get_db
from schemas.character_requests import (
    CreateCharacterRequest,
    ExhaustionRequest,
    GeneratePartyRequest,
    LevelUpRequest,
    PreparedSpellsRequest,
)
from schemas.game_responses import (
    CharacterDetail,
    CharacterOptionsResponse,
    ExhaustionUpdateResult,
    GeneratePartyResponse,
    LevelUpResult,
    PreparedSpellsResult,
)
from services.character_options_service import build_character_options
from services.character_serializer import serialize_character
from services.spell_service import spell_service

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("/options", response_model=CharacterOptionsResponse)
async def get_character_options():
    return build_character_options(spell_service)


@router.post("/create", response_model=CharacterDetail)
async def create_character(
    req: CreateCharacterRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    await get_authorized_module(req.module_id, db, user_id)
    return await _create_player_character(db=db, req=req, user_id=user_id)


@router.post("/generate-party", response_model=GeneratePartyResponse)
async def generate_party(
    req: GeneratePartyRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    await get_authorized_module(req.module_id, db, user_id)
    await get_authorized_character(req.player_character_id, db, user_id, require_control=True)
    return await _generate_ai_party(db=db, req=req)


@router.get("/{character_id}", response_model=CharacterDetail)
async def get_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    char = await get_authorized_character(character_id, db, user_id)
    return serialize_character(char)


@router.patch("/{character_id}/prepared-spells", response_model=PreparedSpellsResult)
async def update_prepared_spells(
    character_id: str,
    req: PreparedSpellsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    await get_authorized_character(character_id, db, user_id, require_control=True)
    return await _update_character_prepared_spells(
        db=db,
        character_id=character_id,
        req=req,
    )


@router.post("/{character_id}/level-up", response_model=LevelUpResult)
async def level_up(
    character_id: str,
    req: LevelUpRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    await get_authorized_character(character_id, db, user_id, require_control=True)
    return await _level_up_character(
        db=db,
        character_id=character_id,
        req=req,
    )


@router.patch("/{character_id}/exhaustion", response_model=ExhaustionUpdateResult)
async def update_exhaustion(
    character_id: str,
    req: ExhaustionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    await get_authorized_character(character_id, db, user_id, require_control=True)
    return await _update_character_exhaustion(
        db=db,
        character_id=character_id,
        req=req,
    )
