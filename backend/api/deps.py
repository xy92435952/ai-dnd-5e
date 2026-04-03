"""
共享依赖与辅助函数
game.py 和 combat.py 共同使用
"""
from fastapi import HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import Session, Character, GameLog, CombatState


# ── JWT 鉴权依赖 ─────────────────────────────────────

async def get_current_user(request: Request) -> dict:
    """从 Authorization header 解析当前用户。所有需要鉴权的端点使用此依赖。"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "未登录，请先登录")
    token = auth_header[7:]
    from api.auth import decode_token
    return decode_token(token)


def get_user_id(user: dict = Depends(get_current_user)) -> str:
    """快捷依赖：只返回 user_id 字符串。"""
    return user["user_id"]


async def get_session_or_404(session_id: str, db: AsyncSession) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "会话不存在")
    return session


def char_brief(char: Character) -> dict:
    """返回角色的简要信息（用于 DM 上下文构建）"""
    derived = char.derived or {}
    return {
        "id":               char.id,
        "name":             char.name,
        "race":             char.race,
        "char_class":       char.char_class,
        "level":            char.level,
        "hp_current":       char.hp_current,
        "hp_max":           derived.get("hp_max", char.hp_current),
        "ac":               derived.get("ac", 10),
        "is_player":        char.is_player,
        "spell_slots":      char.spell_slots or {},
        "proficient_skills":char.proficient_skills or [],
        "proficient_saves": char.proficient_saves or [],
        "conditions":       char.conditions or [],
        "derived":          derived,
        "concentration":    char.concentration,
        "known_spells":     char.known_spells or [],
        "cantrips":         char.cantrips or [],
        "equipment":        char.equipment or {},
        "fighting_style":   char.fighting_style,
    }


def entity_snapshot(char: Character, is_enemy: bool = False) -> dict:
    """战斗地图上的实体快照"""
    derived = char.derived or {}
    return {
        "id":         char.id,
        "name":       char.name,
        "is_player":  char.is_player and not is_enemy,
        "is_enemy":   is_enemy,
        "hp_current": char.hp_current,
        "hp_max":     derived.get("hp_max", char.hp_current),
        "ac":         derived.get("ac", 10),
        "conditions": char.conditions or [],
        "derived":    derived,
    }


def serialize_combat(combat: CombatState) -> dict:
    return {
        "session_id":        combat.session_id,
        "turn_order":        combat.turn_order or [],
        "current_turn_index":combat.current_turn_index,
        "round_number":      combat.round_number,
        "entity_positions":  combat.entity_positions or {},
        "grid_data":         combat.grid_data or {},
    }


def serialize_log(log: GameLog) -> dict:
    return {
        "id":          log.id,
        "role":        log.role,
        "content":     log.content,
        "log_type":    log.log_type,
        "dice_result": log.dice_result,
        "created_at":  log.created_at.isoformat() if log.created_at else None,
    }
