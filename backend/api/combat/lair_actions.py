"""Combat Lair Action endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.combat._shared import (
    _assert_ai_combat_driver,
    _broadcast_combat,
    _build_combat_snapshot,
    _clear_active_ai_control_prompt,
)
from api.combat.legendary_actions import _normalize_target_ids, _resolve_legendary_action_effect
from api.deps import assert_session_access, get_session_or_404, get_user_id
from database import get_db
from models import CombatState, GameLog
from schemas.combat_responses import CombatActionResult
from schemas.ws_events import CombatUpdate
from services.combat_legendary_action_service import find_lair_action

router = APIRouter(prefix="/game", tags=["combat"])


class LairActionRequest(BaseModel):
    source_id: str | None = None
    action_id: str | None = None
    target_id: str | None = None
    target_ids: list[str] | None = None


@router.post("/combat/{session_id}/lair-action", response_model=CombatActionResult)
async def use_lair_action(
    session_id: str,
    req: LairActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Resolve a round-start Lair Action window once per combat round."""
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    await _assert_ai_combat_driver(db, session, user_id)
    if not session.combat_active:
        raise HTTPException(400, "Current session is not in combat")

    combat_result = await db.execute(
        select(CombatState)
        .where(CombatState.session_id == session_id)
        .order_by(CombatState.created_at.desc())
    )
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "Combat state not found")

    round_number = int(combat.round_number or 1)
    state = dict(session.game_state or {})
    if int(state.get("lair_action_used_round", 0) or 0) == round_number:
        raise HTTPException(400, "Lair Action has already been used this round")

    enemies = list(state.get("enemies") or [])
    found = find_lair_action(
        state,
        enemies,
        source_id=req.source_id,
        action_id=req.action_id,
    )
    if not found:
        raise HTTPException(404, "Lair Action not found")

    source = found["source"]
    action = found["action"]
    source_id = str(source.get("id") or req.source_id or "lair")
    source_name = str(source.get("name") or "Lair")
    action_name = str(action.get("name") or "Lair Action")
    description = str(action.get("description") or action.get("effect") or "").strip()
    target_ids = _lair_action_target_ids(req, action)

    effect = await _resolve_legendary_action_effect(
        db,
        session=session,
        session_id=session_id,
        combat=combat,
        actor=source,
        enemies=enemies,
        action=action,
        target_id=target_ids[0] if target_ids else None,
        target_ids=target_ids,
    )

    state["lair_action_used_round"] = round_number
    state["enemies"] = enemies
    session.game_state = state
    flag_modified(session, "game_state")
    _clear_active_ai_control_prompt(session)

    narration = _build_lair_action_narration(
        source_name=source_name,
        action_name=action_name,
        description=description,
        effect=effect,
    )
    target_state = effect.get("target_state")
    dice_result = {
        "type": "lair_action",
        "source_id": source_id,
        "source_name": source_name,
        "actor_id": source_id,
        "actor_name": source_name,
        "action_id": action.get("id"),
        "action_name": action_name,
        "round_number": round_number,
        "description": description,
        **effect.get("dice_result", {}),
    }
    if effect.get("target_id"):
        dice_result["target_id"] = effect["target_id"]
        dice_result["target_name"] = effect.get("target_name")

    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=narration,
        log_type="combat",
        dice_result=dice_result,
    ))
    if effect.get("concentration_log"):
        db.add(effect["concentration_log"])
    for concentration_log in effect.get("concentration_logs") or []:
        if concentration_log and concentration_log is not effect.get("concentration_log"):
            db.add(concentration_log)

    await db.commit()
    await db.refresh(session)

    combat_snapshot = await _build_combat_snapshot(db, session, combat)
    response_fields = effect.get("response", {})
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            combat=combat_snapshot,
            actor_id=source_id,
            actor_name=source_name,
            narration=narration,
            action="lair_action",
            lair_action=dice_result,
            target_id=effect.get("target_id"),
            target_name=effect.get("target_name"),
            target_new_hp=effect.get("target_new_hp"),
            target_state=target_state,
            player_targeted=response_fields.get("player_targeted", False),
            player_can_react=response_fields.get("player_can_react", False),
            reaction_prompt=response_fields.get("reaction_prompt"),
            save=response_fields.get("save"),
            damage=response_fields.get("damage"),
            total_damage=response_fields.get("total_damage"),
            damage_roll=response_fields.get("damage_roll"),
            damage_type=response_fields.get("damage_type"),
            target_results=response_fields.get("target_results") or [],
            aoe_results=response_fields.get("aoe_results") or [],
            concentration_check=response_fields.get("concentration_check"),
            concentration_checks=response_fields.get("concentration_checks") or [],
            concentration_effect_updates=response_fields.get("concentration_effect_updates") or [],
            dice_result=dice_result,
            special_action=dice_result,
        ),
        db=db,
    )

    response = {
        "success": True,
        "action": "lair_action",
        "actor_id": source_id,
        "actor_name": source_name,
        "source_id": source_id,
        "source_name": source_name,
        "round_number": round_number,
        "target_id": effect.get("target_id"),
        "target_name": effect.get("target_name"),
        "hp_before": effect.get("hp_before"),
        "target_new_hp": effect.get("target_new_hp"),
        "narration": narration,
        "log_msg": narration,
        "dice_result": dice_result,
        "special_action": dice_result,
        "target_state": target_state,
        "combat": combat_snapshot,
        "lair_action": dice_result,
    }
    response.update(effect.get("response", {}))
    return response


