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
    get_user_id, assert_can_act, assert_character_in_session, assert_session_access, broadcast_to_session, current_turn_user_id,
)
from services.combat_service import CombatService
from services.spell_service import spell_service
from services.dnd_rules import roll_dice, _normalize_class, get_life_state
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
from schemas.combat_responses import ConditionUpdateResult
from schemas.ws_events import CombatUpdate
from services.combat_concentration_service import break_concentration_if_incapacitated

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/condition/add", response_model=ConditionUpdateResult)
async def add_condition(
    session_id: str,
    req: ConditionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """向战斗实体添加状态条件（角色或敌人）"""
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
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
        await assert_character_in_session(char, session, db)
        conditions = list(char.conditions or [])
        if req.condition not in conditions:
            conditions.append(req.condition)
        char.conditions = conditions
        if req.rounds is not None:
            durations = dict(char.condition_durations or {})
            durations[req.condition] = req.rounds
            char.condition_durations = durations
        concentration_log = break_concentration_if_incapacitated(char, session_id)
        if concentration_log:
            db.add(concentration_log)

    db.add(GameLog(
        session_id = session_id,
        role       = "system",
        content    = f"🔴 {'敌人' if req.is_enemy else req.entity_id} 获得状态：{req.condition}{rounds_str}",
        log_type   = "system",
    ))
    await db.commit()
    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if combat:
        await _broadcast_combat(
            session,
            combat,
            CombatUpdate(actor_id=req.entity_id, condition=req.condition, condition_action="add"),
            db=db,
        )
    response = {"entity_id": req.entity_id, "conditions": conditions}
    if not req.is_enemy:
        response["concentration"] = char.concentration
        response["target_state"] = {
            "target_id": req.entity_id,
            "conditions": conditions,
            "condition_durations": char.condition_durations or {},
            "life_state": get_life_state(char),
            "concentration": char.concentration,
        }
    return response


@router.post("/combat/{session_id}/condition/remove", response_model=ConditionUpdateResult)
async def remove_condition(
    session_id: str,
    req: ConditionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """从战斗实体移除状态条件"""
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
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
        await assert_character_in_session(char, session, db)
        conditions = [c for c in (char.conditions or []) if c != req.condition]
        char.conditions = conditions

    db.add(GameLog(
        session_id = session_id,
        role       = "system",
        content    = f"🟢 {'敌人' if req.is_enemy else req.entity_id} 解除状态：{req.condition}",
        log_type   = "system",
    ))
    await db.commit()
    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if combat:
        await _broadcast_combat(
            session,
            combat,
            CombatUpdate(actor_id=req.entity_id, condition=req.condition, condition_action="remove"),
            db=db,
        )
    return {"entity_id": req.entity_id, "conditions": conditions}


# ── 濒死豁免 ──────────────────────────────────────────────

