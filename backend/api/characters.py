from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.character_create import create_player_character as _create_player_character
from api.character_party import generate_ai_party as _generate_ai_party
from api.character_progression import (
    level_up_character as _level_up_character,
    update_character_exhaustion as _update_character_exhaustion,
    update_character_prepared_spells as _update_character_prepared_spells,
)
from api.deps import assert_character_access, get_user_id
from database import get_db
from models import Character
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
    """获取角色创建所有可选项，含种族加值/职业技能选择等元数据"""
    return build_character_options(spell_service)


@router.post("/create", response_model=CharacterDetail)
async def create_character(
    req: CreateCharacterRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """创建玩家角色（含种族加值、熟练校验）"""
    return await _create_player_character(db=db, req=req, user_id=user_id)


@router.post("/generate-party", response_model=GeneratePartyResponse)
async def generate_party(
    req: GeneratePartyRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """生成 AI 队友，自动应用种族加值和熟练。"""
    return await _generate_ai_party(db=db, req=req, user_id=user_id)


@router.get("/{character_id}", response_model=CharacterDetail)
async def get_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()
    if not char:
        raise HTTPException(404, "角色不存在")
    await assert_character_access(char, user_id, db)
    return serialize_character(char)


@router.patch("/{character_id}/prepared-spells", response_model=PreparedSpellsResult)
async def update_prepared_spells(
    character_id: str,
    req: PreparedSpellsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """更新已准备法术（法师/牧师/德鲁伊专用，上限 = 等级 + 施法调整值）"""
    return await _update_character_prepared_spells(
        db=db,
        character_id=character_id,
        req=req,
        user_id=user_id,
    )


@router.post("/{character_id}/level-up", response_model=LevelUpResult)
async def level_up(
    character_id: str,
    req: LevelUpRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """角色升级：递增等级，重算衍生属性、HP、法术位和 ASI/专长。"""
    return await _level_up_character(
        db=db,
        character_id=character_id,
        req=req,
        user_id=user_id,
    )


@router.patch("/{character_id}/exhaustion", response_model=ExhaustionUpdateResult)
async def update_exhaustion(
    character_id: str,
    req: ExhaustionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Increase or decrease exhaustion level (0-6). Level 6 = death."""
    return await _update_character_exhaustion(
        db=db,
        character_id=character_id,
        req=req,
        user_id=user_id,
    )
