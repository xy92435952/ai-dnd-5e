"""
api.combat.info — 战斗状态查询 / 技能栏 / 命中率预测

从原 combat.py (单体 5368 行) 按功能域拆出，逻辑未改动。
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models import Character, CombatState, SessionMember
from api.deps import (
    assert_character_access,
    assert_character_in_session,
    assert_session_access,
    get_session_or_404,
    get_user_id,
)
from services.combat_prediction_service import build_combat_prediction
from services.combat_skill_bar_service import build_skill_bar
from services.dnd_rules import get_effective_hp_max
from services.combat_attack_modifier_service import calculate_cover_bonus

from api.combat._shared import _build_combat_snapshot, svc

router = APIRouter(prefix="/game", tags=["combat"])


# ── 获取战斗状态 ──────────────────────────────────────────

from schemas.game_responses import CombatStateResponse, SkillBarResponse


@router.get("/combat/{session_id}", response_model=CombatStateResponse)
async def get_combat_state(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """获取当前战斗状态（含完整实体数据）"""
    result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = result.scalars().first()
    if not combat:
        raise HTTPException(404, "当前没有进行中的战斗")

    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    await db.refresh(session)  # 确保读取最新的 game_state
    return await _build_combat_snapshot(
        db,
        session,
        combat,
        viewer_character_id=await _viewer_character_id(db, session, user_id),
    )


async def _viewer_character_id(db: AsyncSession, session, user_id: str) -> str | None:
    if session.is_multiplayer:
        result = await db.execute(
            select(SessionMember).where(
                SessionMember.session_id == session.id,
                SessionMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        return member.character_id if member and member.character_id else None
    return session.player_character_id


# ═══════════════════════════════════════════════════════════
# v0.10 新增：技能栏 + 命中率预测
# ═══════════════════════════════════════════════════════════

class PredictRequest(BaseModel):
    attacker_id: str
    target_id:   str
    action_key:  str = "atk"      # atk / smite / shove / bless / heal / lay / dash / disg / pot / ...
    is_ranged:   bool = False


@router.get("/combat/{session_id}/skill-bar", response_model=SkillBarResponse)
async def get_skill_bar_endpoint(
    session_id: str,
    entity_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    获取当前玩家的 10 格技能栏配置（v0.10 新增）。
    entity_id 可选，默认使用当前用户绑定的角色。
    """
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)

    # 解析目标角色
    if entity_id:
        player = await db.get(Character, entity_id)
        if player:
            await assert_character_access(player, user_id, db)
            await assert_character_in_session(player, session, db)
    elif session.is_multiplayer:
        from models import SessionMember
        mem = await db.execute(
            select(SessionMember).where(
                SessionMember.session_id == session_id,
                SessionMember.user_id == user_id,
            )
        )
        m = mem.scalar_one_or_none()
        if m and m.character_id:
            player = await db.get(Character, m.character_id)
        else:
            player = None
    else:
        player = await db.get(Character, session.player_character_id)

    if not player:
        raise HTTPException(404, "未找到角色")

    return {
        "entity_id":  player.id,
        # 字段名改为 char_class（与 ORM 一致；前端只读 .bar，不受影响）
        "char_class": player.char_class,
        "level":      player.level,
        "bar":        build_skill_bar(player),
    }


# ── 命中率预测 ──────────────────────────────────────────

@router.post("/combat/{session_id}/predict")
async def predict_action_endpoint(
    session_id: str,
    req: PredictRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    预测一次行动的命中率 / 暴击率 / 期望伤害（v0.10 新增）。
    纯算数，不掷骰、不消耗资源、不改状态。
    仅作为 UI 参考值展示；实际战斗仍以 /attack-roll / /spell-roll 为准。
    """
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    attacker = await db.get(Character, req.attacker_id)
    if not attacker:
        raise HTTPException(404, "攻击者不存在")

    await assert_character_access(attacker, user_id, db)
    await assert_character_in_session(attacker, session, db)

    a_derived = attacker.derived or {}
    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()

    # 解析目标（角色 or 敌人）
    state = session.game_state or {}
    enemies = state.get("enemies", [])
    target_ac = 10
    target_name = "?"
    target_hp = target_hp_max = 0
    target_conditions: list[str] = []

    tgt_char = await db.get(Character, req.target_id)
    if tgt_char:
        await assert_character_in_session(tgt_char, session, db)
        target_ac = (tgt_char.derived or {}).get("ac", 10)
        target_name = tgt_char.name
        target_hp = tgt_char.hp_current
        target_hp_max = get_effective_hp_max(tgt_char)
        target_conditions = tgt_char.conditions or []
    else:
        enemy = next((e for e in enemies if e.get("id") == req.target_id), None)
        if enemy:
            target_ac = (enemy.get("derived") or {}).get("ac", enemy.get("ac", 10))
            target_name = enemy.get("name", "敌人")
            target_hp = enemy.get("hp_current", 0)
            target_hp_max = (enemy.get("derived") or {}).get("hp_max", target_hp)
            target_conditions = enemy.get("conditions", [])

    cover_bonus = calculate_cover_bonus(
        grid_data=dict(combat.grid_data or {}) if combat else {},
        positions=dict(combat.entity_positions or {}) if combat else {},
        attacker_id=req.attacker_id,
        target_id=req.target_id,
        attacker_derived=a_derived,
        is_ranged=req.is_ranged,
    )

    return build_combat_prediction(
        attacker_derived=a_derived,
        attacker_conditions=attacker.conditions or [],
        target={
            "name": target_name,
            "hp": target_hp,
            "hp_max": target_hp_max,
            "ac": target_ac,
        },
        action_key=req.action_key,
        is_ranged=req.is_ranged,
        attack_modifiers=svc.get_attack_modifiers(attacker.conditions or [], attacker),
        defense_modifiers=svc.get_defense_modifiers(target_conditions),
        cover_bonus=cover_bonus,
    )


# ── 玩家战斗行动 ──────────────────────────────────────────
