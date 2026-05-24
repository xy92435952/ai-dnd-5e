from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.deps import assert_session_access, get_authorized_character, get_session_or_404, get_user_id
from api.combat.schemas import ConditionRequest
from database import get_db
from models import GameLog
from schemas.combat_responses import ConditionUpdateResult

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/condition/add", response_model=ConditionUpdateResult)
async def add_condition(
    session_id: str,
    req: ConditionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    state = session.game_state or {}

    if req.is_enemy:
        enemies = list(state.get("enemies", []))
        enemy = next((e for e in enemies if e["id"] == req.entity_id), None)
        if not enemy:
            raise HTTPException(404, f"enemy {req.entity_id} not found")
        conditions = list(enemy.get("conditions", []))
        if req.condition not in conditions:
            conditions.append(req.condition)
        if req.rounds is not None:
            durations = dict(enemy.get("condition_durations", {}))
            durations[req.condition] = req.rounds
            enemy["condition_durations"] = durations
        enemy["conditions"] = conditions
        state["enemies"] = enemies
        session.game_state = dict(state)
        flag_modified(session, "game_state")
    else:
        char = await get_authorized_character(req.entity_id, db, user_id, session_id=session_id)
        conditions = list(char.conditions or [])
        if req.condition not in conditions:
            conditions.append(req.condition)
        char.conditions = conditions
        if req.rounds is not None:
            durations = dict(char.condition_durations or {})
            durations[req.condition] = req.rounds
            char.condition_durations = durations

    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=f"{'enemy' if req.is_enemy else req.entity_id} gains condition: {req.condition}",
        log_type="system",
    ))
    await db.commit()
    return {"entity_id": req.entity_id, "conditions": conditions}


@router.post("/combat/{session_id}/condition/remove", response_model=ConditionUpdateResult)
async def remove_condition(
    session_id: str,
    req: ConditionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    state = session.game_state or {}

    if req.is_enemy:
        enemies = list(state.get("enemies", []))
        enemy = next((e for e in enemies if e["id"] == req.entity_id), None)
        if not enemy:
            raise HTTPException(404, f"enemy {req.entity_id} not found")
        conditions = [c for c in enemy.get("conditions", []) if c != req.condition]
        enemy["conditions"] = conditions
        state["enemies"] = enemies
        session.game_state = dict(state)
        flag_modified(session, "game_state")
    else:
        char = await get_authorized_character(req.entity_id, db, user_id, session_id=session_id)
        conditions = [c for c in (char.conditions or []) if c != req.condition]
        char.conditions = conditions

    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=f"{'enemy' if req.is_enemy else req.entity_id} removes condition: {req.condition}",
        log_type="system",
    ))
    await db.commit()
    return {"entity_id": req.entity_id, "conditions": conditions}
