"""
api.combat.deathsaves — 濒死豁免

从原 combat.py (单体 5368 行) 按功能域拆出，逻辑未改动。
"""
import uuid
import random
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, Session, GameLog, CombatState, Module
from api.deps import (
    get_session_or_404, entity_snapshot, serialize_combat,
    get_user_id, assert_can_act, broadcast_to_session, current_turn_user_id,
)
from services.combat_service import CombatService
from services.spell_service import spell_service
from services.dnd_rules import roll_dice, _normalize_class
from services.combat_narrator import narrate_action, narrate_batch
from services.character_roster import CharacterRoster

from api.combat._shared import (
    _DEFAULT_TS, svc,
    _get_ts, _save_ts, _reset_ts,
    _broadcast_combat, _calc_entity_turn_limits,
    _chebyshev_dist, _check_attack_range, _ai_move_toward,
    _has_adjacent_enemy, _has_ally_adjacent_to,
    _do_concentration_check, _tick_conditions_char, _tick_conditions_enemy,
    _chebyshev, _resolve_opportunity_attacks,
)
from api.combat.schemas import (
    MoveRequest, ConditionRequest, CombatActionRequest, DeathSaveRequest,
    SmiteRequest, ClassFeatureRequest, ReactionRequest, GrappleShoveRequest,
    AttackRollRequest, DamageRollRequest, SpellRequest, SpellRollRequest,
    SpellConfirmRequest, ManeuverRequest,
)

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/death-save")
async def death_saving_throw(
    session_id: str,
    req: DeathSaveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    濒死豁免检定（5e PHB p.197）
    - HP = 0 的角色每回合投 d20
    - 20（自然）：立即稳定并恢复1HP
    - 1（自然）：记为2次失败
    - 10+：成功
    - <10：失败
    - 3成功 → 稳定（stable=True，停止豁免）
    - 3失败 → 死亡（角色被移除战斗）
    """
    session = await get_session_or_404(session_id, db)
    await assert_can_act(session, user_id, req.character_id, db, require_current_turn=False)
    char = await db.get(Character, req.character_id)
    if not char:
        raise HTTPException(404, "角色不存在")
    if char.hp_current > 0:
        raise HTTPException(400, "该角色 HP > 0，无需进行濒死豁免")

    saves = dict(char.death_saves or {"successes": 0, "failures": 0, "stable": False})
    if saves.get("stable"):
        raise HTTPException(400, "该角色已稳定，无需再投")

    d20    = req.d20_value if req.d20_value is not None else random.randint(1, 20)
    result = {}

    if d20 == 20:
        # 自然20：立即稳定 + 1HP
        char.hp_current    = 1
        saves["stable"]    = True
        saves["successes"] = 3
        char.death_saves   = saves
        msg = f"🌟 {char.name} 自然20！从死亡边缘爬回，恢复1HP！"
        result = {"d20": d20, "outcome": "revive", "hp": 1}
    elif d20 == 1:
        # 自然1：2次失败
        saves["failures"] = min(3, saves.get("failures", 0) + 2)
        char.death_saves  = saves
        if saves["failures"] >= 3:
            msg = f"💀 {char.name} 自然1！两次失败，已阵亡…"
            result = {"d20": d20, "outcome": "dead", "failures": saves["failures"]}
        else:
            msg = f"😱 {char.name} 自然1！失败计数 +2（{saves['failures']}/3）"
            result = {"d20": d20, "outcome": "failure", "failures": saves["failures"]}
    elif d20 >= 10:
        # 成功
        saves["successes"] = saves.get("successes", 0) + 1
        if saves["successes"] >= 3:
            saves["stable"] = True
            msg = f"✅ {char.name} 濒死豁免成功 3/3！已稳定。"
            result = {"d20": d20, "outcome": "stable", "successes": saves["successes"]}
        else:
            msg = f"✅ {char.name} 濒死豁免成功（{saves['successes']}/3）"
            result = {"d20": d20, "outcome": "success", "successes": saves["successes"]}
        char.death_saves = saves
    else:
        # 失败
        saves["failures"] = saves.get("failures", 0) + 1
        if saves["failures"] >= 3:
            msg = f"💀 {char.name} 濒死豁免失败 3/3，已阵亡…"
            result = {"d20": d20, "outcome": "dead", "failures": saves["failures"]}
        else:
            msg = f"❌ {char.name} 濒死豁免失败（{saves['failures']}/3）"
            result = {"d20": d20, "outcome": "failure", "failures": saves["failures"]}
        char.death_saves = saves

    db.add(GameLog(
        session_id  = session_id,
        role        = "system",
        content     = msg,
        log_type    = "dice",
        dice_result = result,
    ))
    await db.commit()
    return {
        "character_id": req.character_id,
        "character_name": char.name,
        "death_saves": saves,
        **result,
    }



# ── 战技（Battle Master Maneuvers）──────────────────────────

