"""Divine Smite combat endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, CombatState, GameLog, SessionMember
from api.deps import assert_can_act, get_session_or_404, get_user_id
from api.combat._shared import _broadcast_combat, svc
from api.combat.schemas import SmiteRequest
from services.combat_narrator import narrate_action
from services.combat_outcome_service import check_and_cleanup_combat_outcome
from services.combat_smite_target_service import target_gets_divine_smite_extra_damage
from services.dnd_rules import _normalize_class
from schemas.combat_responses import CombatActionResult
from schemas.ws_events import CombatUpdate

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/smite", response_model=CombatActionResult)
async def divine_smite(
    session_id: str,
    req: SmiteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Apply a Paladin Divine Smite from a trusted pending hit window."""
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "Current session is not in combat")

    if session.is_multiplayer:
        member_q = await db.execute(
            select(SessionMember).where(
                SessionMember.session_id == session_id,
                SessionMember.user_id == user_id,
            )
        )
        member = member_q.scalar_one_or_none()
        if not member or not member.character_id:
            raise HTTPException(403, "No character is bound to this room member")
        player = await db.get(Character, member.character_id)
    else:
        player = await db.get(Character, session.player_character_id)
    if not player:
        raise HTTPException(404, "Player character not found")

    await assert_can_act(session, user_id, player.id, db, require_current_turn=False)

    if _normalize_class(player.char_class) != "Paladin":
        raise HTTPException(400, "Only Paladins can use Divine Smite")

    combat_result = await db.execute(
        select(CombatState)
        .where(CombatState.session_id == session_id)
        .order_by(CombatState.created_at.desc())
    )
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "Combat state not found")

    state = session.game_state or {}
    enemies = list(state.get("enemies", []) or [])
    all_turn_states = dict(combat.turn_states or {})
    player_turn_state = dict(all_turn_states.get(str(player.id), {}) or {})
    pending_smite = player_turn_state.get("pending_smite")
    if not isinstance(pending_smite, dict) or pending_smite.get("used"):
        raise HTTPException(400, "Divine Smite requires a fresh confirmed weapon hit")

    smite_target_id = str(req.target_id or pending_smite.get("target_id") or "")
    pending_target_id = str(pending_smite.get("target_id") or "")
    if not smite_target_id or smite_target_id != pending_target_id:
        raise HTTPException(409, "Smite target does not match the confirmed weapon hit")

    smite_is_crit = bool(pending_smite.get("is_crit"))
    if req.is_crit is not None and bool(req.is_crit) != smite_is_crit:
        raise HTTPException(409, "Smite critical state does not match the confirmed weapon hit")

    target_enemy = next(
        (enemy for enemy in enemies if str(enemy.get("id")) == smite_target_id),
        None,
    )
    if not target_enemy or int(target_enemy.get("hp_current", 0) or 0) <= 0:
        raise HTTPException(400, "No valid Divine Smite target is available")
    target_is_undead_or_fiend = target_gets_divine_smite_extra_damage(target_enemy)

    slot_level = max(1, min(int(req.slot_level or 1), 5))
    slot_key = ["1st", "2nd", "3rd", "4th", "5th"][slot_level - 1]
    current_slots = dict(player.spell_slots or {})
    available = int(current_slots.get(slot_key, 0) or 0)
    if available <= 0:
        raise HTTPException(400, f"No available {slot_key} spell slot")

    smite = svc.calc_divine_smite_damage(
        slot_level,
        target_is_undead_or_fiend,
        is_crit=smite_is_crit,
    )
    if req.damage_values:
        smite["damage"] = sum(req.damage_values)
        smite["roll"] = {
            **(smite.get("roll") or {}),
            "total": smite["damage"],
            "rolls": req.damage_values,
        }

    current_slots[slot_key] = available - 1
    player.spell_slots = current_slots
    flag_modified(player, "spell_slots")

    target_enemy["hp_current"] = svc.apply_damage(
        target_enemy.get("hp_current", 0),
        smite["damage"],
        (target_enemy.get("derived") or {}).get("hp_max", target_enemy.get("hp_max", 10)),
    )
    target_new_hp = target_enemy["hp_current"]
    target_name = target_enemy.get("name", "Enemy")
    target_state = _enemy_smite_target_state(target_enemy, smite_target_id)
    damage_roll = smite.get("roll")

    dice_result = {
        "type": "divine_smite",
        "slot_level": slot_level,
        **smite,
        "target_id": smite_target_id,
        "target_name": target_name,
        "target_new_hp": target_new_hp,
        "target_state": target_state,
        "damage_type": "radiant",
        "total_damage": smite["damage"],
        "remaining_slots": current_slots,
        "target_is_undead_or_fiend": target_is_undead_or_fiend,
    }

    player_turn_state.pop("pending_smite", None)
    all_turn_states[str(player.id)] = player_turn_state
    combat.turn_states = all_turn_states
    flag_modified(combat, "turn_states")

    state["enemies"] = enemies
    session.game_state = dict(state)
    flag_modified(session, "game_state")

    undead_note = " with extra undead/fiend radiance" if target_is_undead_or_fiend else ""
    mechanical_narration = (
        f"{player.name} releases Divine Smite for {smite['dice']} radiant damage"
        f"{undead_note}, dealing {smite['damage']} damage to {target_name}."
    )
    vivid = await narrate_action(
        actor_name=player.name,
        actor_class=_normalize_class(player.char_class),
        target_name=target_name,
        action_type="smite",
        damage=smite["damage"],
        damage_type="radiant",
    )
    narration = vivid if vivid else mechanical_narration

    db.add(GameLog(
        session_id=session_id,
        role="player",
        content=narration,
        log_type="combat",
        dice_result=dice_result,
    ))

    combat_over, outcome = await check_and_cleanup_combat_outcome(
        db,
        session=session,
        session_id=session_id,
        enemies=enemies,
        check_combat_over=svc.check_combat_over,
    )

    await db.commit()
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            actor_id=str(player.id),
            actor_name=player.name,
            narration=narration,
            action="divine_smite",
            target_id=smite_target_id,
            target_name=target_name,
            target_new_hp=target_new_hp,
            target_state=target_state,
            damage=smite["damage"],
            total_damage=smite["damage"],
            damage_roll=damage_roll,
            damage_type="radiant",
            dice_result=dice_result,
            special_action=dice_result,
            remaining_slots=current_slots,
            combat_over=combat_over,
            outcome=outcome,
        ),
        db=db,
    )
    return {
        "action": "divine_smite",
        "narration": narration,
        "smite_damage": smite["damage"],
        "smite_dice": smite["dice"],
        "damage": smite["damage"],
        "total_damage": smite["damage"],
        "damage_roll": damage_roll,
        "damage_type": "radiant",
        "is_crit": smite.get("is_crit", False),
        "target_id": smite_target_id,
        "target_name": target_name,
        "target_new_hp": target_new_hp,
        "target_state": target_state,
        "dice_result": dice_result,
        "special_action": dice_result,
        "remaining_slots": current_slots,
        "target_is_undead_or_fiend": target_is_undead_or_fiend,
        "combat_over": combat_over,
        "outcome": outcome,
    }


def _enemy_smite_target_state(enemy: dict, target_id: str) -> dict:
    derived = enemy.get("derived") or {}
    hp_max = enemy.get("hp_max", derived.get("hp_max", 10))
    return {
        "target_id": target_id,
        "target_name": enemy.get("name", "Enemy"),
        "hp_current": enemy.get("hp_current", 0),
        "new_hp": enemy.get("hp_current", 0),
        "hp_max": hp_max,
        "conditions": list(enemy.get("conditions") or []),
        "condition_durations": dict(enemy.get("condition_durations") or {}),
        "life_state": "dead" if int(enemy.get("hp_current", 0) or 0) <= 0 else "alive",
        "is_enemy": True,
    }
