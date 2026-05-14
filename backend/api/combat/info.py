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
from models import Character, CombatState
from api.deps import (
    get_session_or_404, entity_snapshot, serialize_combat, get_user_id,
)
from services.character_roster import CharacterRoster
from services.combat_prediction_service import build_combat_prediction
from services.combat_skill_bar_service import build_skill_bar

from api.combat._shared import svc

router = APIRouter(prefix="/game", tags=["combat"])


# ── 获取战斗状态 ──────────────────────────────────────────

from schemas.game_responses import CombatStateResponse, SkillBarResponse


@router.get("/combat/{session_id}", response_model=CombatStateResponse)
async def get_combat_state(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取当前战斗状态（含完整实体数据）"""
    result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = result.scalars().first()
    if not combat:
        raise HTTPException(404, "当前没有进行中的战斗")

    session = await get_session_or_404(session_id, db)
    await db.refresh(session)  # 确保读取最新的 game_state
    state   = session.game_state or {}
    enemies = state.get("enemies", [])
    entities: dict = {}

    roster = CharacterRoster(db, session)
    for c in await roster.party():
        entities[c.id] = entity_snapshot(c, is_enemy=False)

    for e in enemies:
        entities[e["id"]] = {
            "id":         e["id"],
            "name":       e["name"],
            "is_player":  False,
            "is_enemy":   True,
            "hp_current": e.get("hp_current", 0),
            "hp_max":     e.get("derived", {}).get("hp_max", 10),
            "ac":         e.get("derived", {}).get("ac", 10),
            "conditions": e.get("conditions", []),
        }

    return {**serialize_combat(combat), "entities": entities, "turn_states": combat.turn_states or {}}


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

    # 解析目标角色
    if entity_id:
        player = await db.get(Character, entity_id)
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
    attacker = await db.get(Character, req.attacker_id)
    if not attacker:
        raise HTTPException(404, "攻击者不存在")

    a_derived = attacker.derived or {}

    # 解析目标（角色 or 敌人）
    state = session.game_state or {}
    enemies = state.get("enemies", [])
    target_ac = 10
    target_name = "?"
    target_hp = target_hp_max = 0
    target_conditions: list[str] = []

    tgt_char = await db.get(Character, req.target_id)
    if tgt_char:
        target_ac = (tgt_char.derived or {}).get("ac", 10)
        target_name = tgt_char.name
        target_hp = tgt_char.hp_current
        target_hp_max = (tgt_char.derived or {}).get("hp_max", tgt_char.hp_current)
        target_conditions = tgt_char.conditions or []
    else:
        enemy = next((e for e in enemies if e.get("id") == req.target_id), None)
        if enemy:
            target_ac = (enemy.get("derived") or {}).get("ac", enemy.get("ac", 10))
            target_name = enemy.get("name", "敌人")
            target_hp = enemy.get("hp_current", 0)
            target_hp_max = (enemy.get("derived") or {}).get("hp_max", target_hp)
            target_conditions = enemy.get("conditions", [])

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
        attack_modifiers=svc.get_attack_modifiers(attacker.conditions or []),
        defense_modifiers=svc.get_defense_modifiers(target_conditions),
    )


# ── 玩家战斗行动 ──────────────────────────────────────────
