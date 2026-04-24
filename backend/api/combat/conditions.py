"""
api.combat.conditions — 状态条件增删

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


@router.post("/combat/{session_id}/condition/add")
async def add_condition(
    session_id: str,
    req: ConditionRequest,
    db: AsyncSession = Depends(get_db),
):
    """向战斗实体添加状态条件（角色或敌人）"""
    session = await get_session_or_404(session_id, db)
    state   = session.game_state or {}

    rounds_str = f"（{req.rounds}回合）" if req.rounds else "（永久）"
    if req.is_enemy:
        enemies = list(state.get("enemies", []))
        enemy = next((e for e in enemies if e["id"] == req.entity_id), None)
        if not enemy:
            raise HTTPException(404, f"敌人 {req.entity_id} 不存在")
        conditions = list(enemy.get("conditions", []))
        if req.condition not in conditions:
            conditions.append(req.condition)
        if req.rounds is not None:
            durations = dict(enemy.get("condition_durations", {}))
            durations[req.condition] = req.rounds
            enemy["condition_durations"] = durations
        enemy["conditions"] = conditions
        state["enemies"] = enemies
        session.game_state = dict(state); flag_modified(session, "game_state")
    else:
        char = await db.get(Character, req.entity_id)
        if not char:
            raise HTTPException(404, "角色不存在")
        conditions = list(char.conditions or [])
        if req.condition not in conditions:
            conditions.append(req.condition)
        char.conditions = conditions
        if req.rounds is not None:
            durations = dict(char.condition_durations or {})
            durations[req.condition] = req.rounds
            char.condition_durations = durations

    db.add(GameLog(
        session_id = session_id,
        role       = "system",
        content    = f"🔴 {'敌人' if req.is_enemy else req.entity_id} 获得状态：{req.condition}{rounds_str}",
        log_type   = "system",
    ))
    await db.commit()
    return {"entity_id": req.entity_id, "conditions": conditions}


@router.post("/combat/{session_id}/condition/remove")
async def remove_condition(
    session_id: str,
    req: ConditionRequest,
    db: AsyncSession = Depends(get_db),
):
    """从战斗实体移除状态条件"""
    session = await get_session_or_404(session_id, db)
    state   = session.game_state or {}

    if req.is_enemy:
        enemies = list(state.get("enemies", []))
        enemy = next((e for e in enemies if e["id"] == req.entity_id), None)
        if not enemy:
            raise HTTPException(404, f"敌人 {req.entity_id} 不存在")
        conditions = [c for c in enemy.get("conditions", []) if c != req.condition]
        enemy["conditions"] = conditions
        state["enemies"] = enemies
        session.game_state = dict(state); flag_modified(session, "game_state")
    else:
        char = await db.get(Character, req.entity_id)
        if not char:
            raise HTTPException(404, "角色不存在")
        conditions = [c for c in (char.conditions or []) if c != req.condition]
        char.conditions = conditions

    db.add(GameLog(
        session_id = session_id,
        role       = "system",
        content    = f"🟢 {'敌人' if req.is_enemy else req.entity_id} 解除状态：{req.condition}",
        log_type   = "system",
    ))
    await db.commit()
    return {"entity_id": req.entity_id, "conditions": conditions}


# ── 濒死豁免 ──────────────────────────────────────────────

