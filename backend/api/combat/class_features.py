"""
api.combat.class_features — combat class feature endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Character, CombatState, GameLog
from api.deps import (
    assert_can_act,
    assert_character_can_act,
    assert_optional_session_access,
    get_optional_user_id,
    get_session_or_404,
)
from api.combat._shared import _broadcast_combat, _get_ts, svc
from api.combat.schemas import ClassFeatureRequest
from services.combat_class_feature_service import (
    CombatClassFeatureError,
    resolve_combat_class_feature,
)
from services.combat_narrator import narrate_action
from services.dnd_rules import roll_dice
from schemas.combat_responses import CombatActionResult
from schemas.ws_events import CombatUpdate

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/class-feature", response_model=CombatActionResult)
async def use_class_feature(
    session_id: str,
    req: ClassFeatureRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    使用职业战斗特性：
    - second_wind:  Fighter 1+, 恢复 1d10+level HP, 附赠行动, 每短休1次
    - action_surge: Fighter 2+, 本回合获得额外行动, 每短休1次
    - rage:         Barbarian 1+, 进入/退出狂暴, 附赠行动
    - cunning_action_dash: Rogue 2+, 附赠行动冲刺
    - cunning_action_disengage: Rogue 2+, 附赠行动脱离
    - cunning_action_hide: Rogue 2+, 附赠行动隐匿
    """
    session = await get_session_or_404(session_id, db)
    await assert_optional_session_access(session, user_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    player = await db.get(Character, session.player_character_id)
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    player_id = session.player_character_id
    if session.is_multiplayer and combat.turn_order:
        try:
            current = combat.turn_order[combat.current_turn_index or 0]
            current_id = current.get("character_id") if isinstance(current, dict) else None
            if current_id:
                player_id = current_id
        except (IndexError, AttributeError):
            pass
    if user_id:
        await assert_can_act(session, user_id, player_id, db)
    else:
        await assert_character_can_act(player_id, db)
    if player_id != session.player_character_id:
        player = await db.get(Character, player_id)
        if not player:
            raise HTTPException(404, "Player character not found")

    turn_state = _get_ts(combat, player_id)
    try:
        result = resolve_combat_class_feature(
            feature=req.feature_name,
            player=player,
            player_id=player_id,
            combat=combat,
            turn_state=turn_state,
            combat_service=svc,
            roll_dice_fn=roll_dice,
        )
    except CombatClassFeatureError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    narration = result.narration
    vivid = await narrate_action(
        actor_name=player.name,
        actor_class=result.character_class,
        target_name="",
        action_type="class_feature",
        extra_details=narration,
    )
    if vivid:
        narration = vivid

    db.add(GameLog(
        session_id=session_id,
        role="player",
        content=narration,
        log_type="combat",
        dice_result={"type": "class_feature", "feature": req.feature_name},
    ))
    await db.commit()
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            actor_id=str(player_id),
            actor_name=player.name,
            narration=narration,
            feature=req.feature_name,
        ),
        db=db,
    )

    return {
        "action": "class_feature",
        "feature": req.feature_name,
        "narration": narration,
        "turn_state": result.turn_state,
        "class_resources": result.class_resources,
        "hp_current": player.hp_current,
        "temporary_hp": result.temporary_hp,
        "hp_max": result.hp_max,
        "dice_roll": result.dice_roll,
    }
