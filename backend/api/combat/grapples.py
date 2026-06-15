"""
api.combat.grapples — Grapple and shove combat endpoint.
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
from api.combat._shared import _broadcast_combat
from api.combat.schemas import GrappleEscapeRequest, GrappleShoveRequest
from schemas.combat_responses import CombatActionResult
from schemas.ws_events import CombatUpdate
from services.combat_action_rules_service import CombatActionRuleError, validate_can_take_reaction
from services.combat_grapple_service import CombatGrappleError, resolve_grapple_shove
from services.combat_reaction_service import (
    CuttingWordsError,
    calculate_cutting_words_ability_check_prevention,
    spend_cutting_words_resource,
)
from services.combat_turn_state_service import get_turn_state, save_turn_state
from services.dnd_rules import get_life_state, roll_skill_check

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/grapple-shove", response_model=CombatActionResult)
async def grapple_shove(
    session_id: str,
    req: GrappleShoveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    Grapple or Shove action. Replaces one attack.
    Grapple: contested Athletics check, success → target grappled (speed=0)
    Shove: contested Athletics check, success → target prone or pushed 5ft
    """
    session = await get_session_or_404(session_id, db)
    await assert_optional_session_access(session, user_id, db)
    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if combat and combat.turn_order:
        try:
            current = combat.turn_order[combat.current_turn_index or 0]
            actor_id = current.get("character_id") if isinstance(current, dict) else None
            if actor_id:
                if user_id:
                    await assert_can_act(session, user_id, actor_id, db)
                else:
                    await assert_character_can_act(actor_id, db)
        except (IndexError, AttributeError):
            pass

    try:
        result = await resolve_grapple_shove(
            db,
            session=session,
            combat=combat,
            action_type=req.action_type,
            target_id=req.target_id,
            shove_type=req.shove_type,
            use_cutting_words=bool(req.use_cutting_words),
            cutting_words_roll=req.cutting_words_roll,
        )
    except CombatGrappleError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    db.add(GameLog(
        session_id=session_id,
        role="player",
        content=result.narration,
        log_type="combat",
        dice_result=result.log_dice_result,
    ))
    await db.commit()
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            actor_id=result.payload.get("actor_id"),
            actor_name=result.payload.get("actor_name"),
            narration=result.narration,
            action=req.action_type,
            target_id=result.payload.get("target_id"),
            target_name=result.payload.get("target_name"),
            target_state=result.payload.get("target_state"),
            condition_result=result.payload.get("condition_result"),
            dice_result=result.payload.get("dice_result"),
            special_action=result.payload.get("special_action"),
        ),
        db=db,
    )
    return result.payload


