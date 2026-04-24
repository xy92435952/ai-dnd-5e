"""
api.combat.movement — 网格移动 + 借机攻击触发

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


@router.post("/combat/{session_id}/move")
async def combat_move(
    session_id: str, req: MoveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """在战斗格子上移动实体（每回合最多 6 格 = 30ft）"""
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")
    await assert_can_act(session, user_id, req.entity_id, db)

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    if not (0 <= req.to_x < 20 and 0 <= req.to_y < 12):
        raise HTTPException(400, "目标格子超出地图范围（20×12）")

    positions = dict(combat.entity_positions or {})
    for eid, pos in positions.items():
        if eid != req.entity_id and pos.get("x") == req.to_x and pos.get("y") == req.to_y:
            raise HTTPException(400, "目标格子已有其他实体")

    # ── 使用回合状态追踪移动力 ────────────────────────────
    ts  = _get_ts(combat, req.entity_id)
    cur = positions.get(str(req.entity_id))
    if cur:
        # Chebyshev 距离（对角移动和直线移动同等消耗，符合 5e 标准规则）
        dist      = max(abs(cur["x"] - req.to_x), abs(cur["y"] - req.to_y))
        remaining = ts["movement_max"] - ts["movement_used"]
        if dist > remaining:
            raise HTTPException(400, f"移动距离 {dist} 格超出剩余移动力（剩余 {remaining} 格）")

        # ── 借机攻击检查（移动前，使用旧位置计算相邻性）────
        # 脱离接战的实体不触发借机攻击
        opp_results = []
        if not ts.get("disengaged"):
            opp_results = await _resolve_opportunity_attacks(
                db       = db,
                session  = session,
                combat   = combat,
                moving_id = str(req.entity_id),
                old_pos  = cur,
                new_pos  = {"x": req.to_x, "y": req.to_y},
                positions = positions,
            )
        for opp in opp_results:
            if opp.get("log"):
                db.add(opp["log"])

        ts["movement_used"] += dist
        _save_ts(combat, req.entity_id, ts)

    positions[str(req.entity_id)] = {"x": req.to_x, "y": req.to_y}
    combat.entity_positions        = positions

    # 借机攻击后检查战斗是否结束
    opp_combat_over, opp_outcome = False, None
    if opp_results:
        opp_state   = session.game_state or {}
        opp_enemies = list(opp_state.get("enemies", []))
        player_opp  = await db.get(Character, session.player_character_id)
        opp_combat_over, opp_outcome = svc.check_combat_over(
            opp_enemies, player_opp.hp_current if player_opp else 0
        )
        if opp_combat_over:
            session.combat_active = False

    await db.commit()
    # 多人联机：广播位置变更
    await _broadcast_combat(session, combat, event_type="entity_moved",
                            entity_id=req.entity_id,
                            position={"x": req.to_x, "y": req.to_y})
    return {
        "entity_id":               req.entity_id,
        "x":                       req.to_x,
        "y":                       req.to_y,
        "positions":               positions,
        "turn_state":              ts,
        "movement_used":           ts["movement_used"],
        "movement_max":            ts["movement_max"],
        "opportunity_attacks":     [
            {"attacker": o["attacker"], "target": o["target"], **o["result"]}
            for o in opp_results
        ],
        "combat_over":             opp_combat_over,
        "outcome":                 opp_outcome,
    }


# ── 法术 ─────────────────────────────────────────────────

