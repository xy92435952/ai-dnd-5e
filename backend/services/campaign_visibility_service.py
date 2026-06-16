from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


HIDDEN_STATUS_VALUES = {
    "hidden",
    "secret",
    "private",
    "dm_only",
    "dm-only",
    "dmonly",
    "unrevealed",
    "undiscovered",
    "unknown",
    "locked",
    "future",
}

PRIVATE_SCOPE_VALUES = {
    "dm",
    "dm_only",
    "dm-only",
    "dmonly",
    "private",
    "group",
    "party",
    "limited",
}

CLUE_REFERENCE_KEYS = {
    "related_clues",
    "linked_clues",
    "clue_ids",
    "clueids",
    "clue_refs",
}


def public_campaign_state(campaign_state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(campaign_state, dict):
        return {}

    public_clues, public_clue_identities, hidden_clue_identities = _clue_visibility_sets(campaign_state)
    sanitized = _sanitize_value(
        campaign_state,
        key="",
        public_clue_identities=public_clue_identities,
        hidden_clue_identities=hidden_clue_identities,
    )
    if not isinstance(sanitized, dict):
        return {}

    if "clues" in campaign_state or public_clues:
        sanitized["clues"] = public_clues

    if "recent_updates" in campaign_state:
        sanitized["recent_updates"] = [
            item for item in (
                _sanitize_value(
                    update,
                    key="recent_updates",
                    public_clue_identities=public_clue_identities,
                    hidden_clue_identities=hidden_clue_identities,
                )
                for update in _filter_public_recent_updates(
                    campaign_state.get("recent_updates"),
                    raw_clues=_as_list(campaign_state.get("clues")),
                    public_clue_identities=public_clue_identities,
                )
            )
            if isinstance(item, dict)
        ]

    return sanitized


def public_game_state(
    game_state: dict[str, Any] | None,
    campaign_state: dict[str, Any] | None,
    *,
    viewer_character_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(game_state, dict):
        return {}

    public_state = deepcopy(game_state)
    _sanitize_trap_state_feather_fall(public_state, viewer_character_id=viewer_character_id)
    if isinstance(campaign_state, dict):
        _, public_clue_identities, hidden_clue_identities = _clue_visibility_sets(campaign_state)
    else:
        public_clue_identities = set()
        hidden_clue_identities = set()
    last_turn = public_state.get("last_turn")
    if isinstance(last_turn, dict):
        sanitized_last_turn = _sanitize_value(
            last_turn,
            key="last_turn",
            public_clue_identities=public_clue_identities,
            hidden_clue_identities=hidden_clue_identities,
        )
        if isinstance(sanitized_last_turn, dict):
            public_state["last_turn"] = sanitized_last_turn
        else:
            public_state.pop("last_turn", None)

    return public_state


def _sanitize_trap_state_feather_fall(
    game_state: dict[str, Any],
    *,
    viewer_character_id: str | None,
) -> None:
    trap_states = game_state.get("trap_states")
    if not isinstance(trap_states, dict):
        return
    for trap_state in trap_states.values():
        if not isinstance(trap_state, dict):
            continue
        last_trigger = trap_state.get("last_trigger")
        if not isinstance(last_trigger, dict):
            continue
        feather_fall = last_trigger.get("feather_fall")
        if not isinstance(feather_fall, dict):
            continue
        caster_id = feather_fall.get("caster_id")
        if _viewer_matches_character(viewer_character_id, caster_id):
            continue
        feather_fall.pop("spell_slots", None)


def public_log_entry(
    log_entry: dict[str, Any] | None,
    campaign_state: dict[str, Any] | None,
    *,
    viewer_character_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(log_entry, dict):
        return {}
    entry = _public_ready_action_log_entry(log_entry, viewer_character_id=viewer_character_id)
    if not isinstance(campaign_state, dict):
        return entry

    redactions = _hidden_clue_redaction_values(campaign_state)
    if not redactions:
        return entry
    return _redact_hidden_strings(entry, redactions)


def _public_ready_action_log_entry(
    log_entry: dict[str, Any],
    *,
    viewer_character_id: str | None,
) -> dict[str, Any]:
    entry = deepcopy(log_entry)
    dice = entry.get("dice_result")
    if not isinstance(dice, dict):
        return entry

    dice_type = dice.get("type")
    ready_payload = dice.get("ready_action") if isinstance(dice.get("ready_action"), dict) else None
    target_state = dice.get("target_state") if isinstance(dice.get("target_state"), dict) else None
    target_ready_action_failed = (
        target_state.get("ready_action_failed")
        if isinstance(target_state, dict)
        else None
    )
    actor_id = (
        (ready_payload or {}).get("actor_id")
        or dice.get("actor_id")
        or ((dice.get("ready_action_failed") or {}).get("actor_id") if isinstance(dice.get("ready_action_failed"), dict) else None)
        or ((target_ready_action_failed or {}).get("actor_id") if isinstance(target_ready_action_failed, dict) else None)
    )
    if not actor_id or _viewer_matches_character(viewer_character_id, actor_id):
        return entry

    actor_name = (
        (ready_payload or {}).get("actor_name")
        or dice.get("actor_name")
        or dice.get("target_name")
        or "A combatant"
    )
    if dice_type == "ready_action_declared":
        entry["content"] = f"{actor_name} readies an action."
        entry["dice_result"] = {
            "type": "ready_action_declared",
            "ready_action": _redacted_ready_action_payload(ready_payload, "ready_action"),
        }
        return entry

    if dice_type == "ready_action_expired":
        entry["content"] = f"{actor_name}'s readied action expires."
        entry["dice_result"] = _redacted_ready_action_payload(dice, "ready_action_expired")
        return entry

    if dice_type == "concentration_end" and isinstance(dice.get("ready_action_failed"), dict):
        entry["content"] = f"{actor_name} ends concentration."
        entry["dice_result"] = _redact_ready_action_failed_dice(dice)
        return entry

    if dice_type == "condition_update" and isinstance(target_ready_action_failed, dict):
        entry["dice_result"] = _redact_ready_action_failed_dice(dice)
        return entry

    if dice_type == "enemy_inspect":
        entry["dice_result"] = _redact_enemy_inspect_payload(dice)
        return entry

    if dice_type == "ready_action":
        clean = _redact_ready_action_result_payload(dice)
        entry["dice_result"] = clean
    return entry


def _redact_ready_action_failed_dice(value: dict[str, Any]) -> dict[str, Any]:
    clean = deepcopy(value)
    clean["concentration_spell_name"] = None
    if isinstance(clean.get("ready_action_failed"), dict):
        clean["ready_action_failed"] = _redacted_ready_action_payload(
            clean["ready_action_failed"],
            "ready_action_failed",
        )
    if isinstance(clean.get("actor_state"), dict):
        actor_state = dict(clean["actor_state"])
        if isinstance(actor_state.get("ready_action_failed"), dict):
            actor_state["ready_action_failed"] = _redacted_ready_action_payload(
                actor_state["ready_action_failed"],
                "ready_action_failed",
            )
        clean["actor_state"] = actor_state
    if isinstance(clean.get("caster_state"), dict):
        caster_state = dict(clean["caster_state"])
        if isinstance(caster_state.get("ready_action_failed"), dict):
            caster_state["ready_action_failed"] = _redacted_ready_action_payload(
                caster_state["ready_action_failed"],
                "ready_action_failed",
            )
        clean["caster_state"] = caster_state
    if isinstance(clean.get("target_state"), dict):
        target_state = dict(clean["target_state"])
        if isinstance(target_state.get("ready_action_failed"), dict):
            target_state["ready_action_failed"] = _redacted_ready_action_payload(
                target_state["ready_action_failed"],
                "ready_action_failed",
            )
        clean["target_state"] = target_state
    return clean


def _redact_ready_action_result_payload(value: Any) -> Any:
    private_keys = {
        "condition_text",
        "trigger",
        "trigger_match",
        "slot_already_consumed",
        "slot_key",
        "slots_remaining",
        "concentration_spell_name",
    }
    if isinstance(value, dict):
        return {
            key: _redact_ready_action_result_payload(child)
            for key, child in value.items()
            if key not in private_keys
        }
    if isinstance(value, list):
        return [_redact_ready_action_result_payload(item) for item in value]
    return deepcopy(value)


def _redacted_ready_action_payload(value: Any, kind: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "type": kind,
            "redacted": True,
            "visibility": "other_character",
        }
    return {
        "type": value.get("type") or kind,
        "redacted": True,
        "visibility": "other_character",
        "actor_id": value.get("actor_id"),
        "actor_name": value.get("actor_name"),
    }


def _redact_enemy_inspect_payload(value: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {
        "type": "enemy_inspect",
        "redacted": True,
        "visibility": "other_character",
    }
    for key in (
        "actor_id",
        "actor_name",
        "target_id",
        "target_name",
        "skill",
        "dc",
        "success",
    ):
        if key in value:
            clean[key] = value.get(key)
    if isinstance(value.get("check"), dict):
        clean["check"] = deepcopy(value["check"])
    return clean


def _viewer_matches_character(viewer_character_id: str | None, character_id: Any) -> bool:
    return (
        viewer_character_id is not None
        and character_id is not None
        and str(viewer_character_id) == str(character_id)
    )


def public_text(
    text: Any,
    campaign_state: dict[str, Any] | None,
) -> str:
    value = str(text or "")
    if not isinstance(campaign_state, dict):
        return value
    redactions = _hidden_clue_redaction_values(campaign_state)
    if not redactions:
        return value
    return _redact_hidden_strings(value, redactions)


def _clue_visibility_sets(
    campaign_state: dict[str, Any],
) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    raw_clues = [item for item in _as_list(campaign_state.get("clues"))]
    public_clues = [
        deepcopy(clue)
        for clue in raw_clues
        if _is_public_clue(clue)
    ]
    public_clue_identities = {
        identity
        for clue in public_clues
        for identity in _clue_identity_values(clue)
    }
    hidden_clue_identities = {
        identity
        for clue in raw_clues
        if isinstance(clue, dict) and not _is_public_clue(clue)
        for identity in _clue_identity_values(clue)
    }
    return public_clues, public_clue_identities, hidden_clue_identities


def _hidden_clue_redaction_values(campaign_state: dict[str, Any]) -> list[str]:
    _, public_clue_identities, hidden_clue_identities = _clue_visibility_sets(campaign_state)
    values: set[str] = set()
    for clue in _as_list(campaign_state.get("clues")):
        if not isinstance(clue, dict) or _is_public_clue(clue):
            continue
        for value in _clue_identity_raw_values(clue):
            identity = _normalize_identity(value)
            if identity and identity in hidden_clue_identities and identity not in public_clue_identities:
                values.add(value)
    return sorted(values, key=len, reverse=True)


def _redact_hidden_strings(value: Any, redactions: list[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact_hidden_strings(child, redactions)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_redact_hidden_strings(item, redactions) for item in value]
    if isinstance(value, str):
        redacted = value
        for secret in redactions:
            if len(secret) < 4:
                continue
            redacted = re.sub(re.escape(secret), "[hidden]", redacted, flags=re.IGNORECASE)
        return redacted
    return deepcopy(value)


def _sanitize_value(
    value: Any,
    *,
    key: str,
    public_clue_identities: set[str],
    hidden_clue_identities: set[str],
) -> Any:
    normalized_key = _normalize_status(key)

    if isinstance(value, dict):
        if key and _is_explicitly_hidden_record(value):
            return None
        sanitized: dict[str, Any] = {}
        for child_key, child_value in value.items():
            clean_child = _sanitize_value(
                child_value,
                key=str(child_key),
                public_clue_identities=public_clue_identities,
                hidden_clue_identities=hidden_clue_identities,
            )
            if clean_child is None:
                continue
            sanitized[child_key] = clean_child
        if normalized_key == "player_choices" and _choice_lost_public_text(value, sanitized):
            return None
        return sanitized

    if isinstance(value, list):
        if normalized_key == "clues":
            return [
                deepcopy(item)
                for item in value
                if _is_public_clue(item)
            ]
        if normalized_key in CLUE_REFERENCE_KEYS:
            return [
                item for item in (
                    _sanitize_clue_reference(
                        entry,
                        public_clue_identities=public_clue_identities,
                        hidden_clue_identities=hidden_clue_identities,
                    )
                    for entry in value
                )
                if item is not None
            ]
        return [
            item for item in (
                _sanitize_value(
                    entry,
                    key=key,
                    public_clue_identities=public_clue_identities,
                    hidden_clue_identities=hidden_clue_identities,
                )
                for entry in value
            )
            if item is not None
        ]

    if _is_hidden_clue_identity(value, public_clue_identities, hidden_clue_identities):
        return None

    return deepcopy(value)


def _sanitize_clue_reference(
    value: Any,
    *,
    public_clue_identities: set[str],
    hidden_clue_identities: set[str],
) -> Any:
    if isinstance(value, dict):
        identities = set(_clue_identity_values(value))
        if identities & hidden_clue_identities:
            return None
        if identities and public_clue_identities and not (identities & public_clue_identities):
            return None
        if not identities and public_clue_identities:
            return None
        return _sanitize_value(
            value,
            key="clue_reference",
            public_clue_identities=public_clue_identities,
            hidden_clue_identities=hidden_clue_identities,
        )

    identity = _normalize_identity(value)
    if not identity:
        return None
    if identity in hidden_clue_identities:
        return None
    if public_clue_identities and identity not in public_clue_identities:
        return None
    return deepcopy(value)


def _filter_public_recent_updates(
    updates: Any,
    *,
    raw_clues: list[Any],
    public_clue_identities: set[str],
) -> list[dict[str, Any]]:
    public_updates = []
    for update in _as_list(updates):
        if _is_public_recent_update(
            update,
            raw_clues=raw_clues,
            public_clue_identities=public_clue_identities,
        ):
            public_updates.append(update)
    return public_updates


def _is_public_recent_update(
    update: Any,
    *,
    raw_clues: list[Any],
    public_clue_identities: set[str],
) -> bool:
    if not isinstance(update, dict):
        return False
    if _is_explicitly_hidden_record(update):
        return False
    if _normalize_status(update.get("type")) != "clue":
        return True

    display_text = _clean_text(
        update.get("text")
        or update.get("label")
        or update.get("name")
        or update.get("detail")
        or update.get("clue_id")
        or update.get("clueId")
        or update.get("id")
        or update.get("key")
    )
    if not _is_public_clue({**update, "text": display_text}):
        return False
    if not raw_clues:
        return True

    identities = _clue_update_identity_values(update)
    if not identities:
        return True
    return any(identity in public_clue_identities for identity in identities)


def _is_public_clue(clue: Any) -> bool:
    if not isinstance(clue, dict):
        return False
    if not _clean_text(clue.get("text")):
        return False
    if any(_is_true_marker(clue.get(key)) for key in ("hidden", "secret", "private", "dm_only", "dmOnly")):
        return False
    if any(
        _is_false_marker(clue.get(key))
        for key in ("visible", "revealed", "discovered", "public", "player_visible", "playerVisible")
    ):
        return False
    if any(_is_hidden_status(clue.get(key)) for key in ("status", "state")):
        return False
    visibility = clue.get("visibility")
    if isinstance(visibility, str) and _is_hidden_status(visibility):
        return False
    if _is_hidden_visibility_object(visibility):
        return False
    return True


def _is_explicitly_hidden_record(value: dict[str, Any]) -> bool:
    if any(_is_true_marker(value.get(key)) for key in ("hidden", "secret", "private", "dm_only", "dmOnly")):
        return True
    if any(
        _is_false_marker(value.get(key))
        for key in ("visible", "revealed", "discovered", "public", "player_visible", "playerVisible")
    ):
        return True
    if any(_is_hidden_status(value.get(key)) for key in ("status", "state")):
        return True
    visibility = value.get("visibility")
    if isinstance(visibility, str) and _is_hidden_status(visibility):
        return True
    return _is_hidden_visibility_object(visibility)


def _choice_lost_public_text(raw: dict[str, Any], sanitized: dict[str, Any]) -> bool:
    if "text" not in raw:
        return False
    return "text" not in sanitized


def _is_hidden_clue_identity(
    value: Any,
    public_clue_identities: set[str],
    hidden_clue_identities: set[str],
) -> bool:
    identity = _normalize_identity(value)
    return bool(
        identity
        and identity in hidden_clue_identities
        and identity not in public_clue_identities
    )


def _is_hidden_visibility_object(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if any(_is_true_marker(value.get(key)) for key in ("hidden", "secret", "private", "dm_only", "dmOnly")):
        return True
    if any(
        _is_false_marker(value.get(key))
        for key in ("public", "visible", "revealed", "discovered", "player_visible", "playerVisible")
    ):
        return True
    if any(_is_hidden_status(value.get(key)) for key in ("status", "state", "scope", "audience", "access")):
        return True
    scope = _normalize_status(value.get("scope") or value.get("audience") or value.get("access"))
    return scope in PRIVATE_SCOPE_VALUES and not _has_explicit_public_visibility(value)


def _has_explicit_public_visibility(value: dict[str, Any]) -> bool:
    return any(
        _is_true_marker(value.get(key))
        for key in ("public", "visible", "revealed", "discovered", "player_visible", "playerVisible")
    )


def _clue_identity_values(clue: Any) -> list[str]:
    if not isinstance(clue, dict):
        return []
    return [
        item for item in (
            _normalize_identity(clue.get("id")),
            _normalize_identity(clue.get("key")),
            _normalize_identity(clue.get("clue_id")),
            _normalize_identity(clue.get("clueId")),
            _normalize_identity(clue.get("text")),
            _normalize_identity(clue.get("label")),
            _normalize_identity(clue.get("name")),
        )
        if item
    ]


def _clue_identity_raw_values(clue: Any) -> list[str]:
    if not isinstance(clue, dict):
        return []
    return [
        item for item in (
            _clean_text(clue.get("id")),
            _clean_text(clue.get("key")),
            _clean_text(clue.get("clue_id")),
            _clean_text(clue.get("clueId")),
            _clean_text(clue.get("text")),
            _clean_text(clue.get("label")),
            _clean_text(clue.get("name")),
        )
        if item
    ]


def _clue_update_identity_values(update: Any) -> list[str]:
    if not isinstance(update, dict):
        return []
    return [
        item for item in (
            _normalize_identity(update.get("clue_id")),
            _normalize_identity(update.get("clueId")),
            _normalize_identity(update.get("clue")),
            _normalize_identity(update.get("id")),
            _normalize_identity(update.get("key")),
            _normalize_identity(update.get("text")),
            _normalize_identity(update.get("label")),
            _normalize_identity(update.get("name")),
        )
        if item
    ]


def _is_true_marker(value: Any) -> bool:
    if value is True:
        return True
    return _normalize_status(value) in {"true", "1", "yes", "y"}


def _is_false_marker(value: Any) -> bool:
    if value is False:
        return True
    return _normalize_status(value) in {"false", "0", "no", "n"}


def _is_hidden_status(value: Any) -> bool:
    return _normalize_status(value) in HIDDEN_STATUS_VALUES


def _normalize_status(value: Any) -> str:
    return _clean_text(value).lower().replace(" ", "_")


def _normalize_identity(value: Any) -> str:
    return " ".join(
        _clean_text(value)
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
