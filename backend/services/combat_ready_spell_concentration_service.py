from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from models import Character, CombatState, GameLog
from services.combat_concentration_effect_service import set_concentration_with_cleanup
from services.combat_turn_state_service import get_turn_state, save_turn_state


READY_SPELL_CONCENTRATION_PREFIX = "准备法术: "


@dataclass
class ReadySpellConcentrationClearResult:
    ready_action_failed: dict[str, Any]
    actor_state: dict[str, Any]


def build_ready_spell_concentration_name(spell_name: str) -> str:
    return f"{READY_SPELL_CONCENTRATION_PREFIX}{str(spell_name or '').strip()}"


def is_ready_spell_concentration(value: str | None) -> bool:
    return str(value or "").startswith(READY_SPELL_CONCENTRATION_PREFIX)


def ready_spell_name_from_concentration(value: str | None) -> str:
    raw = str(value or "")
    if not raw.startswith(READY_SPELL_CONCENTRATION_PREFIX):
        return raw
    return raw[len(READY_SPELL_CONCENTRATION_PREFIX):].strip()


def ready_spell_concentration_matches(ready_action: dict[str, Any], concentration: str | None) -> bool:
    marker = ready_action.get("concentration_spell_name")
    if not marker:
        spell_name = ready_action.get("spell_name")
        marker = build_ready_spell_concentration_name(spell_name) if spell_name else ""
    return bool(marker and str(concentration or "") == str(marker))


def build_ready_spell_actor_state(
    actor: Character,
    *,
    concentration: str | None | object = Ellipsis,
) -> dict[str, Any]:
    resolved_concentration = actor.concentration if concentration is Ellipsis else concentration
    return {
        "target_id": str(actor.id),
        "entity_id": str(actor.id),
        "target_name": actor.name,
        "concentration": resolved_concentration,
    }


async def set_ready_spell_concentration_hold(
    db,
    session,
    caster: Character,
    *,
    spell_name: str,
    caster_id: str,
) -> tuple[str, list[dict[str, Any]]]:
    marker = build_ready_spell_concentration_name(spell_name)
    updates = await set_concentration_with_cleanup(
        db,
        session,
        caster,
        marker,
        caster_id=caster_id,
    )
    return marker, updates


def clear_ready_spell_concentration_hold(actor: Character, ready_action: dict[str, Any]) -> dict[str, Any] | None:
    if not ready_spell_concentration_matches(ready_action, actor.concentration):
        return None
    actor.concentration = None
    return build_ready_spell_actor_state(actor, concentration=None)


async def clear_expired_ready_spell_concentration_hold(
    db,
    actor_id: str,
    expiry: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not expiry or expiry.get("action_type") != "spell":
        return None
    actor = await db.get(Character, actor_id)
    if not actor:
        return None
    actor_state = clear_ready_spell_concentration_hold(actor, expiry)
    if actor_state:
        expiry["actor_state"] = actor_state
        expiry["concentration_ended"] = True
        expiry["concentration_spell_name"] = (
            expiry.get("concentration_spell_name")
            or build_ready_spell_concentration_name(str(expiry.get("spell_name") or ""))
        )
    return actor_state


async def clear_ready_spell_for_lost_concentration(
    db,
    session,
    character: Character,
    *,
    concentration_spell_name: str | None,
    reason: str = "concentration_lost",
    triggered_by: str | None = None,
    add_log: bool = True,
) -> ReadySpellConcentrationClearResult | None:
    if not is_ready_spell_concentration(concentration_spell_name):
        return None

    character_id = str(character.id)
    result = await db.execute(
        select(CombatState)
        .where(CombatState.session_id == str(session.id))
        .order_by(CombatState.created_at.desc())
    )
    combat = result.scalars().first()
    if not combat:
        return None

    turn_state = get_turn_state(combat, character_id)
    ready_action = turn_state.get("ready_action")
    if not isinstance(ready_action, dict) or ready_action.get("action_type") != "spell":
        return None

    ready_marker = (
        ready_action.get("concentration_spell_name")
        or build_ready_spell_concentration_name(str(ready_action.get("spell_name") or ""))
    )
    if str(ready_marker or "") != str(concentration_spell_name or ""):
        return None

    spell_name = ready_action.get("spell_name") or ready_spell_name_from_concentration(concentration_spell_name)
    actor_state = build_ready_spell_actor_state(character, concentration=None)
    failure = {
        "type": "ready_action_failed",
        "action_type": "spell",
        "reason": reason,
        "actor_id": character_id,
        "actor_name": character.name or character_id,
        "target_id": ready_action.get("target_id"),
        "target_name": ready_action.get("target_name"),
        "spell_name": spell_name,
        "spell_level": ready_action.get("spell_level"),
        "concentration_spell_name": concentration_spell_name,
        "slot_already_consumed": ready_action.get("slot_already_consumed"),
        "slot_key": ready_action.get("slot_key"),
        "slots_remaining": ready_action.get("slots_remaining"),
        "actor_state": actor_state,
    }
    if triggered_by:
        failure["triggered_by"] = triggered_by

    turn_state.pop("ready_action", None)
    turn_state["ready_action_failed"] = failure
    save_turn_state(combat, character_id, turn_state)

    if add_log:
        db.add(build_ready_spell_dissipated_log(str(session.id), failure))

    return ReadySpellConcentrationClearResult(
        ready_action_failed=failure,
        actor_state=actor_state,
    )


def build_ready_spell_dissipated_log(session_id: str, failure: dict[str, Any]) -> GameLog:
    actor_name = failure.get("actor_name") or failure.get("actor_id") or "角色"
    spell_name = failure.get("spell_name") or "法术"
    return GameLog(
        session_id=session_id,
        role="system",
        content=f"{actor_name} 的准备法术 {spell_name} 因专注中断而消散。",
        log_type="combat",
        dice_result={
            **failure,
            "type": "ready_action",
            "action_type": "spell",
            "applied": False,
            "reason": failure.get("reason") or "concentration_lost",
            "concentration_lost": True,
            "reaction_used": False,
            "ready_action_failed": failure,
        },
    )
