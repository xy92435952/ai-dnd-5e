"""
api.combat.smites — Divine Smite combat endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import CombatState, GameLog
from api.deps import (
    get_session_or_404,
    get_user_id,
    assert_can_act,
    resolve_controlled_player_character,
)
from api.combat._shared import svc
from api.combat.schemas import SmiteRequest
from services.combat_narrator import narrate_action
from services.combat_outcome_service import check_and_cleanup_combat_outcome
from services.dnd_rules import _normalize_class
from schemas.combat_responses import CombatActionResult

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/smite", response_model=CombatActionResult)
async def divine_smite(
    session_id: str,
    req: SmiteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    Paladin Divine Smite -- 成功命中后追加辐光伤害。
    前端在攻击命中后弹出选择，玩家决定消耗法术位。
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    player = await resolve_controlled_player_character(session, user_id, db)
    await assert_can_act(session, user_id, player.id, db)

    p_class = _normalize_class(player.char_class)
    if p_class != "Paladin":
        raise HTTPException(400, "只有圣武士可以使用神圣斩击")

    # 消耗法术位
    slot_key = ["1st", "2nd", "3rd", "4th", "5th"][min(req.slot_level - 1, 4)]
    current_slots = dict(player.spell_slots or {})
    available = current_slots.get(slot_key, 0)
    if available <= 0:
        raise HTTPException(400, f"没有可用的{slot_key}环法术位")
    current_slots[slot_key] = available - 1
    player.spell_slots = current_slots

    # 计算斩击伤害
    smite = svc.calc_divine_smite_damage(req.slot_level, req.target_is_undead)

    # 前端骰子物理结果覆盖
    if req.damage_values:
        smite["damage"] = sum(req.damage_values)

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()

    state   = session.game_state or {}
    enemies = list(state.get("enemies", []))

    # 确定斩击目标：优先用前端传入的 target_id
    smite_target_id = req.target_id
    if not smite_target_id:
        # Fallback：从 pending_attack 或最近日志推断
        if combat:
            all_ts = dict(combat.turn_states or {})
            player_ts = all_ts.get(str(player.id), {})
            smite_target_id = player_ts.get("last_attack_target")
        if not smite_target_id:
            # 最后兜底：第一个存活敌人
            for e in enemies:
                if e.get("hp_current", 0) > 0:
                    smite_target_id = e["id"]
                    break

    # 对目标施加伤害
    target_new_hp = None
    target_name   = "目标"
    smite_applied = False
    for e in enemies:
        if str(e.get("id")) != str(smite_target_id):
            continue
        if e.get("hp_current", 0) <= 0:
            continue
        e["hp_current"] = svc.apply_damage(
            e.get("hp_current", 0), smite["damage"],
            e.get("derived", {}).get("hp_max", 10),
        )
        target_new_hp = e["hp_current"]
        target_name   = e["name"]
        smite_applied = True
        break

    if not smite_applied:
        current_slots[slot_key] = available
        player.spell_slots = current_slots
        raise HTTPException(400, "没有可施加斩击的目标")

    state["enemies"]   = enemies
    session.game_state = dict(state); flag_modified(session, "game_state")

    undead_note = "（对亡灵/邪魔额外+1d8）" if req.target_is_undead else ""
    mechanical_narration = f"✨ {player.name} 释放神圣斩击！{smite['dice']}辐光伤害{undead_note}，对 {target_name} 造成 {smite['damage']} 点伤害！"

    vivid = await narrate_action(
        actor_name=player.name, actor_class=_normalize_class(player.char_class),
        target_name=target_name, action_type="smite",
        damage=smite["damage"], damage_type="辐光",
    )
    narration = vivid if vivid else mechanical_narration

    db.add(GameLog(
        session_id  = session_id,
        role        = "player",
        content     = narration,
        log_type    = "combat",
        dice_result = {"type": "divine_smite", "slot_level": req.slot_level, **smite},
    ))

    combat_over, outcome = await check_and_cleanup_combat_outcome(
        db,
        session=session,
        session_id=session_id,
        enemies=enemies,
        check_combat_over=svc.check_combat_over,
    )

    await db.commit()
    return {
        "action":          "divine_smite",
        "narration":       narration,
        "smite_damage":    smite["damage"],
        "smite_dice":      smite["dice"],
        "target_name":     target_name,
        "target_new_hp":   target_new_hp,
        "remaining_slots": current_slots,
        "combat_over":     combat_over,
        "outcome":         outcome,
    }
