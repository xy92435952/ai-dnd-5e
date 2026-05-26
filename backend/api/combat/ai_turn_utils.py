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

    if ("Absorb Elements" in known_spells or "absorb_elements" in known_spells) and p_slots.get("1st", 0) > 0:
        available_reactions.append({
            "id": "absorb_elements",
            "name": "Absorb Elements",
            "type": "spell",
            "cost": "1st-level spell slot",
            "slot_level": "1st",
            "slots_remaining": p_slots.get("1st", 0),
            "effect": "获得触发元素的伤害抗性（持续到下回合开始），下次近战+1d6该元素伤害",
        })

    if ("Counterspell" in known_spells or "counterspell" in known_spells) and p_slots.get("3rd", 0) > 0:
        available_reactions.append({
            "id": "counterspell",
            "name": "Counterspell",
            "type": "spell",
            "cost": "3rd-level spell slot",
            "slot_level": "3rd",
            "slots_remaining": p_slots.get("3rd", 0),
            "effect": "反制敌人施放的法术（3环或以下自动成功，更高需检定）",
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
