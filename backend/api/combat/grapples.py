"""
api.combat.grapples — Grapple and shove combat endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, CombatState, GameLog
from api.deps import get_session_or_404
from api.combat._shared import _get_ts, _save_ts, svc
from api.combat.schemas import GrappleShoveRequest
from services.combat_narrator import narrate_action
from services.dnd_rules import _normalize_class
from schemas.combat_responses import CombatActionResult

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/grapple-shove", response_model=CombatActionResult)
async def grapple_shove(
    session_id: str,
    req: GrappleShoveRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Grapple or Shove action. Replaces one attack.
    Grapple: contested Athletics check, success → target grappled (speed=0)
    Shove: contested Athletics check, success → target prone or pushed 5ft
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    player = await db.get(Character, session.player_character_id)
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    player_id = session.player_character_id
    ts = _get_ts(combat, player_id)

    # Uses one attack (or the action if no attacks remain)
    max_attacks = svc.get_attack_count(player.derived or {}, player.level, _normalize_class(player.char_class))
    ts.setdefault("attacks_made", 0)
    ts["attacks_max"] = max_attacks
    if ts["attacks_made"] >= max_attacks:
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        raise HTTPException(400, "本回合攻击次数已达上限")

    state = session.game_state or {}
    enemies = list(state.get("enemies", []))

    # Get target
    target_name = ""
    target_derived = {}
    target_is_enemy = False
    target_skills = []

    tchar = await db.get(Character, req.target_id)
    if tchar:
        target_name = tchar.name
        target_derived = tchar.derived or {}
        target_skills = tchar.proficient_skills or []
    else:
        enemy = next((e for e in enemies if e["id"] == req.target_id), None)
        if enemy:
            target_name = enemy["name"]
            target_derived = enemy.get("derived", {})
            target_is_enemy = True

    if not target_name:
        raise HTTPException(404, "目标不存在")

    p_derived = player.derived or {}
    p_skills = player.proficient_skills or []

    if req.action_type == "grapple":
        result = svc.resolve_grapple(p_derived, target_derived, p_skills, target_skills)
        if result["success"]:
            # Apply grappled condition
            if target_is_enemy:
                for e in enemies:
                    if e["id"] == req.target_id:
                        conds = list(e.get("conditions", []))
                        if "grappled" not in conds:
                            conds.append("grappled")
                        e["conditions"] = conds
                state["enemies"] = enemies
                session.game_state = dict(state); flag_modified(session, "game_state")
            else:
                conds = list(tchar.conditions or [])
                if "grappled" not in conds:
                    conds.append("grappled")
                tchar.conditions = conds

            narration = f"🤼 {player.name} 成功擒抱 {target_name}！{target_name} 速度降为0！"
        else:
            narration = f"🤼 {player.name} 尝试擒抱 {target_name}，但失败了！"

    elif req.action_type == "shove":
        result = svc.resolve_shove(p_derived, target_derived, p_skills, target_skills, req.shove_type)
        if result["success"]:
            if req.shove_type == "prone":
                if target_is_enemy:
                    for e in enemies:
                        if e["id"] == req.target_id:
                            conds = list(e.get("conditions", []))
                            if "prone" not in conds:
                                conds.append("prone")
                            e["conditions"] = conds
                    state["enemies"] = enemies
                    session.game_state = dict(state); flag_modified(session, "game_state")
                else:
                    conds = list(tchar.conditions or [])
                    if "prone" not in conds:
                        conds.append("prone")
                    tchar.conditions = conds
                narration = f"💥 {player.name} 成功推倒 {target_name}！{target_name} 陷入倒地状态！"
            else:
                # Push 5ft away
                positions = dict(combat.entity_positions or {})
                p_pos = positions.get(str(player_id))
                t_pos = positions.get(str(req.target_id))
                if p_pos and t_pos:
                    dx = t_pos["x"] - p_pos["x"]
                    dy = t_pos["y"] - p_pos["y"]
                    # Normalize direction and push 1 tile
                    push_x = t_pos["x"] + (1 if dx > 0 else (-1 if dx < 0 else 0))
                    push_y = t_pos["y"] + (1 if dy > 0 else (-1 if dy < 0 else 0))
                    push_x = max(0, min(19, push_x))
                    push_y = max(0, min(11, push_y))
                    positions[str(req.target_id)] = {"x": push_x, "y": push_y}
                    combat.entity_positions = positions; flag_modified(combat, "entity_positions")
                narration = f"💥 {player.name} 推开 {target_name}！{target_name} 被推后5英尺！"
        else:
            narration = f"💥 {player.name} 尝试推撞 {target_name}，但失败了！"
    else:
        raise HTTPException(400, f"未知动作类型：{req.action_type}")

    # Count as one attack
    ts["attacks_made"] = ts.get("attacks_made", 0) + 1
    if ts["attacks_made"] >= max_attacks:
        ts["action_used"] = True
    _save_ts(combat, player_id, ts)

    # LLM vivid narration for grapple/shove
    vivid = await narrate_action(
        actor_name=player.name, actor_class=_normalize_class(player.char_class),
        target_name=target_name, action_type=req.action_type,
        hit=result["success"],
    )
    if vivid:
        narration = vivid

    db.add(GameLog(
        session_id=session_id, role="player",
        content=narration, log_type="combat",
        dice_result={
            "type": req.action_type,
            "success": result["success"],
            "attacker_roll": result["attacker_roll"],
            "target_roll": result["target_roll"],
        },
    ))
    await db.commit()

    return {
        "action": req.action_type,
        "success": result["success"],
        "narration": narration,
        "attacker_roll": result["attacker_roll"],
        "target_roll": result["target_roll"],
        "turn_state": ts,
        "combat_over": False,
        "outcome": None,
    }
