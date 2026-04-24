"""
api.combat — 所有 /game/combat/* 端点

原 combat.py (5368 行) 已按功能域拆分为多个子模块，此处把它们的
router 合并暴露。main.py 仍然 `from api.combat import router` 即可。
"""
from fastapi import APIRouter

from . import (
    info, attacks, turns, reactions, ai_turn,
    movement, spellcasting, conditions, deathsaves,
)

router = APIRouter()
for _mod in (info, attacks, turns, reactions, ai_turn,
             movement, spellcasting, conditions, deathsaves):
    router.include_router(_mod.router)