@router.post("/combat/{session_id}/lair-action/skip", response_model=CombatActionResult)
async def skip_lair_action(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Persistently skip the active Lair Action window without applying effects."""
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    await _assert_ai_combat_driver(db, session, user_id)
    if not session.combat_active:
        raise HTTPException(400, "Current session is not in combat")

    combat_result = await db.execute(
        select(CombatState)
        .where(CombatState.session_id == session_id)
        .order_by(CombatState.created_at.desc())
    )
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "Combat state not found")

    _clear_active_ai_control_prompt(session)
    await db.commit()
    await db.refresh(session)
    combat_snapshot = await _build_combat_snapshot(db, session, combat)
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            combat=combat_snapshot,
            action="lair_action_skip",
            narration="Lair Action skipped.",
            lair_action_prompt=None,
            legendary_action_prompt=None,
        ),
        db=db,
    )
    return {
        "success": True,
        "action": "lair_action_skip",
        "narration": "Lair Action skipped.",
        "combat": combat_snapshot,
        "lair_action_prompt": None,
        "legendary_action_prompt": None,
    }


def _lair_action_target_ids(req: LairActionRequest, action: dict[str, Any]) -> list[str]:
    requested = _normalize_target_ids(req.target_ids)
    if requested:
        return requested
    if req.target_id:
        return _normalize_target_ids([req.target_id])
    for key in ("target_ids", "targetIds"):
        values = _normalize_target_ids(action.get(key))
        if values:
            return values
    if isinstance(action.get("targets"), (list, tuple, set)):
        values = _normalize_target_ids(action.get("targets"))
        if values:
            return values
    action_target_id = action.get("target_id") or action.get("targetId")
    if action_target_id:
        return _normalize_target_ids([action_target_id])
    return []


def _build_lair_action_narration(
    *,
    source_name: str,
    action_name: str,
    description: str,
    effect: dict,
) -> str:
    base = f"{source_name} uses Lair Action: {action_name}."
    resolution = effect.get("response", {}).get("resolution")
    if resolution == "save":
        target_results = effect.get("response", {}).get("target_results") or []
        if len(target_results) > 1:
            failed = int(effect.get("response", {}).get("save_failed_count", 0) or 0)
            saved = int(effect.get("response", {}).get("save_succeeded_count", 0) or 0)
            damage = effect.get("response", {}).get("total_damage", 0)
            damage_type = effect.get("response", {}).get("damage_type") or "damage"
            names = _target_summary(target_results)
            return (
                f"{base} {len(target_results)} targets affected ({failed} failed, "
                f"{saved} succeeded saves): {names}. Total damage {damage} {damage_type}."
            )
        save = effect.get("response", {}).get("save") or {}
        target_name = effect.get("target_name") or "target"
        outcome = "succeeds" if save.get("success") else "fails"
        damage = effect.get("response", {}).get("total_damage", 0)
        damage_type = effect.get("response", {}).get("damage_type") or "damage"
        return (
            f"{base} {target_name} {outcome} the {save.get('ability', 'save')} save "
            f"(DC{save.get('dc')}, total {save.get('total')}) and takes {damage} {damage_type} damage."
        )
    if resolution == "attack":
        attack = effect.get("response", {}).get("attack") or {}
        target_name = effect.get("target_name") or "target"
        compare = f"{attack.get('attack_total')} vs AC{attack.get('target_ac')}"
        if attack.get("hit"):
            damage = effect.get("response", {}).get("total_damage", 0)
            damage_type = effect.get("response", {}).get("damage_type") or "damage"
            return f"{base} {source_name} hits {target_name} ({compare}) for {damage} {damage_type} damage."
        return f"{base} {source_name} misses {target_name} ({compare})."
    return f"{base} {description}".strip()


def _target_summary(target_results: list[dict[str, Any]]) -> str:
    names = [
        str(result.get("target_name") or result.get("target_id") or "target")
        for result in target_results
    ]
    if len(names) <= 3:
        return ", ".join(names)
    return f"{', '.join(names[:3])}, and {len(names) - 3} more"
