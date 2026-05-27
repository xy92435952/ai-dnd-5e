"""
api.combat.ai_turn_utils — shared helpers for AI combat turns.
"""
from sqlalchemy.orm.attributes import flag_modified

from api.combat._shared import (
    _calc_entity_turn_limits,
    _reset_ts,
    _tick_conditions_char,
    _tick_conditions_enemy,
)
from models import GameLog
from services.combat_reaction_service import (
    build_pending_spell_reaction,
    character_knows_counterspell,
    choose_counterspell_slot,
    calculate_shield_prevention,
    calculate_uncanny_dodge_prevention,
)
from services.dnd_rules import _normalize_class


async def advance_ai_turn(combat, session, db, turn_order, next_index: int) -> None:
    """Advance combat state to the next turn and reset the next actor's turn state."""
    combat.current_turn_index = next_index
    if next_index == 0:
        combat.round_number += 1
    if turn_order:
        next_entity_id = turn_order[next_index]["character_id"]
        next_atk_max, next_move_max = await _calc_entity_turn_limits(db, session, next_entity_id)
        _reset_ts(combat, next_entity_id, attacks_max=next_atk_max, movement_max=next_move_max)


def tick_ai_actor_conditions(
    *,
    session_id: str,
    session,
    actor_name: str,
    is_enemy: bool,
    enemy,
    character,
    enemies: list[dict] | None = None,
) -> list[GameLog]:
    """Tick the AI actor's own conditions at the end of its turn."""
    tick_logs: list[GameLog] = []
    if is_enemy and enemy:
        removed = _tick_conditions_enemy(enemy)
        for condition in removed:
            tick_logs.append(GameLog(
                session_id=session_id,
                role="system",
                content=f"🟢 {actor_name} 的【{condition}】状态到期解除",
                log_type="system",
            ))
        if enemies is not None:
            state = session.game_state or {}
            state["enemies"] = enemies
            session.game_state = dict(state)
            flag_modified(session, "game_state")
    elif not is_enemy and character:
        removed = _tick_conditions_char(character)
        for condition in removed:
            tick_logs.append(GameLog(
                session_id=session_id,
                role="system",
                content=f"🟢 {actor_name} 的【{condition}】状态到期解除",
                log_type="system",
            ))
    return tick_logs


def build_reaction_prompt(
    player_check,
    player_ts: dict,
    target_id,
    actor_name: str,
    actor_id: str,
    total_damage: int,
    result_obj,
):
    """Build the reaction prompt shown when the player is targeted."""
    if not player_check:
        return False, False, None

    if str(target_id) != str(player_check.id):
        return False, False, None

    if player_ts.get("reaction_used"):
        return True, False, None

    p_derived_r = player_check.derived or {}
    p_cls = _normalize_class(player_check.char_class)
    p_level = player_check.level or 1
    known_spells = set(player_check.known_spells or []) | set(player_check.prepared_spells or [])
    p_slots = dict(player_check.spell_slots or {})
    pending_reaction = player_ts.get("pending_attack_reaction") or {}
    available_reactions = []

    if ("Shield" in known_spells or "shield" in known_spells) and p_slots.get("1st", 0) > 0:
        shield_preview = calculate_shield_prevention(pending_reaction)
        available_reactions.append({
            "id": "shield",
            "name": "Shield",
            "type": "shield",
            "cost": "1st-level spell slot",
            "slot_level": "1st",
            "slots_remaining": p_slots.get("1st", 0),
            "effect": "+5 AC（持续到你的下个回合开始）",
            "resulting_ac": p_derived_r.get("ac", 10) + 5,
            "damage_prevented": shield_preview["damage_prevented"],
            "blocked_attacks": shield_preview["blocked_attacks"],
        })

    if p_cls == "Rogue" and p_level >= 5:
        dodge_preview = calculate_uncanny_dodge_prevention(pending_reaction)
        available_reactions.append({
            "id": "uncanny_dodge",
            "name": "Uncanny Dodge",
            "type": "uncanny_dodge",
            "cost": "reaction",
            "effect": f"将此次攻击的伤害减半（{dodge_preview['original_damage']} → {dodge_preview['reduced_damage']}）",
            "reduced_damage": dodge_preview["reduced_damage"],
            "damage_prevented": dodge_preview["damage_prevented"],
        })

    if ("Hellish Rebuke" in known_spells or "hellish_rebuke" in known_spells) and p_slots.get("1st", 0) > 0:
        available_reactions.append({
            "id": "hellish_rebuke",
            "name": "Hellish Rebuke",
            "type": "hellish_rebuke",
            "cost": "1st-level spell slot",
            "slot_level": "1st",
            "slots_remaining": p_slots.get("1st", 0),
            "effect": "对攻击者造成 2d10 火焰伤害（DEX豁免成功减半）",
            "damage_dice": "2d10",
        })

    if not available_reactions:
        return True, False, None

    return True, True, {
        "can_react": True,
        "reaction_used": player_ts.get("reaction_used", False),
        "attack_roll": result_obj.attack_roll.get("attack_total", 0) if result_obj else 0,
        "player_ac": p_derived_r.get("ac", 10),
        "incoming_damage": total_damage,
        "attacker_name": actor_name,
        "attacker_id": actor_id,
        "reactor_character_id": str(player_check.id),
        "target_id": actor_id,
        "spell_slots": p_slots,
        "available_reactions": available_reactions,
        "options": [
            {
                "type": reaction["type"],
                "target_id": actor_id,
                "character_id": str(player_check.id),
                "label": f"{reaction['name']} - {reaction.get('effect', '')}".strip(" -"),
            }
            for reaction in available_reactions
        ],
    }


