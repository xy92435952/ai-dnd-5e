"""
api.combat.ai_turn_spell — AI spell-casting branch for combat turns.
"""
from sqlalchemy.orm.attributes import flag_modified

from api.combat._shared import _get_ts, _save_ts
from api.combat.ai_turn_utils import advance_ai_turn, build_counterspell_prompt, tick_ai_actor_conditions
from models import GameLog
from services.character_roster import CharacterRoster
from services.combat_ai_spell_service import resolve_ai_spell_action, resolve_ai_spell_level
from services.combat_narrator import narrate_action
from services.dnd_rules import _normalize_class
from services.spell_service import spell_service


async def _counterspell_reactor_candidates(db, session, target_id: str | None):
    roster = CharacterRoster(db, session)
    party = await roster.allies_alive()
    candidates = []
    if target_id:
        for character in party:
            if str(character.id) == str(target_id):
                candidates.append(character)
                break
    candidates.extend(character for character in party if character not in candidates)
    return candidates


def _find_pending_counterspell(combat, actor_id: str):
    for reactor_id, state in (combat.turn_states or {}).items():
        pending = (state or {}).get("pending_spell_reaction") or {}
        if (
            pending.get("trigger") == "spell_cast"
            and str(pending.get("caster_id")) == str(actor_id)
        ):
            return str(reactor_id), dict(state or {}), pending
    return None, None, None


def find_resumable_spell_reaction(combat, actor_id: str):
    for reactor_id, state in (combat.turn_states or {}).items():
        pending = (state or {}).get("resume_spell_reaction") or {}
        if (
            pending.get("trigger") == "spell_cast"
            and str(pending.get("caster_id")) == str(actor_id)
        ):
            return str(reactor_id), dict(state or {}), pending
    return None, None, None


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
    pending_reactor_id, _pending_ts, pending_spell = _find_pending_counterspell(combat, actor_id)
    if pending_spell:
        return {
            "actor_name": actor_name,
            "actor_id": actor_id,
            "narration": f"{actor_name} is waiting for a reaction to {pending_spell.get('spell_name', 'the spell')}.",
            "attack_result": {},
            "damage": 0,
            "target_id": pending_spell.get("spell_target_id"),
            "target_new_hp": None,
            "player_targeted": bool(pending_spell.get("spell_target_id")),
            "player_can_react": True,
            "reaction_prompt": {
                "can_react": True,
                "trigger": "spell_cast",
                "context": f"{actor_name} is casting {pending_spell.get('spell_name', 'a spell')}.",
                "attacker_name": actor_name,
                "attacker_id": actor_id,
                "caster_name": actor_name,
                "caster_id": actor_id,
                "spell_name": pending_spell.get("spell_name"),
                "spell_level": pending_spell.get("spell_level"),
                "reactor_character_id": pending_reactor_id,
                "target_id": actor_id,
                "spell_target_id": pending_spell.get("spell_target_id"),
                "available_reactions": [{
                    "id": "counterspell",
                    "name": "Counterspell",
                    "type": "counterspell",
                    "effect": f"Cancel {actor_name}'s {pending_spell.get('spell_name', 'spell')}",
                }],
                "options": [{
                    "type": "counterspell",
                    "target_id": actor_id,
                    "character_id": pending_reactor_id,
                    "label": f"Counterspell - Cancel {actor_name}'s {pending_spell.get('spell_name', 'spell')}",
                }],
            },
            "next_turn_index": combat.current_turn_index,
            "round_number": combat.round_number,
            "combat_over": False,
            "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        }

    resume_reactor_id, resume_ts, resume_spell = find_resumable_spell_reaction(combat, actor_id)
    if resume_spell:
        decision = resume_spell.get("decision") or decision
        decided_target_id = resume_spell.get("spell_target_id")
        decided_reason = resume_spell.get("decided_reason") or decided_reason
        if resume_ts is not None:
            resume_ts.pop("resume_spell_reaction", None)
            _save_ts(combat, resume_reactor_id, resume_ts)

    spell_name = decision.get("action_name")
    spell_data = spell_service.get(spell_name) if decision.get("action_type") == "spell" and spell_name else None
    if is_enemy and spell_data and not resume_spell:
        spell_level = resolve_ai_spell_level(decision, spell_data)
        for reactor in await _counterspell_reactor_candidates(db, session, decided_target_id):
            reactor_ts = _get_ts(combat, reactor.id)
            player_can_react, has_prompt, reaction_prompt = build_counterspell_prompt(
                player_check=reactor,
                player_ts=reactor_ts,
                actor_id=actor_id,
                actor_name=actor_name,
                spell_name=spell_name,
                spell_level=spell_level,
                spell_target_id=decided_target_id,
                decision=decision,
                decided_reason=decided_reason,
                combat=combat,
                caster_conditions=(enemy or {}).get("conditions", []) if is_enemy else getattr(achar, "conditions", []),
            )
            if has_prompt:
                _save_ts(combat, reactor.id, reactor_ts)
                narration = f"{actor_name} begins casting {spell_name}."
                db.add(GameLog(
                    session_id=session_id,
                    role="enemy",
                    content=narration,
                    log_type="combat",
                ))
                await db.commit()
                return {
                    "actor_name": actor_name,
                    "actor_id": actor_id,
                    "narration": narration,
                    "attack_result": {},
                    "damage": 0,
                    "target_id": str(decided_target_id) if decided_target_id else None,
                    "target_new_hp": None,
                    "player_targeted": bool(decided_target_id),
                    "player_can_react": player_can_react,
                    "reaction_prompt": reaction_prompt,
                    "next_turn_index": combat.current_turn_index,
                    "round_number": combat.round_number,
                    "combat_over": False,
                    "outcome": None,
                    "entity_positions": dict(combat.entity_positions or {}),
                }

    spell_resolution = await resolve_ai_spell_action(
        db,
        session=session,
        actor_name=actor_name,
        is_enemy=is_enemy,
        caster=enemy if is_enemy else achar,
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
