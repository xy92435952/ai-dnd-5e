from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Character, GameLog
from schemas.game_requests import SkillCheckRequest
from schemas.game_responses import SkillCheckResult
from services.dnd_rules import roll_skill_check

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/skill-check", response_model=SkillCheckResult)
async def skill_check(req: SkillCheckRequest, db: AsyncSession = Depends(get_db)):
    """执行技能检定（正确检查角色是否熟练）"""
    character = await db.get(Character, req.character_id)
    if not character:
        raise HTTPException(404, "角色不存在")

    result = roll_skill_check(
        character={
            "derived": character.derived,
            "proficient_skills": character.proficient_skills or [],
        },
        skill=req.skill,
        dc=req.dc,
    )
    if req.d20_value is not None:
        modifier = result["modifier"]
        total = req.d20_value + modifier
        result = {
            **result,
            "d20": req.d20_value,
            "total": total,
            "success": total >= req.dc,
        }

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
