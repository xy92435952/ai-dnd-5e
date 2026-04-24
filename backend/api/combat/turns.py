"""
api.combat.turns — 明确结束回合

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


@router.post("/combat/{session_id}/end-turn")
async def end_player_turn(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    玩家明确结束回合。
    - 对当前实体执行条件倒计时
    - 推进 current_turn_index
    - 重置下一实体的回合状态
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    turn_order = combat.turn_order or []
    current    = turn_order[combat.current_turn_index] if turn_order else {}
    # 多人联机：必须由当前回合归属玩家本人结束（AI 托管角色由 ai-turn 推进）
    current_cid = current.get("character_id") if isinstance(current, dict) else None
    if current_cid:
        await assert_can_act(session, user_id, current_cid, db)

    # ── 当前实体条件倒计时 ────────────────────────────────
    tick_logs = []
    if current.get("is_player"):
        player = await db.get(Character, session.player_character_id)
        if player:
            removed = _tick_conditions_char(player)
            for c in removed:
                tick_logs.append(GameLog(
                    session_id=session_id, role="system",
                    content=f"[{player.name}] 的【{c}】状态到期解除",
                    log_type="system",
                ))

    # ── 推进回合 ──────────────────────────────────────────
    next_index = (combat.current_turn_index + 1) % max(len(turn_order), 1)
    combat.current_turn_index = next_index
    if next_index == 0:
        combat.round_number += 1

    # ── 重置下一实体的回合状态（根据角色实际数据）────────
    if turn_order:
        next_entity_id = turn_order[next_index]["character_id"]
        next_atk_max, next_move_max = await _calc_entity_turn_limits(db, session, next_entity_id)
        _reset_ts(combat, next_entity_id, attacks_max=next_atk_max, movement_max=next_move_max)

    # ── 检查战斗结束 ──────────────────────────────────────
    state   = session.game_state or {}
    enemies = list(state.get("enemies", []))
    player_check         = await db.get(Character, session.player_character_id)
    combat_over, outcome = svc.check_combat_over(enemies, player_check.hp_current if player_check else 0)
    if combat_over:
        session.combat_active = False
        # 清理战斗状态记录，防止下次战斗残留旧数据
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs: await db.delete(_old_cs)
        except Exception: pass

    for tl in tick_logs:
        db.add(tl)
    await db.commit()
    # 多人联机：广播回合切换 + 最新战斗状态
    await _broadcast_combat(session, combat, event_type="turn_changed",
                            round_number=combat.round_number,
                            next_turn_index=next_index)

    return {
        "next_turn_index":    next_index,
        "round_number":       combat.round_number,
        "expired_conditions": [tl.content for tl in tick_logs],
        "combat_over":        combat_over,
        "outcome":            outcome,
    }


# ── 反应 (Reaction System, P0-6) ─────────────────────────

