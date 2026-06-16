from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from models.character import Character
from models.session import Session
from services.exploration_rules_service import (
    apply_trap_resolution_to_target,
    resolve_trap_trigger,
)
from services.feather_fall_service import (
    build_feather_fall_reaction_option,
    is_fall_damage_event,
)


PENDING_EXPLORATION_REACTION_KEY = "pending_exploration_reaction"


def maybe_create_feather_fall_prompt(
    *,
    session: Session,
    trap: dict[str, Any],
    target: Character,
    characters: list[Character],
    trigger_actor_user_id: str | None = None,
) -> dict[str, Any] | None:
    """Roll a fall trap once and persist a private Feather Fall prompt when possible."""
    if not is_fall_damage_event(trap):
        return None

    resolution = resolve_trap_trigger(trap, target)
    if int(resolution.get("final_damage") or 0) <= 0:
        return None

    fall_event = {
        **dict(trap or {}),
        "damage": resolution.get("final_damage", 0),
        "final_damage": resolution.get("final_damage", 0),
        "rolled_damage": resolution.get("rolled_damage", 0),
        "damage_type": resolution.get("damage_type"),
    }
    for caster in characters:
        reactor_user_id = _reaction_user_id(session, caster)
        if session.is_multiplayer and not reactor_user_id:
            continue
        option = build_feather_fall_reaction_option(
            caster,
            fall_event,
            targets=[target],
        )
        if not option:
            continue

        prompt = {
            "id": _pending_reaction_id(session, resolution, caster, target),
            "type": "feather_fall",
            "trigger": "fall_damage",
            "reactor_character_id": str(caster.id),
            "reactor_character_name": caster.name,
            "reactor_user_id": reactor_user_id,
            "target_character_id": str(target.id),
            "target_character_name": target.name,
            "trap_id": resolution.get("trap_id"),
            "trap_name": resolution.get("name") or resolution.get("trap_id") or "Trap",
            "damage_before": resolution.get("final_damage", 0),
            "damage_after": 0,
            "damage_prevented": resolution.get("final_damage", 0),
            "available_reactions": [option],
            "options": [{
                "type": "feather_fall",
                "label": "Cast Feather Fall",
                "cost": option.get("cost"),
                "slot_level": option.get("slot_level"),
                "damage_prevented": option.get("damage_prevented"),
            }],
            "can_decline": True,
            "trap": deepcopy(trap),
            "trap_resolution": deepcopy(resolution),
            "trigger_actor_user_id": trigger_actor_user_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        persist_pending_exploration_reaction(session, prompt)
        return project_exploration_reaction_prompt(
            prompt,
            viewer_character_id=str(caster.id),
            viewer_user_id=reactor_user_id,
        )

    return None


def persist_pending_exploration_reaction(session: Session, prompt: dict[str, Any]) -> None:
    game_state = dict(session.game_state or {})
    game_state[PENDING_EXPLORATION_REACTION_KEY] = deepcopy(prompt)
    session.game_state = game_state
    flag_modified(session, "game_state")


def clear_pending_exploration_reaction(session: Session) -> None:
    game_state = dict(session.game_state or {})
    if PENDING_EXPLORATION_REACTION_KEY not in game_state:
        return
    game_state.pop(PENDING_EXPLORATION_REACTION_KEY, None)
    session.game_state = game_state
    flag_modified(session, "game_state")


def pending_exploration_reaction(session: Session) -> dict[str, Any] | None:
    pending = (session.game_state or {}).get(PENDING_EXPLORATION_REACTION_KEY)
    return pending if isinstance(pending, dict) else None


def project_exploration_reaction_prompt(
    prompt: dict[str, Any] | None,
    *,
    viewer_character_id: str | None = None,
    viewer_user_id: str | None = None,
) -> dict[str, Any] | None:
    if not isinstance(prompt, dict):
        return None
    if not _viewer_can_see_prompt(
        prompt,
        viewer_character_id=viewer_character_id,
        viewer_user_id=viewer_user_id,
    ):
        return None
    return deepcopy(prompt)


def project_game_state_exploration_reaction(
    game_state: dict[str, Any],
    *,
    viewer_character_id: str | None = None,
    viewer_user_id: str | None = None,
) -> None:
    prompt = game_state.get(PENDING_EXPLORATION_REACTION_KEY)
    projected = project_exploration_reaction_prompt(
        prompt,
        viewer_character_id=viewer_character_id,
        viewer_user_id=viewer_user_id,
    )
    if projected:
        game_state[PENDING_EXPLORATION_REACTION_KEY] = projected
    else:
        game_state.pop(PENDING_EXPLORATION_REACTION_KEY, None)


def resolve_pending_exploration_reaction(
    *,
    session: Session,
    reactor: Character,
    target: Character,
    accept: bool,
) -> dict[str, Any]:
    pending = pending_exploration_reaction(session)
    if not pending:
        raise ValueError("No pending exploration reaction.")
    if str(pending.get("reactor_character_id") or "") != str(reactor.id):
        raise ValueError("This character is not the pending reactor.")
    if str(pending.get("target_character_id") or "") != str(target.id):
        raise ValueError("Pending reaction target mismatch.")

    trap = pending.get("trap") if isinstance(pending.get("trap"), dict) else {}
    resolution = (
        pending.get("trap_resolution")
        if isinstance(pending.get("trap_resolution"), dict)
        else None
    )
    if resolution is None:
        resolution = resolve_trap_trigger(trap, target)

    if accept:
        result = apply_trap_resolution_to_target(
            resolution,
            target,
            trap=trap,
            feather_fall_caster=reactor,
            feather_fall_reaction_state={},
        )
    else:
        result = apply_trap_resolution_to_target(
            resolution,
            target,
            trap=trap,
        )
        result["reaction_declined"] = {
            "type": "feather_fall",
            "reactor_character_id": str(reactor.id),
            "reactor_character_name": reactor.name,
        }

    clear_pending_exploration_reaction(session)
    return result


def user_can_answer_exploration_reaction(
    prompt: dict[str, Any] | None,
    *,
    user_id: str,
    character_id: str | None,
    session: Session,
) -> bool:
    if not isinstance(prompt, dict):
        return False
    reactor_user_id = prompt.get("reactor_user_id")
    if reactor_user_id:
        return str(reactor_user_id) == str(user_id)
    if session.is_multiplayer:
        return False
    return (
        str(session.user_id or "") == str(user_id)
        or str(prompt.get("reactor_character_id") or "") == str(character_id or "")
    )


def _viewer_can_see_prompt(
    prompt: dict[str, Any],
    *,
    viewer_character_id: str | None,
    viewer_user_id: str | None,
) -> bool:
    reactor_character_id = prompt.get("reactor_character_id")
    reactor_user_id = prompt.get("reactor_user_id")
    return (
        reactor_character_id is not None
        and viewer_character_id is not None
        and str(reactor_character_id) == str(viewer_character_id)
    ) or (
        reactor_user_id is not None
        and viewer_user_id is not None
        and str(reactor_user_id) == str(viewer_user_id)
    )


def _reaction_user_id(session: Session, caster: Character) -> str | None:
    if getattr(caster, "user_id", None):
        return str(caster.user_id)
    if not session.is_multiplayer and session.user_id:
        return str(session.user_id)
    return None


def _pending_reaction_id(
    session: Session,
    resolution: dict[str, Any],
    caster: Character,
    target: Character,
) -> str:
    pieces = [
        "explore",
        "feather_fall",
        str(session.id),
        str(resolution.get("trap_id") or "trap"),
        str(target.id),
        str(caster.id),
    ]
    return ":".join(pieces)
