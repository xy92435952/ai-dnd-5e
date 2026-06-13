"""Combat enemy inspection endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.combat._shared import (
    _assert_expected_turn_token,
    _broadcast_combat,
    _build_combat_snapshot,
    _get_ts,
    _save_ts,
)
from api.combat.schemas import CombatInspectRequest
from api.deps import assert_can_act, assert_character_in_session, get_session_or_404, get_user_id
from database import get_db
from models import Character, CombatState, GameLog
from schemas.ws_events import CombatUpdate
from services.dnd_rules import roll_skill_check
from services.enemy_inspect_service import (
    apply_enemy_inspect_result,
    default_enemy_inspect_dc,
    normalize_inspect_skill,
)

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/inspect")
async def inspect_enemy(
    session_id: str,
    req: CombatInspectRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "Current session is not in combat")
    await assert_can_act(session, user_id, req.character_id, db)

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "Combat state not found")
    _assert_expected_turn_token(combat, req.expected_turn_token, detail_prefix="Inspect")

    character = await db.get(Character, req.character_id)
    if not character:
        raise HTTPException(404, "Character not found")
    await assert_character_in_session(character, session, db)

    state = dict(session.game_state or {})
    enemies = list(state.get("enemies") or [])
    target = next((enemy for enemy in enemies if str(enemy.get("id")) == str(req.target_id)), None)
    if not target:
        raise HTTPException(404, "Enemy not found")

    turn_state = _get_ts(combat, req.character_id)
    if turn_state.get("action_used"):
        raise HTTPException(400, "Action already used")

    skill = normalize_inspect_skill(req.skill)
    dc = req.dc if req.dc is not None else default_enemy_inspect_dc(target)
    check = _roll_inspect_check(character, skill, dc, req.d20_value, req.second_d20_value)

    enemies, inspected_enemy, revealed_stats = apply_enemy_inspect_result(
        enemies,
        req.target_id,
        skill=skill,
        dc=dc,
        check_result=check,
        character_id=character.id,
        character_name=character.name,
    )
    if inspected_enemy is None:
        raise HTTPException(404, "Enemy not found")

    state["enemies"] = enemies
    session.game_state = state
    flag_modified(session, "game_state")

    turn_state["action_used"] = True
    _save_ts(combat, req.character_id, turn_state)

    outcome = "success" if check.get("success") else "failed"
    target_name = inspected_enemy.get("name", "Enemy")
    combat_snapshot = await _build_combat_snapshot(
        db,
        session,
        combat,
        viewer_character_id=req.character_id,
    )
    actor_enemy_snapshot = combat_snapshot.get("entities", {}).get(str(req.target_id))
    session.game_state = state
    flag_modified(session, "game_state")
    inspect_result = {
        "type": "enemy_inspect",
        "actor_id": character.id,
        "actor_name": character.name,
        "target_id": req.target_id,
        "target_name": target_name,
        "skill": skill,
        "dc": dc,
        "check": check,
        "success": bool(check.get("success")),
        "revealed_stats": revealed_stats,
        "enemy": actor_enemy_snapshot,
    }
    narration = f"[Inspect] {character.name} inspected {target_name}: {check['total']} vs DC {dc} ({outcome})"
    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=narration,
        log_type="dice",
        dice_result=inspect_result,
    ))

    await db.commit()
    await db.refresh(session)
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            action="enemy_inspect",
            actor_id=character.id,
            actor_name=character.name,
            narration=narration,
            target_id=req.target_id,
            target_name=target_name,
            inspect_result=inspect_result,
            dice_result=inspect_result,
            special_action=inspect_result,
        ),
        db=db,
    )

    return {
        "action": "enemy_inspect",
        "target_id": req.target_id,
        "target_name": target_name,
        "skill": skill,
        "dc": dc,
        "check": check,
        "success": bool(check.get("success")),
        "revealed_stats": revealed_stats,
        "turn_state": turn_state,
        "enemy": actor_enemy_snapshot,
        "combat": combat_snapshot,
        "inspect_result": inspect_result,
        "dice_result": inspect_result,
        "special_action": inspect_result,
    }


def _roll_inspect_check(
    character: Character,
    skill: str,
    dc: int,
    d20_value: int | None,
    second_d20_value: int | None,
) -> dict:
    result = roll_skill_check(
        character={
            "derived": character.derived or {},
            "proficient_skills": character.proficient_skills or [],
            "conditions": character.conditions or [],
            "condition_durations": character.condition_durations or {},
        },
        skill=skill,
        dc=dc,
    )
    if d20_value is None:
        return result

    modifier = result["modifier"]
    condition_modifier = result.get("condition_modifier", 0) or 0
    d20 = d20_value
    other_roll = None
    if second_d20_value is not None and result.get("advantage") != result.get("disadvantage"):
        if result.get("advantage"):
            d20 = max(d20_value, second_d20_value)
        elif result.get("disadvantage"):
            d20 = min(d20_value, second_d20_value)
        other_roll = second_d20_value if d20 == d20_value else d20_value
    total = d20 + modifier + condition_modifier
    return {
        **result,
        "d20": d20,
        "other_roll": other_roll,
        "total": total,
        "success": total >= dc,
    }
