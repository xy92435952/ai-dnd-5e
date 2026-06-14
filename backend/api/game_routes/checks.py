from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_can_act, assert_session_access, get_session_or_404, get_user_id
from database import get_db
from models import Character, GameLog
from schemas.game_requests import SkillCheckRequest
from schemas.game_responses import SkillCheckResult
from services.dnd_rules import roll_skill_check
from services.lucky_feat_service import (
    LuckyFeatError,
    apply_lucky_to_skill_check,
    spend_lucky_point,
)

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/skill-check", response_model=SkillCheckResult)
async def skill_check(
    req: SkillCheckRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """执行技能检定（正确检查角色是否熟练）"""
    session = await get_session_or_404(req.session_id, db)
    await assert_session_access(session, user_id, db)
    character = await db.get(Character, req.character_id)
    if not character:
        raise HTTPException(404, "角色不存在")

    if character.session_id != req.session_id:
        raise HTTPException(403, "瑙掕壊涓嶅睘浜庤浼氳瘽")
    await assert_can_act(
        session,
        user_id,
        req.character_id,
        db,
        require_current_turn=False,
    )

    result = roll_skill_check(
        character={
            "derived": character.derived or {},
            "proficient_skills": character.proficient_skills or [],
            "conditions": character.conditions or [],
            "condition_durations": character.condition_durations or {},
        },
        skill=req.skill,
        dc=req.dc,
    )
    if req.d20_value is not None:
        modifier = result["modifier"]
        condition_modifier = result.get("condition_modifier", 0) or 0
        d20 = req.d20_value
        other_roll = None
        if req.second_d20_value is not None and result.get("advantage") != result.get("disadvantage"):
            if result.get("advantage"):
                d20 = max(req.d20_value, req.second_d20_value)
            elif result.get("disadvantage"):
                d20 = min(req.d20_value, req.second_d20_value)
            other_roll = req.second_d20_value if d20 == req.d20_value else req.d20_value
        total = d20 + modifier + condition_modifier
        result = {
            **result,
            "d20": d20,
            "other_roll": other_roll,
            "total": total,
            "success": total >= req.dc,
        }
    if req.use_lucky:
        try:
            lucky = spend_lucky_point(
                character,
                d20_before=result.get("d20"),
                lucky_d20_value=req.lucky_d20_value,
                context="skill_check",
            )
        except LuckyFeatError as exc:
            raise HTTPException(exc.status_code, exc.detail) from exc
        result = apply_lucky_to_skill_check(result, lucky=lucky, dc=req.dc)

    db.add(GameLog(
        session_id=req.session_id,
        role="system",
        content=(
            f"🎲 {character.name} 进行【{req.skill}】检定 (DC {req.dc})："
            f"d20={result['d20']} {'+' if result['modifier'] >= 0 else ''}{result['modifier']}"
            f" = **{result['total']}** → "
            f"{'✅ 成功' if result['success'] else '❌ 失败'}"
            f"{' [已熟练]' if result['proficient'] else ' [未熟练]'}"
        ),
        log_type="dice",
        dice_result=result,
    ))
    await db.commit()
    return result
