"""Shared helpers for AI combat turns."""

from api.combat._shared import _calc_entity_turn_limits, _reset_ts
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


def _knows_spell(known_spells: set[str], *names: str) -> bool:
    normalized = {str(spell).strip().lower().replace(" ", "_") for spell in known_spells}
    return any(name.lower().replace(" ", "_") in normalized for name in names)


def _reaction_option(item: dict, attacker_id: str) -> dict:
    return {
        "type": item["id"],
        "label": item["name"],
        "target_id": attacker_id,
        "cost": item.get("cost"),
        "effect": item.get("effect"),
    }


async def advance_after_pending_ai_attack(combat, session, db, pending: dict) -> None:
    next_index = pending.get("next_turn_index")
    turn_order = combat.turn_order or []
    if next_index is None or not turn_order:
        return
    await advance_ai_turn(combat, session, db, turn_order, int(next_index))


def build_reaction_prompt(player_check, player_ts: dict, target_id, actor_name: str, actor_id: str, total_damage: int, result_obj):
    """Build the weapon-attack reaction prompt shown when the player is targeted.

    Keep this list aligned with /combat/{session_id}/reaction. Spell reactions
    that need a different trigger, such as Counterspell, should be offered by
    the spell-casting path instead of this weapon-attack prompt.
    """
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
    available_reactions = []

    if _knows_spell(known_spells, "Shield") and p_slots.get("1st", 0) > 0:
        available_reactions.append({
            "id": "shield",
            "name": "Shield",
            "type": "spell",
            "cost": "1st-level spell slot",
            "slot_level": "1st",
            "slots_remaining": p_slots.get("1st", 0),
            "effect": "+5 AC until the start of your next turn",
            "resulting_ac": p_derived_r.get("ac", 10) + 5,
        })

    if p_cls == "Rogue" and p_level >= 5:
        available_reactions.append({
            "id": "uncanny_dodge",
            "name": "Uncanny Dodge",
            "type": "class_feature",
            "cost": "reaction",
            "effect": f"Halve this attack's damage ({total_damage} -> {total_damage // 2})",
            "reduced_damage": total_damage // 2,
        })

    if _knows_spell(known_spells, "Hellish Rebuke") and p_slots.get("1st", 0) > 0:
        available_reactions.append({
            "id": "hellish_rebuke",
            "name": "Hellish Rebuke",
            "type": "spell",
            "cost": "1st-level spell slot",
            "slot_level": "1st",
            "slots_remaining": p_slots.get("1st", 0),
            "effect": "Deal 2d10 fire damage to the attacker",
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
        "spell_slots": p_slots,
        "available_reactions": available_reactions,
        "options": [_reaction_option(item, actor_id) for item in available_reactions],
    }
