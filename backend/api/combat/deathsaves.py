"""Death saving throw endpoint."""

import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.combat._shared import _broadcast_combat
from api.combat.schemas import DeathSaveRequest
from api.deps import assert_can_act, get_session_or_404, get_user_id
from database import get_db
from models import Character, CombatState, GameLog
from schemas.combat_responses import DeathSaveResult
from schemas.ws_events import CombatUpdate
from services.dnd_rules import (
    apply_character_healing,
    default_death_saves,
    is_dead,
)

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/death-save", response_model=DeathSaveResult)
async def death_saving_throw(
    session_id: str,
    req: DeathSaveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Resolve a DnD 5e death saving throw for a 0-HP character."""
    session = await get_session_or_404(session_id, db)
    await assert_can_act(session, user_id, req.character_id, db, require_current_turn=False)
    char = await db.get(Character, req.character_id)
    if not char:
        raise HTTPException(404, "Character not found")
    if char.hp_current > 0:
        raise HTTPException(400, "Character has HP above 0 and does not need a death save")

    saves = dict(char.death_saves or default_death_saves())
    if is_dead(char):
        raise HTTPException(400, "Character is dead and needs a resurrection effect")
    if saves.get("stable"):
        raise HTTPException(400, "Character is already stable")

    d20 = req.d20_value if req.d20_value is not None else random.randint(1, 20)

    if d20 == 20:
        apply_character_healing(char, 1)
        saves = char.death_saves or default_death_saves()
        msg = f"{char.name} rolled a natural 20 and regains 1 HP."
        result = {
            "d20": d20,
            "outcome": "revive",
            "hp": char.hp_current,
            "hp_current": char.hp_current,
            "revived": True,
            "dead": False,
            "stable": False,
        }
    elif d20 == 1:
        saves["failures"] = min(3, saves.get("failures", 0) + 2)
        char.death_saves = saves
        if saves["failures"] >= 3:
            msg = f"{char.name} rolled a natural 1 and dies after three failed death saves."
            result = {"d20": d20, "outcome": "dead", "failures": saves["failures"], "dead": True}
        else:
            msg = f"{char.name} rolled a natural 1: two failed death saves ({saves['failures']}/3)."
            result = {"d20": d20, "outcome": "failure", "failures": saves["failures"], "dead": False}
    elif d20 >= 10:
        saves["successes"] = min(3, saves.get("successes", 0) + 1)
        if saves["successes"] >= 3:
            saves["stable"] = True
            msg = f"{char.name} has three successful death saves and is stable."
            result = {
                "d20": d20,
                "outcome": "stable",
                "successes": saves["successes"],
                "stable": True,
                "dead": False,
            }
        else:
            msg = f"{char.name} succeeds on a death save ({saves['successes']}/3)."
            result = {
                "d20": d20,
                "outcome": "success",
                "successes": saves["successes"],
                "stable": False,
                "dead": False,
            }
        char.death_saves = saves
    else:
        saves["failures"] = min(3, saves.get("failures", 0) + 1)
        if saves["failures"] >= 3:
            msg = f"{char.name} has three failed death saves and dies."
            result = {"d20": d20, "outcome": "dead", "failures": saves["failures"], "dead": True}
        else:
            msg = f"{char.name} fails a death save ({saves['failures']}/3)."
            result = {"d20": d20, "outcome": "failure", "failures": saves["failures"], "dead": False}
        char.death_saves = saves

    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=msg,
        log_type="dice",
        dice_result=result,
    ))
    await db.commit()

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if combat:
        await _broadcast_combat(
            session,
            combat,
            CombatUpdate(
                actor_id=str(req.character_id),
                actor_name=char.name,
                narration=msg,
                death_save=result,
            ),
            db=db,
        )

    return {
        "character_id": req.character_id,
        "character_name": char.name,
        "death_saves": saves,
        "hp_current": char.hp_current,
        **result,
    }
