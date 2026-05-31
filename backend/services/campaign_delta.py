"""Campaign delta normalization and merge helpers.

These helpers keep DM-generated campaign memory updates deterministic before
they touch persisted session.campaign_state.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _strict_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _clean_text(value: Any, limit: int = 120) -> str:
    return str(value or "").strip()[:limit]


def _clean_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def _unique_append(items: list, value: Any, limit: int | None = None) -> list:
    if value not in items:
        items.append(value)
    return items[-limit:] if limit else items


def _recent_update(
    update_type: str,
    label: Any,
    detail: Any = "",
    now_iso: str | None = None,
    extra: dict | None = None,
) -> dict | None:
    label_text = _clean_text(label, 120)
    if not label_text:
        return None
    entry = {
        "type": _clean_text(update_type, 24),
        "label": label_text,
        "detail": _clean_text(detail, 180),
        "at": now_iso or (datetime.utcnow().isoformat() + "Z"),
    }
    if extra:
        entry.update({k: v for k, v in extra.items() if v is not None})
    return entry


def _normalize_scene_route(scene_vibe: dict[str, Any]) -> dict[str, Any]:
    route = scene_vibe.get("route") if isinstance(scene_vibe.get("route"), dict) else {}
    normalized: dict[str, Any] = {}
    for key, aliases, limit in (
        ("type", ("type", "route_type", "kind"), 32),
        ("label", ("label", "route_label", "name"), 80),
        ("status", ("status", "route_status"), 32),
        ("requires_key", ("requires_key", "key", "key_item"), 80),
        ("check_type", ("check_type", "skill", "skill_check"), 40),
    ):
        value = None
        for alias in aliases:
            if route.get(alias) is not None:
                value = route.get(alias)
                break
            if scene_vibe.get(alias) is not None:
                value = scene_vibe.get(alias)
                break
        text = _clean_text(value, limit)
        if text:
            normalized[key] = text

    dc = route.get("dc", route.get("check_dc", scene_vibe.get("dc", scene_vibe.get("check_dc"))))
    if dc is not None:
        try:
            normalized["dc"] = int(dc)
        except (TypeError, ValueError):
            text = _clean_text(dc, 20)
            if text:
                normalized["dc"] = text

    for key, aliases in (
        ("locked", ("locked", "route_locked")),
        ("hidden", ("hidden", "secret", "route_hidden")),
        ("one_way", ("one_way", "oneWay", "oneway", "route_one_way")),
    ):
        for alias in aliases:
            if route.get(alias) is not None:
                normalized[key] = _clean_bool(route.get(alias))
                break
            if scene_vibe.get(alias) is not None:
                normalized[key] = _clean_bool(scene_vibe.get(alias))
                break

    return normalized


def normalize_campaign_delta(delta: Any) -> dict:
    delta = delta if isinstance(delta, dict) else {}

    quest_updates = []
    for item in delta.get("quest_updates", []):
        if not isinstance(item, dict) or not item.get("quest"):
            continue
        quest_updates.append({
            "quest": _clean_text(item.get("quest"), 80),
            "status": _clean_text(item.get("status") or "active", 20),
            "outcome": _clean_text(item.get("outcome"), 160),
        })

    npc_updates = []
    for item in delta.get("npc_updates", []):
        if not isinstance(item, dict) or not item.get("name"):
            continue
        entry = {
            "name": _clean_text(item.get("name"), 40),
            "relationship": _clean_text(item.get("relationship") or "未知", 20),
            "key_facts": [_clean_text(v, 80) for v in _as_list(item.get("key_facts")) if _clean_text(v)],
            "promises": [_clean_text(v, 80) for v in _as_list(item.get("promises")) if _clean_text(v)],
        }
        npc_updates.append(entry)

    clues_add = []
    for item in delta.get("clues_add", []):
        if not isinstance(item, dict) or not item.get("text"):
            continue
        clues_add.append({
            "text": _clean_text(item.get("text"), 80),
            "category": _clean_text(item.get("category") or "general", 24),
        })

    scene_vibe = delta.get("scene_vibe")
    if isinstance(scene_vibe, dict):
        raw_scene_vibe = scene_vibe
        scene_vibe = {
            "location": _clean_text(scene_vibe.get("location"), 40) or None,
            "time_of_day": _clean_text(scene_vibe.get("time_of_day"), 20) or None,
            "tension": _clean_text(scene_vibe.get("tension"), 20) or None,
        }
        location_id = _clean_text(raw_scene_vibe.get("location_id"), 80)
        if location_id:
            scene_vibe["location_id"] = location_id
        route = _normalize_scene_route(raw_scene_vibe)
        if route:
            scene_vibe["route"] = route
    else:
        scene_vibe = None

    world_flags = delta.get("world_flags_set", {})
    if not isinstance(world_flags, dict):
        world_flags = {}

    return {
        "quest_updates": quest_updates,
        "npc_updates": npc_updates,
        "key_decisions_add": [_clean_text(v, 120) for v in _strict_list(delta.get("key_decisions_add")) if _clean_text(v)],
        "world_flags_set": dict(world_flags),
        "clues_add": clues_add,
        "scene_vibe": scene_vibe,
    }


def apply_campaign_delta(existing_state: dict | None, delta: Any, now_iso: str | None = None) -> dict:
    now_iso = now_iso or (datetime.utcnow().isoformat() + "Z")
    delta = normalize_campaign_delta(delta)
    merged = deepcopy(existing_state or {})
    recent_updates = [
        dict(item)
        for item in _strict_list(merged.get("recent_updates"))
        if isinstance(item, dict) and item.get("label")
    ]

    quest_map = {
        q.get("quest"): dict(q)
        for q in merged.get("quest_log", [])
        if isinstance(q, dict) and q.get("quest")
    }
    for update in delta["quest_updates"]:
        quest_map[update["quest"]] = update
        recent = _recent_update(
            "quest",
            update["quest"],
            update.get("outcome") or update.get("status"),
            now_iso,
            {"status": update.get("status")},
        )
        if recent:
            recent_updates.append(recent)
    if quest_map:
        merged["quest_log"] = list(quest_map.values())

    npc_registry = deepcopy(merged.get("npc_registry", {}))
    if not isinstance(npc_registry, dict):
        npc_registry = {}
    for update in delta["npc_updates"]:
        name = update["name"]
        current = npc_registry.get(name, {}) if isinstance(npc_registry.get(name, {}), dict) else {}
        facts = list(current.get("key_facts", []) or [])
        promises = list(current.get("promises", []) or [])
        for fact in update["key_facts"]:
            _unique_append(facts, fact, limit=8)
        for promise in update["promises"]:
            _unique_append(promises, promise, limit=8)
        npc_registry[name] = {
            **current,
            "relationship": update["relationship"] or current.get("relationship", "未知"),
            "key_facts": facts,
            "promises": promises,
        }
        detail_parts = [update["relationship"]]
        if update["key_facts"]:
            detail_parts.append(update["key_facts"][-1])
        elif update["promises"]:
            detail_parts.append(update["promises"][-1])
        recent = _recent_update("npc", name, " / ".join(part for part in detail_parts if part), now_iso)
        if recent:
            recent_updates.append(recent)
    if npc_registry:
        merged["npc_registry"] = npc_registry

    decisions = list(merged.get("key_decisions", []) or [])
    for decision in delta["key_decisions_add"]:
        is_new_decision = decision not in decisions
        decisions = _unique_append(decisions, decision, limit=20)
        if is_new_decision:
            recent = _recent_update("decision", decision, "关键决定", now_iso)
            if recent:
                recent_updates.append(recent)
    if decisions:
        merged["key_decisions"] = decisions

    world_flags = dict(merged.get("world_flags", {}) or {})
    world_flags.update(delta["world_flags_set"])
    for key, value in delta["world_flags_set"].items():
        recent = _recent_update("world", key, "已触发" if value else "已清除", now_iso)
        if recent:
            recent_updates.append(recent)
    if world_flags:
        merged["world_flags"] = world_flags

    clues = list(merged.get("clues", []) or [])
    seen_clues = {
        str(c.get("text") if isinstance(c, dict) else c).strip()
        for c in clues
        if str(c.get("text") if isinstance(c, dict) else c).strip()
    }
    for clue in delta["clues_add"]:
        if clue["text"] in seen_clues:
            continue
        clues.append({
            "text": clue["text"],
            "category": clue["category"],
            "found_at": now_iso,
            "is_new": True,
        })
        recent = _recent_update("clue", clue["text"], clue["category"], now_iso)
        if recent:
            recent_updates.append(recent)
        seen_clues.add(clue["text"])
    if clues:
        merged["clues"] = clues[-40:]

    if recent_updates:
        merged["recent_updates"] = recent_updates[-12:]

    return merged