def build_counterspell_prompt(
    *,
    player_check,
    player_ts: dict,
    actor_id: str,
    actor_name: str,
    spell_name: str,
    spell_level: int,
    spell_target_id: str | None,
    decision: dict,
    decided_reason: str,
):
    if not player_check:
        return False, False, None
    if player_ts.get("reaction_used"):
        return True, False, None
    if not character_knows_counterspell(player_check):
        return True, False, None

    slot_choice = choose_counterspell_slot(player_check.spell_slots or {}, spell_level)
    if not slot_choice:
        return True, False, None

    slot_key, slot_level = slot_choice
    declined = player_ts.get("resume_spell_reaction") or {}
    spell_target_key = str(spell_target_id) if spell_target_id is not None else None
    if (
        declined.get("trigger") == "spell_cast"
        and str(declined.get("caster_id")) == str(actor_id)
        and declined.get("spell_name") == spell_name
        and int(declined.get("spell_level") or 0) == int(spell_level or 0)
        and declined.get("spell_target_id") == spell_target_key
    ):
        return True, False, None

    pending_reaction = build_pending_spell_reaction(
        caster_id=actor_id,
        caster_name=actor_name,
        reactor_id=str(player_check.id),
        spell_name=spell_name,
        spell_level=spell_level,
        spell_target_id=spell_target_id,
        decision=decision,
        decided_reason=decided_reason,
    )
    player_ts["pending_spell_reaction"] = pending_reaction

    reaction = {
        "id": "counterspell",
        "name": "Counterspell",
        "type": "counterspell",
        "cost": f"{slot_key} spell slot",
        "slot_level": slot_key,
        "slot_level_number": slot_level,
        "slots_remaining": (player_check.spell_slots or {}).get(slot_key, 0),
        "effect": (
            f"Cancel {actor_name}'s {spell_name}"
            if spell_level <= slot_level
            else f"Attempt to cancel {actor_name}'s {spell_name} (DC {10 + int(spell_level or 0)})"
        ),
        "countered_spell": spell_name,
        "countered_spell_level": int(spell_level or 0),
    }
    return True, True, {
        "can_react": True,
        "reaction_used": player_ts.get("reaction_used", False),
        "trigger": "spell_cast",
        "context": f"{actor_name} is casting {spell_name}.",
        "attacker_name": actor_name,
        "attacker_id": actor_id,
        "caster_name": actor_name,
        "caster_id": actor_id,
        "spell_name": spell_name,
        "spell_level": int(spell_level or 0),
        "reactor_character_id": str(player_check.id),
        "target_id": actor_id,
        "spell_target_id": str(spell_target_id) if spell_target_id is not None else None,
        "spell_slots": player_check.spell_slots or {},
        "available_reactions": [reaction],
        "options": [{
            "type": "counterspell",
            "target_id": actor_id,
            "character_id": str(player_check.id),
            "label": f"{reaction['name']} - {reaction.get('effect', '')}".strip(" -"),
        }],
    }
