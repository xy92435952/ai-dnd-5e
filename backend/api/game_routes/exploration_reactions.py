from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    assert_can_act,
    assert_session_access,
    char_brief,
    get_session_or_404,
    get_user_id,
)
from database import get_db
from models import Character, GameLog
from schemas.game_requests import ExplorationReactionRequest
from schemas.game_responses import PlayerActionResponse
from services.exploration_reaction_service import (
    pending_exploration_reaction,
    resolve_pending_exploration_reaction,
    user_can_answer_exploration_reaction,
)
from services.state_applicator import StateApplicator


router = APIRouter(prefix="/game", tags=["game"])


@router.post(
    "/sessions/{session_id}/exploration-reaction",
    response_model=PlayerActionResponse,
)
async def use_exploration_reaction(
    session_id: str,
    req: ExplorationReactionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_session_or_404(session_id, db)
    member = await assert_session_access(session, user_id, db)
    pending = pending_exploration_reaction(session)
    if not pending:
        raise HTTPException(409, "No pending exploration reaction")

    controlled_character_id = (
        member.character_id
        if member and member.character_id
        else session.player_character_id
    )
    if not user_can_answer_exploration_reaction(
        pending,
        user_id=user_id,
        character_id=controlled_character_id,
        session=session,
    ):
        raise HTTPException(403, "Only the prompted character can answer this reaction")

    reactor_id = str(pending.get("reactor_character_id") or "")
    if req.character_id and str(req.character_id) != reactor_id:
        raise HTTPException(400, "Reaction character does not match the pending prompt")

    reactor = await db.get(Character, reactor_id)
    target = await db.get(Character, str(pending.get("target_character_id") or ""))
    if not reactor or not target:
        raise HTTPException(404, "Pending reaction character no longer exists")

    await assert_can_act(
        session,
        user_id,
        reactor.id,
        db,
        require_current_turn=False,
    )

    accept = req.reaction_type == "feather_fall"
    try:
        result = resolve_pending_exploration_reaction(
            session=session,
            reactor=reactor,
            target=target,
            accept=accept,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    applicator = StateApplicator(db)
    dice_display = applicator._trap_dice_display(result)
    applicator._record_trap_trigger_state(session, result)

    narrative = _reaction_narrative(
        result,
        reactor_name=reactor.name,
        target_name=target.name,
        accepted=accept,
    )
    db.add(GameLog(
        session_id=session.id,
        role="system",
        content=narrative,
        log_type="narrative",
        dice_result=dice_display or None,
    ))
    await db.commit()

    if session.is_multiplayer:
        await _broadcast_exploration_reaction_result(
            db=db,
            session=session,
            actor_user_id=user_id,
            trigger_actor_user_id=pending.get("trigger_actor_user_id"),
            narrative=narrative,
            dice_display=dice_display,
        )

    reaction_effect = result.get("feather_fall") or result.get("reaction_declined")
    return {
        "type": "exploration_reaction",
        "action": "reaction" if accept else "reaction_declined",
        "reaction_type": "feather_fall",
        "narrative": narrative,
        "companion_reactions": "",
        "dice_display": dice_display,
        "player_choices": [],
        "needs_check": {"required": False},
        "combat_triggered": False,
        "combat_ended": False,
        "combat_end_result": None,
        "combat_update": None,
        "reaction_effect": reaction_effect,
        "target_state": result.get("target_state"),
        "caster_state": char_brief(reactor),
        "exploration_reaction_prompt": None,
        "errors": [],
    }


def _reaction_narrative(
    result: dict,
    *,
    reactor_name: str,
    target_name: str,
    accepted: bool,
) -> str:
    trap_name = result.get("name") or result.get("trap_id") or "the trap"
    if accepted:
        prevented = (result.get("feather_fall") or {}).get("damage_prevented", 0)
        return (
            f"{reactor_name} casts Feather Fall as {target_name} drops through "
            f"{trap_name}, preventing {prevented} fall damage."
        )
    damage = int(result.get("final_damage") or 0)
    return (
        f"{reactor_name} lets the Feather Fall window pass; "
        f"{trap_name} deals {damage} damage to {target_name}."
    )


async def _broadcast_exploration_reaction_result(
    *,
    db: AsyncSession,
    session,
    actor_user_id: str,
    trigger_actor_user_id: str | None,
    narrative: str,
    dice_display: list,
) -> None:
    from api.ws import _advance_speaker
    from schemas.ws_events import DMResponded, DMSpeakTurn, RoomStateUpdated
    from services import room_service
    from services.ws_manager import ws_manager

    try:
        await ws_manager.broadcast(
            session.id,
            DMResponded(
                by_user_id=actor_user_id,
                action_type="exploration_reaction",
                narrative=narrative,
                companion_reactions="",
                dice_display=dice_display or [],
                combat_triggered=False,
                combat_ended=False,
            ),
        )
    except Exception:
        pass

    next_user = await _advance_speaker(
        db,
        session.id,
        str(trigger_actor_user_id or actor_user_id),
    )
    if not next_user:
        return
    try:
        await ws_manager.broadcast(session.id, DMSpeakTurn(user_id=next_user, auto=True))
        room_info = await room_service.get_room_info(db, session.id)
        await ws_manager.broadcast(session.id, RoomStateUpdated(room=room_info))
    except Exception:
        pass
