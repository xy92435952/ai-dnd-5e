"""
api.combat.ai_turn_spell — AI spell-casting branch for combat turns.
"""
from sqlalchemy.orm.attributes import flag_modified

from api.combat.ai_turn_utils import advance_ai_turn, tick_ai_actor_conditions
from models import GameLog
from services.combat_ai_spell_service import resolve_ai_spell_action
from services.combat_narrator import narrate_action
from services.dnd_rules import _normalize_class


async def handle_ai_spell_action(
    session_id: str,
    db,
    session,
    combat,
    turn_order,
    next_index: int,
    actor_id: str,
    actor_name: str,
    is_enemy: bool,
    achar,
    actor_derived: dict,
    decided_target_id: str | None,
    decided_reason: str,
    decision: dict,
    state: dict,
    enemies: list,
    enemies_alive: list,
    all_characters: list,
    enemy=None,
):
    """Handle AI spell casting and return a response dict when resolved."""
    spell_resolution = await resolve_ai_spell_action(
        db,
        session=session,
        actor_name=actor_name,
        is_enemy=is_enemy,
        caster=achar,
        actor_derived=actor_derived,
        decided_target_id=decided_target_id,
        decided_reason=decided_reason,
        decision=decision,
        state=state,
        enemies=enemies,
        enemies_alive=enemies_alive,
        all_characters=all_characters,
    )
    if spell_resolution is None:
        return None

    ai_class = _normalize_class(achar.char_class) if achar else actor_name
    vivid = await narrate_action(
        actor_name=actor_name,
        actor_class=ai_class,
        target_name=spell_resolution.target_name or "目标",
        action_type="spell",
        spell_name=spell_resolution.spell_name,
        damage=spell_resolution.damage,
        heal_amount=spell_resolution.heal,
    )
    narration = vivid if vivid else spell_resolution.mechanical_narration

    db.add(GameLog(
        session_id=session_id,
        role="enemy" if is_enemy else f"companion_{actor_name}",
        content=narration,
        log_type="combat",
    ))
    tick_logs = tick_ai_actor_conditions(
        session_id=session_id,
        session=session,
        actor_name=actor_name,
        is_enemy=is_enemy,
        enemy=enemy,
        character=achar,
        enemies=enemies,
    )
    for log in tick_logs:
        db.add(log)

    await advance_ai_turn(combat, session, db, turn_order, next_index)
    flag_modified(session, "game_state")
    await db.commit()
    return {
        "actor_name": actor_name,
        "actor_id": actor_id,
        "narration": narration,
        "attack_result": {},
        "damage": spell_resolution.damage,
        "target_id": str(spell_resolution.spell_target) if spell_resolution.spell_target else None,
        "target_new_hp": spell_resolution.target_new_hp,
        "target_state": spell_resolution.target_state,
        "next_turn_index": next_index,
        "round_number": combat.round_number,
        "combat_over": False,
        "outcome": None,
        "entity_positions": dict(combat.entity_positions or {}),
    }
