"""
api.combat.ai_turn — NPC 自动回合 + 结束战斗

从原 combat.py (单体 5368 行) 按功能域拆出，逻辑未改动。
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import CombatState, Module
from api.deps import get_session_or_404

from api.combat._shared import (
    _broadcast_combat,
    _calc_entity_turn_limits,
    _reset_ts,
)
from api.combat.ai_turn_utils import advance_ai_turn
from api.combat.ai_turn_context import build_ai_turn_context
from api.combat.ai_turn_actions import handle_ai_simple_action
from api.combat.ai_turn_spell import handle_ai_spell_action
from api.combat.ai_turn_attack import handle_ai_attack_action
from schemas.combat_responses import EndTurnResult
from schemas.ws_events import CombatUpdate

router = APIRouter(prefix="/game", tags=["combat"])


async def _broadcast_ai_turn_result(session, combat, db, result: dict | None) -> dict | None:
    if result is None:
        return result
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            combat_over=result.get("combat_over", False),
            outcome=result.get("outcome"),
            actor_id=result.get("actor_id"),
            actor_name=result.get("actor_name"),
            narration=result.get("narration"),
            next_turn_index=result.get("next_turn_index"),
            round_number=result.get("round_number"),
            target_id=result.get("target_id"),
            target_new_hp=result.get("target_new_hp"),
            player_targeted=result.get("player_targeted", False),
            player_can_react=result.get("player_can_react", False),
            reaction_prompt=result.get("reaction_prompt"),
        ),
        db=db,
    )
    return result


@router.post("/combat/{session_id}/ai-turn", response_model=EndTurnResult)
async def ai_combat_turn(session_id: str, db: AsyncSession = Depends(get_db)):
    """处理当前 AI 实体的回合（队友或敌人）"""
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    turn_order = combat.turn_order or []
    if not turn_order:
        raise HTTPException(400, "先攻顺序为空")

    current    = turn_order[combat.current_turn_index]
    if current.get("is_player"):
        raise HTTPException(400, "当前是玩家回合，请使用 /action 接口")

    actor_id   = current.get("character_id", "")
    actor_name = current.get("name", "未知")
    state      = session.game_state or {}
    enemies    = list(state.get("enemies", []))
    positions  = dict(combat.entity_positions or {})
    is_enemy   = actor_id in [e["id"] for e in enemies]

    # ── 回合开始：重置施动者回合状态 ────────────────────────
    ai_atk_max, ai_move_max = await _calc_entity_turn_limits(db, session, actor_id)
    _reset_ts(combat, actor_id, attacks_max=ai_atk_max, movement_max=ai_move_max)

    # ── 获取施动者数据 ─────────────────────────────────────
    ai_ctx = await build_ai_turn_context(db, session, combat, actor_id, actor_name, enemies)
    actor_derived = ai_ctx["actor_derived"]
    actor_hp = ai_ctx["actor_hp"]
    e = ai_ctx["enemy_ref"]  # 敌人实体引用（供回合结束条件tick使用）
    achar = ai_ctx["ally_ref"]  # 队友实体引用（供回合结束条件tick使用）
    player = ai_ctx["player"]
    companions_alive = ai_ctx["companions_alive"]
    enemies_alive = ai_ctx["enemies_alive"]
    all_characters = ai_ctx["all_characters"]
    actor_full = ai_ctx["actor_full"]

    # 已死亡：跳过
    if actor_hp <= 0:
        next_index = (combat.current_turn_index + 1) % max(len(turn_order), 1)
        await advance_ai_turn(combat, session, db, turn_order, next_index)
        await db.commit()
        return await _broadcast_ai_turn_result(session, combat, db, {
            "actor_name": actor_name, "narration": f"{actor_name} 已倒下，跳过回合。",
            "actor_id": actor_id,
            "attack_result": {}, "damage": 0, "target_id": None, "target_new_hp": None,
            "next_turn_index": next_index, "round_number": combat.round_number,
            "combat_over": False, "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        })

    # ── 计算下一回合索引（多处提前返回需要使用）────────────
    next_index = (combat.current_turn_index + 1) % max(len(turn_order), 1)

    # ── AI 决策：选择目标和行动 ─────────────────────────────
    from services.ai_combat_agent import get_ai_decision, calc_difficulty

    # 获取模组难度
    _module = await db.get(Module, session.module_id) if session.module_id else None
    _parsed = (_module.parsed_content or {}) if _module else {}
    _difficulty = calc_difficulty(_parsed)

    # 获取战术/性格
    _tactics = actor_full.get("tactics", "") if is_enemy else ""
    _personality = ""
    if not is_enemy and achar:
        _personality = f"{achar.personality or ''} 战斗偏好: {actor_derived.get('combat_preference', '平衡')}"

    # 调用 AI 决策
    decision = await get_ai_decision(
        actor=actor_full,
        actor_is_enemy=is_enemy,
        all_characters=all_characters,
        all_enemies=enemies_alive,
        positions=dict(combat.entity_positions or {}),
        module_difficulty=_difficulty,
        module_tactics=_tactics,
        actor_personality=_personality,
    )

    # 从决策中获取目标
    decided_target_id = decision.get("target_id")
    decided_action = decision.get("action_type", "attack")
    decided_reason = decision.get("reason", "")
    simple_response = await handle_ai_simple_action(
        combat,
        session,
        db,
        turn_order,
        next_index,
        actor_id,
        actor_name,
        decided_action,
        decided_target_id,
        decided_reason,
        positions,
    )
    if simple_response is not None:
        return await _broadcast_ai_turn_result(session, combat, db, simple_response)

    spell_response = await handle_ai_spell_action(
        session_id,
        db,
        session,
        combat,
        turn_order,
        next_index,
        actor_id,
        actor_name,
        is_enemy,
        achar,
        actor_derived,
        decided_target_id,
        decided_reason,
        decision,
        state,
        enemies,
        enemies_alive,
        all_characters,
    )
    if spell_response is not None:
        return await _broadcast_ai_turn_result(session, combat, db, spell_response)

    attack_response = await handle_ai_attack_action(
        session_id,
        db,
        session,
        combat,
        turn_order,
        next_index,
        actor_id,
        actor_name,
        is_enemy,
        e,
        achar,
        actor_derived,
        player,
        companions_alive,
        enemies,
        enemies_alive,
        all_characters,
        positions,
        decided_target_id,
        decided_reason,
        decision,
    )
    if attack_response is not None:
        return await _broadcast_ai_turn_result(session, combat, db, attack_response)


# ── 移动 ─────────────────────────────────────────────────
