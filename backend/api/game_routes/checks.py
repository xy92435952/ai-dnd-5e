from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_character_control, get_authorized_session, get_user_id
from database import get_db
from models import Character, GameLog
from schemas.game_requests import SavingThrowRequest, SkillCheckRequest
from schemas.game_responses import SavingThrowResult, SkillCheckResult
from services.dnd_rules import roll_saving_throw, roll_skill_check

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/skill-check", response_model=SkillCheckResult)
async def skill_check(
    req: SkillCheckRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_authorized_session(req.session_id, db, user_id)
    character = await db.get(Character, req.character_id)
    if not character:
        raise HTTPException(404, "character not found")
    if character.session_id != req.session_id and session.player_character_id != character.id:
        raise HTTPException(403, "character does not belong to this session")
    await assert_character_control(character, session, user_id, db)

    result = roll_skill_check(
        character={
            "derived": character.derived,
            "proficient_skills": character.proficient_skills or [],
        },
        skill=req.skill,
        dc=req.dc,
        advantage=req.advantage,
        disadvantage=req.disadvantage,
    )
    if req.d20_value is not None:
        advantage = bool(req.advantage and not req.disadvantage)
        disadvantage = bool(req.disadvantage and not req.advantage)
        modifier = result["modifier"]
        total = req.d20_value + modifier
        result = {
            **result,
            "d20": req.d20_value,
            "advantage": advantage,
            "disadvantage": disadvantage,
            "total": total,
            "success": total >= req.dc,
        }

    db.add(GameLog(
        session_id=req.session_id,
        role="system",
        content=(
            f"{character.name} skill check [{req.skill}] DC {req.dc}: "
            f"d20={result['d20']} {'+' if result['modifier'] >= 0 else ''}{result['modifier']} "
            f"= {result['total']} -> {'success' if result['success'] else 'failure'}"
        ),
        log_type="dice",
        dice_result=result,
    ))
    await db.commit()
    return result


@router.post("/saving-throw", response_model=SavingThrowResult)
async def saving_throw(
    req: SavingThrowRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_authorized_session(req.session_id, db, user_id)
    character = await db.get(Character, req.character_id)
    if not character:
        raise HTTPException(404, "character not found")
    if character.session_id != req.session_id and session.player_character_id != character.id:
        raise HTTPException(403, "character does not belong to this session")
    await assert_character_control(character, session, user_id, db)

    result = roll_saving_throw(
        character={
            "derived": character.derived or {},
            "proficient_saves": character.proficient_saves or [],
        },
        ability=req.ability,
        dc=req.dc,
        advantage=req.advantage,
        disadvantage=req.disadvantage,
    )
    if req.d20_value is not None:
        advantage = bool(req.advantage and not req.disadvantage)
        disadvantage = bool(req.disadvantage and not req.advantage)
        modifier = result["modifier"]
        total = req.d20_value + modifier
        result = {
            **result,
            "d20": req.d20_value,
            "advantage": advantage,
            "disadvantage": disadvantage,
            "total": total,
            "success": total >= req.dc,
        }

    db.add(GameLog(
        session_id=req.session_id,
        role="system",
        content=(
            f"{character.name} saving throw [{req.ability}] DC {req.dc}: "
            f"d20={result['d20']} {'+' if result['modifier'] >= 0 else ''}{result['modifier']} "
            f"= {result['total']} -> {'success' if result['success'] else 'failure'}"
        ),
        log_type="dice",
        dice_result=result,
    ))
    await db.commit()
    return result
