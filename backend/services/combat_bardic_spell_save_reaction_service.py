from __future__ import annotations

from typing import Any

from sqlalchemy import select

from models import Character, SessionMember
from services.bardic_inspiration_service import get_bardic_inspiration_die
from services.combat_spell_resolution_service import build_spell_resolution_context
from services.combat_turn_state_service import save_turn_state


PENDING_BARDIC_SPELL_SAVE_REACTION_KEY = "pending_bardic_spell_save_reaction"
BARDIC_SPELL_SAVE_REACTION_TYPE = "bardic_spell_save"
BARDIC_SPELL_SAVE_TRIGGER = "spell_save"


async def build_pending_bardic_spell_save_reaction(
    db,
    *,
    session,
    caster,
    caster_entity_id: str,
    pending: dict[str, Any],
    spell: dict[str, Any],
    damage_values: list[int] | None,
    requesting_user_id: str | None,
) -> dict[str, Any] | None:
    """Build a private Bardic spell-save prompt for the first eligible target."""
    if not getattr(session, "is_multiplayer", False):
        return None
    if not spell.get("save"):
        return None

    target_ids = [str(target_id) for target_id in pending.get("target_ids") or []]
    if not target_ids:
        return None

    spell_context = build_spell_resolution_context(getattr(caster, "derived", None) or {})
    for target_id in target_ids:
        target = await db.get(Character, target_id)
        if not target or not getattr(target, "is_player", False):
            continue
        controller_user_id = await get_character_controller_user_id(
            db,
            session_id=session.id,
            character=target,
        )
        if not controller_user_id:
            continue
        if requesting_user_id and str(controller_user_id) == str(requesting_user_id):
            continue
        die = get_bardic_inspiration_die(target)
        if not die:
            continue
        return build_bardic_spell_save_prompt(
            caster=caster,
            caster_entity_id=str(caster_entity_id),
            target=target,
            pending=pending,
            spell=spell,
            die=die,
            save_dc=spell_context["spell_save_dc"],
            damage_values=damage_values,
        )
    return None


def build_bardic_spell_save_prompt(
    *,
    caster,
    caster_entity_id: str,
    target,
    pending: dict[str, Any],
    spell: dict[str, Any],
    die: str,
    save_dc: int | None,
    damage_values: list[int] | None,
) -> dict[str, Any]:
    spell_name = pending.get("spell_name") or spell.get("name") or "spell"
    spell_level = int(pending.get("spell_level") or 0)
    save_ability = spell.get("save")
    target_id = str(getattr(target, "id"))
    caster_name = getattr(caster, "name", None) or "Caster"
    target_name = getattr(target, "name", None) or "Target"
    label = f"Bardic Inspiration {die}"
    return {
        "trigger": BARDIC_SPELL_SAVE_TRIGGER,
        "reaction_type": BARDIC_SPELL_SAVE_REACTION_TYPE,
        "pending_spell_id": pending.get("pending_spell_id"),
        "caster_id": str(caster_entity_id),
        "caster_name": caster_name,
        "spell_name": spell_name,
        "spell_level": spell_level,
        "spell_type": pending.get("spell_type"),
        "target_id": target_id,
        "target_name": target_name,
        "reactor_character_id": target_id,
        "reactor_name": target_name,
        "save_ability": save_ability,
        "save_dc": save_dc,
        "die": die,
        "damage_values": list(damage_values) if damage_values is not None else None,
        "context": _build_prompt_context(
            caster_name=caster_name,
            spell_name=spell_name,
            save_ability=save_ability,
            save_dc=save_dc,
        ),
        "available_reactions": [
            {
                "id": BARDIC_SPELL_SAVE_REACTION_TYPE,
                "type": BARDIC_SPELL_SAVE_REACTION_TYPE,
                "name": "Bardic Inspiration",
                "label": label,
                "effect": f"Roll {die} and add it to this saving throw.",
                "cost": f"spend Bardic Inspiration {die}",
                "die": die,
                "target_id": target_id,
                "character_id": target_id,
            },
        ],
        "options": [
            {
                "type": BARDIC_SPELL_SAVE_REACTION_TYPE,
                "label": label,
                "cost": f"spend Bardic Inspiration {die}",
                "die": die,
                "target_id": target_id,
                "character_id": target_id,
            },
        ],
        "can_decline": True,
    }


def store_pending_bardic_spell_save_reaction(combat, prompt: dict[str, Any]) -> dict[str, Any]:
    reactor_id = str(prompt["reactor_character_id"])
    turn_states = dict(combat.turn_states or {})
    turn_state = dict(turn_states.get(reactor_id) or {})
    turn_state[PENDING_BARDIC_SPELL_SAVE_REACTION_KEY] = prompt
    save_turn_state(combat, reactor_id, turn_state)
    return turn_state


async def get_character_controller_user_id(
    db,
    *,
    session_id: str,
    character: Character,
) -> str | None:
    if getattr(character, "user_id", None):
        return str(character.user_id)
    result = await db.execute(
        select(SessionMember.user_id)
        .where(SessionMember.session_id == session_id)
        .where(SessionMember.character_id == character.id)
    )
    user_id = result.scalar_one_or_none()
    return str(user_id) if user_id else None


def _build_prompt_context(
    *,
    caster_name: str,
    spell_name: str,
    save_ability: str | None,
    save_dc: int | None,
) -> str:
    save_label = str(save_ability or "save").upper()
    dc_label = f" DC{save_dc}" if save_dc is not None else ""
    return f"{caster_name}'s {spell_name} forces a {save_label}{dc_label} saving throw."
