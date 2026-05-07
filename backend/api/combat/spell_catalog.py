"""
api.combat.spell_catalog — spell list query endpoints.
"""
from fastapi import APIRouter

from services.spell_service import spell_service

router = APIRouter(prefix="/game", tags=["combat"])


@router.get("/spells")
async def get_spell_list():
    """获取完整法术列表"""
    return spell_service.get_all()


@router.get("/spells/class/{class_name}")
async def get_spells_for_class(class_name: str, max_level: int = 9):
    """获取指定职业的可用法术"""
    return spell_service.get_for_class(class_name, max_level)
