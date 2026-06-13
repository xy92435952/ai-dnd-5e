"""
api.combat — 所有 /game/combat/* 端点

原 combat.py (5368 行) 已按功能域拆分为多个子模块，此处把它们的
router 合并暴露。main.py 仍然 `from api.combat import router` 即可。
"""
from fastapi import APIRouter

from . import (
    info, attacks, attack_rolls, turns, reactions, ready_actions, ai_turn, ai_end,
    movement, spell_catalog, spell_rolls, spellcasting, conditions, deathsaves,
    grapples, smites, class_features, maneuvers, inspect,
)
from ._shared import (
    _get_ts, _save_ts, _check_attack_range, _ai_move_toward,
    _chebyshev_dist, _calc_entity_turn_limits,
)

router = APIRouter()
for _mod in (info, attacks, attack_rolls, turns, reactions, ready_actions, ai_turn, ai_end,
             movement, spell_catalog, spell_rolls, spellcasting, conditions, deathsaves,
             grapples, smites, class_features, maneuvers, inspect):
    router.include_router(_mod.router)