@router.post("/combat/{session_id}/grapple-escape", response_model=CombatActionResult)
async def grapple_escape(
    session_id: str,
    req: GrappleEscapeRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """Escape an active grapple with a contested Athletics/Acrobatics check."""
    session = await get_session_or_404(session_id, db)
    await assert_optional_session_access(session, user_id, db)
    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat or not combat.turn_order:
        raise HTTPException(404, "Combat state not found")

    current = combat.turn_order[combat.current_turn_index or 0]
    actor_id = current.get("character_id") if isinstance(current, dict) else None
    if not actor_id:
        raise HTTPException(400, "Current turn actor is missing")
    if user_id:
        await assert_can_act(session, user_id, actor_id, db)
    else:
        await assert_character_can_act(actor_id, db)

    actor = await db.get(Character, actor_id)
    if not actor:
        raise HTTPException(404, "Character not found")
    conditions = list(actor.conditions or [])
    if "grappled" not in conditions:
        raise HTTPException(400, "Character is not grappled")

    source_id = req.source_id or ((actor.condition_durations or {}).get("grappled") or {}).get("source_id")
    source = await _resolve_escape_source(db, session=session, source_id=source_id)
    skill = _escape_skill(actor, req.skill)
    actor_roll = roll_skill_check(
        {
            "derived": actor.derived or {},
            "proficient_skills": actor.proficient_skills or [],
            "conditions": actor.conditions or [],
            "condition_durations": actor.condition_durations or {},
        },
        "Acrobatics" if skill == "acrobatics" else "Athletics",
        dc=0,
    )
    source_roll = roll_skill_check(
        {
            "derived": source.get("derived") or {},
            "proficient_skills": source.get("skills") or [],
            "conditions": source.get("conditions") or [],
            "condition_durations": source.get("condition_durations") or {},
        },
        "Athletics",
        dc=0,
    )
    cutting_words_spend = None
    if req.use_cutting_words:
        try:
            validate_can_take_reaction(actor)
        except CombatActionRuleError as exc:
            raise HTTPException(exc.status_code, exc.detail) from exc
        try:
            cutting_words_spend = spend_cutting_words_resource(
                actor,
                cutting_words_roll=req.cutting_words_roll,
            )
        except CuttingWordsError as exc:
            raise HTTPException(400, str(exc)) from exc
    cutting_words_result = None
    if cutting_words_spend:
        cutting_check = calculate_cutting_words_ability_check_prevention(
            source_roll,
            cutting_words_roll=cutting_words_spend["roll"],
        )
        source_roll = dict(source_roll)
        source_roll["total_before_cutting_words"] = cutting_check["check_total_before"]
        source_roll["total"] = cutting_check["check_total_after"]
        source_roll["cutting_words"] = {
            **cutting_words_spend,
            "context": "ability_check",
        }
        cutting_words_result = {
            **cutting_words_spend,
            "context": "ability_check",
            "source_id": source_id,
            "source_name": source.get("name"),
            **cutting_check,
            "class_resources": actor.class_resources or {},
        }
    escaped = actor_roll["total"] >= source_roll["total"]
    if escaped:
        actor.conditions = [condition for condition in conditions if condition != "grappled"]
        durations = dict(actor.condition_durations or {})
        durations.pop("grappled", None)
        actor.condition_durations = durations

    turn_state = get_turn_state(combat, actor_id)
    if cutting_words_result:
        turn_state["reaction_used"] = True
    turn_state["action_used"] = True
    save_turn_state(combat, actor_id, turn_state)

    target_state = _character_target_state(actor, actor_id)
    condition_result = {
        "condition": "grappled",
        "removed": bool(escaped),
        "applied": False,
        "source_id": source_id,
        "source_name": source.get("name"),
    }
    dice_result = {
        "type": "grapple_escape",
        "success": bool(escaped),
        "skill": skill,
        "actor_roll": actor_roll,
        "source_roll": source_roll,
        "target_id": actor_id,
        "target_name": actor.name,
        "source_id": source_id,
        "source_name": source.get("name"),
        "target_state": target_state,
        "condition_result": condition_result,
    }
    if cutting_words_result:
        dice_result["cutting_words"] = cutting_words_result
    narration = (
        f"{actor.name} escapes the grapple."
        if escaped
        else f"{actor.name} fails to escape the grapple."
    )
    if cutting_words_result:
        narration += (
            f" Cutting Words reduces {source.get('name') or 'the grappler'}'s check from "
            f"{cutting_words_result['check_total_before']} to {cutting_words_result['check_total_after']}."
        )
    payload = {
        "action": "grapple_escape",
        "success": bool(escaped),
        "narration": narration,
        "actor_id": actor_id,
        "actor_name": actor.name,
        "actor_roll": actor_roll,
        "source_roll": source_roll,
        "target_id": actor_id,
        "target_name": actor.name,
        "source_id": source_id,
        "source_name": source.get("name"),
        "target_state": target_state,
        "condition_result": condition_result,
        "dice_result": dice_result,
        "special_action": dice_result,
        "turn_state": turn_state,
        "combat_over": False,
        "outcome": None,
    }
    if cutting_words_result:
        payload["cutting_words"] = cutting_words_result
        payload["class_resources"] = actor.class_resources or {}

    db.add(GameLog(
        session_id=session_id,
        role="player",
        content=narration,
        log_type="combat",
        dice_result=dice_result,
    ))
    await db.commit()
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            actor_id=actor_id,
            actor_name=actor.name,
            narration=narration,
            action="grapple_escape",
            target_id=actor_id,
            target_name=actor.name,
            source_id=source_id,
            source_name=source.get("name"),
            target_state=target_state,
            condition_result=condition_result,
            dice_result=dice_result,
            special_action=dice_result,
        ),
        db=db,
    )
    return payload


async def _resolve_escape_source(db, *, session, source_id: str | None) -> dict:
    state = session.game_state or {}
    for enemy in state.get("enemies", []) or []:
        if str(enemy.get("id")) == str(source_id):
            return {
                "id": source_id,
                "name": enemy.get("name", "Enemy"),
                "derived": enemy.get("derived") or {},
                "skills": enemy.get("proficient_skills") or [],
                "conditions": enemy.get("conditions") or [],
                "condition_durations": enemy.get("condition_durations") or {},
            }
    if source_id:
        source_char = await db.get(Character, source_id)
        if source_char:
            return {
                "id": source_id,
                "name": source_char.name,
                "derived": source_char.derived or {},
                "skills": source_char.proficient_skills or [],
                "conditions": source_char.conditions or [],
                "condition_durations": source_char.condition_durations or {},
            }
    return {"id": source_id, "name": None, "derived": {}, "skills": []}


def _escape_skill(actor: Character, requested: str | None) -> str:
    clean = (requested or "").strip().lower()
    if clean in {"athletics", "acrobatics"}:
        return clean
    derived = actor.derived or {}
    mods = derived.get("ability_modifiers") or {}
    proficiency = derived.get("proficiency_bonus", 2)
    skills = set(actor.proficient_skills or [])
    athletics = mods.get("str", 0) + (proficiency if "Athletics" in skills or "运动" in skills else 0)
    acrobatics = mods.get("dex", 0) + (proficiency if "Acrobatics" in skills or "杂技" in skills else 0)
    return "acrobatics" if acrobatics > athletics else "athletics"


def _character_target_state(actor: Character, actor_id: str) -> dict:
    return {
        "target_id": actor_id,
        "target_name": actor.name,
        "hp_current": actor.hp_current,
        "hp_max": (actor.derived or {}).get("hp_max"),
        "conditions": list(actor.conditions or []),
        "condition_durations": dict(actor.condition_durations or {}),
        "life_state": get_life_state(actor),
        "is_enemy": False,
    }
