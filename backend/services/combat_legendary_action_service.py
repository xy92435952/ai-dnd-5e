"""Helpers for monster Legendary Action resources."""

from __future__ import annotations

import re
import math
from typing import Any


def normalize_legendary_actions(value: Any) -> list[dict[str, Any]]:
    """Return a clean list of legendary action definitions."""
    if not isinstance(value, list):
        return []

    actions: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, dict):
            name = str(item.get("name") or f"Legendary Action {index + 1}").strip()
            action = dict(item)
        elif isinstance(item, str):
            name = item.strip() or f"Legendary Action {index + 1}"
            action = {"name": name, "description": item}
        else:
            continue

        action["id"] = str(action.get("id") or _legendary_action_id(name, index))
        action["name"] = name
        action["cost"] = _normalize_action_cost(action.get("cost", action.get("points", 1)))
        actions.append(action)
    return actions


def normalize_lair_actions(value: Any) -> list[dict[str, Any]]:
    """Return a clean list of lair action definitions."""
    if not isinstance(value, list):
        return []

    actions: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, dict):
            name = str(item.get("name") or f"Lair Action {index + 1}").strip()
            action = dict(item)
        elif isinstance(item, str):
            name = item.strip() or f"Lair Action {index + 1}"
            action = {"name": name, "description": item}
        else:
            continue

        action["id"] = str(action.get("id") or _lair_action_id(name, index))
        action["name"] = name
        action["cost"] = _normalize_action_cost(action.get("cost", action.get("points", 1)))
        actions.append(action)
    return actions


def normalize_legendary_action_uses(value: Any, *, actions: list[dict[str, Any]] | None = None) -> int:
    """Read the per-round Legendary Action pool, defaulting to 3 when actions exist."""
    if isinstance(value, bool) or value is None:
        return 3 if actions else 0
    if isinstance(value, (int, float)):
        return max(0, int(value))

    text = str(value).strip()
    digits = re.findall(r"\d+", text)
    if digits:
        return max(0, int(digits[0]))
    return 3 if actions else 0


def initialize_legendary_actions(enemy: dict[str, Any]) -> dict[str, int]:
    """Normalize legendary actions and ensure max/remaining resource fields exist."""
    actions = normalize_legendary_actions(enemy.get("legendary_actions"))
    uses = normalize_legendary_action_uses(
        enemy.get("legendary_action_uses", enemy.get("legendary_actions_per_round")),
        actions=actions,
    )
    raw_remaining = enemy.get("legendary_action_uses_remaining")
    if raw_remaining is None:
        remaining = uses
    else:
        remaining = min(uses, normalize_legendary_action_uses(raw_remaining, actions=actions))

    enemy["legendary_actions"] = actions
    enemy["legendary_action_uses"] = uses
    enemy["legendary_action_uses_remaining"] = remaining
    return {"uses": uses, "remaining": remaining}


def refresh_legendary_actions_for_turn_start(enemy: dict[str, Any] | None) -> dict[str, Any]:
    """Refresh one surviving monster's Legendary Action pool at the start of its turn."""
    if not enemy:
        return {"changed": False, "refreshed": None}

    before_remaining = enemy.get("legendary_action_uses_remaining")
    state = initialize_legendary_actions(enemy)
    if not enemy.get("legendary_actions") or enemy.get("hp_current", 0) <= 0:
        return {"changed": False, "refreshed": None}

    changed = before_remaining != state["uses"]
    if changed:
        enemy["legendary_action_uses_remaining"] = state["uses"]
    return {
        "changed": changed,
        "refreshed": {
            "enemy_id": enemy.get("id"),
            "name": enemy.get("name"),
            "uses": state["uses"],
        } if changed else None,
    }


def refresh_legendary_actions_for_new_round(enemies: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Refresh each surviving monster's Legendary Action pool at the start of a round."""
    changed = False
    refreshed: list[dict[str, Any]] = []
    for enemy in enemies or []:
        result = refresh_legendary_actions_for_turn_start(enemy)
        if result["changed"]:
            changed = True
            refreshed.append(result["refreshed"])
    return {"changed": changed, "refreshed": refreshed}


def build_legendary_action_prompt(
    enemies: list[dict[str, Any]] | None,
    *,
    trigger_entity_id: str | None = None,
    trigger_entity_name: str | None = None,
    positions: dict[str, Any] | None = None,
    target_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Build the first available end-of-turn Legendary Action prompt."""
    trigger_id = str(trigger_entity_id or "")
    for enemy in enemies or []:
        if not enemy or str(enemy.get("id") or "") == trigger_id:
            continue
        if int(enemy.get("hp_current", 0) or 0) <= 0:
            continue

        state = initialize_legendary_actions(enemy)
        remaining = state["remaining"]
        uses = state["uses"]
        if remaining <= 0 or uses <= 0:
            continue

        actions = [
            _legendary_action_prompt_option(
                action,
                remaining,
                actor=enemy,
                trigger_entity_id=trigger_entity_id,
                trigger_entity_name=trigger_entity_name,
                positions=positions,
                target_candidates=target_candidates,
            )
            for action in enemy.get("legendary_actions") or []
            if _normalize_action_cost(action.get("cost", 1)) <= remaining
        ]
        actions = [action for action in actions if action]
        if not actions:
            continue

        actor_name = str(enemy.get("name") or "Enemy")
        return {
            "trigger": "legendary_action",
            "trigger_entity_id": trigger_entity_id,
            "trigger_entity_name": trigger_entity_name,
            "actor_id": str(enemy.get("id")),
            "actor_name": actor_name,
            "remaining": remaining,
            "uses": uses,
            "context": (
                f"{actor_name} can use a Legendary Action"
                + (f" after {trigger_entity_name}'s turn." if trigger_entity_name else ".")
            ),
            "actions": actions,
        }
    return None


def build_lair_action_prompt(
    state: dict[str, Any] | None,
    enemies: list[dict[str, Any]] | None,
    *,
    round_number: int,
    timing: str = "round_start",
    trigger_entity_id: str | None = None,
    trigger_entity_name: str | None = None,
    positions: dict[str, Any] | None = None,
    target_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Build the first available initiative-count Lair Action prompt."""
    for source in _lair_action_sources(state, enemies):
        source_id = str(source.get("id") or "")
        actions = []
        for action in source.get("lair_actions") or []:
            option = _legendary_action_prompt_option(
                action,
                1,
                actor=source,
                trigger_entity_id=trigger_entity_id,
                trigger_entity_name=trigger_entity_name,
                positions=positions,
                target_candidates=target_candidates,
            )
            if not option:
                continue
            option.pop("cost", None)
            option.pop("remaining_after", None)
            actions.append(option)
        if not actions:
            continue

        source_name = str(source.get("name") or "Lair")
        timing_context = (
            f"{source_name} can use a Lair Action at initiative count 20 in round {round_number}."
            if timing == "initiative_count_20"
            else f"{source_name} can use a Lair Action at the start of round {round_number}."
        )
        return {
            "trigger": "lair_action",
            "timing": timing,
            "round_number": round_number,
            "trigger_entity_id": trigger_entity_id,
            "trigger_entity_name": trigger_entity_name,
            "source_id": source_id,
            "source_name": source_name,
            "actor_id": source_id,
            "actor_name": source_name,
            "context": timing_context,
            "actions": actions,
        }
    return None


def should_prompt_lair_action_for_turn_advance(
    turn_order: list[dict[str, Any]] | None,
    *,
    current_index: int,
    next_index: int,
    round_started: bool,
    initiative_count: int = 20,
) -> bool:
    """Return whether this turn advance crosses the Lair Action initiative count."""
    if not turn_order:
        return False

    current_entry = turn_order[current_index % len(turn_order)]
    next_entry = turn_order[next_index % len(turn_order)]
    current_initiative = _entry_initiative(current_entry)
    next_initiative = _entry_initiative(next_entry)

    if current_initiative is None or next_initiative is None:
        return bool(round_started)

    if round_started:
        return next_initiative < initiative_count or current_initiative >= initiative_count

    return current_initiative >= initiative_count and next_initiative < initiative_count


def find_lair_action(
    state: dict[str, Any] | None,
    enemies: list[dict[str, Any]] | None,
    *,
    source_id: str | None,
    action_id: str | None,
) -> dict[str, Any] | None:
    """Return the source/action pair for a Lair Action request."""
    requested_source = str(source_id or "")
    requested_action = _normalize_name(action_id)
    for source in _lair_action_sources(state, enemies):
        if requested_source and str(source.get("id") or "") != requested_source:
            continue
        actions = list(source.get("lair_actions") or [])
        if not actions:
            continue
        action = None
        if requested_action:
            action = next(
                (
                    item
                    for item in actions
                    if _normalize_name(item.get("id") or item.get("name")) == requested_action
                ),
                None,
            )
            if action is None:
                continue
        else:
            action = actions[0]
        return {"source": source, "action": action}
    return None


def _lair_action_sources(
    state: dict[str, Any] | None,
    enemies: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    state = state or {}

    top_actions = normalize_lair_actions(state.get("lair_actions") or state.get("lairActions"))
    if top_actions:
        sources.append({
            "id": str(state.get("lair_id") or state.get("lairId") or "lair"),
            "name": str(state.get("lair_name") or state.get("lairName") or "Lair"),
            "hp_current": 1,
            "lair_actions": top_actions,
        })

    for enemy in enemies or []:
        if not enemy:
            continue
        try:
            hp_current = int(enemy.get("hp_current", 0) or 0)
        except (TypeError, ValueError):
            hp_current = 0
        if hp_current <= 0:
            continue
        actions = normalize_lair_actions(enemy.get("lair_actions") or enemy.get("lairActions"))
        if not actions:
            continue
        source = dict(enemy)
        source["id"] = str(source.get("id") or "")
        source["name"] = str(source.get("name") or "Lair")
        source["lair_actions"] = actions
        sources.append(source)

    return sources


def spend_legendary_action(enemy: dict[str, Any] | None, action_id: str | None = None) -> dict[str, Any]:
    """Spend one legendary action definition if the monster has enough remaining uses."""
    if not enemy:
        return {"spent": False, "reason": "missing_enemy"}

    state = initialize_legendary_actions(enemy)
    actions = list(enemy.get("legendary_actions") or [])
    if not actions:
        return {"spent": False, "reason": "no_legendary_actions"}

    action = _choose_action(actions, action_id)
    if not action:
        return {"spent": False, "reason": "unknown_action"}

    cost = _normalize_action_cost(action.get("cost", 1))
    remaining = state["remaining"]
    if remaining < cost:
        return {"spent": False, "reason": "insufficient_uses", "remaining": remaining, "cost": cost}

    enemy["legendary_action_uses_remaining"] = remaining - cost
    return {
        "spent": True,
        "action": action,
        "cost": cost,
        "remaining": enemy["legendary_action_uses_remaining"],
    }


def _choose_action(actions: list[dict[str, Any]], action_id: str | None) -> dict[str, Any] | None:
    if action_id:
        for action in actions:
            if str(action.get("id")) == str(action_id) or _normalize_name(action.get("name")) == _normalize_name(action_id):
                return action
        return None
    return actions[0] if actions else None


def _legendary_action_prompt_option(
    action: dict[str, Any],
    remaining: int,
    *,
    actor: dict[str, Any] | None = None,
    trigger_entity_id: str | None = None,
    trigger_entity_name: str | None = None,
    positions: dict[str, Any] | None = None,
    target_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cost = _normalize_action_cost(action.get("cost", 1))
    target_ids = _coerce_target_ids(action.get("target_ids") or action.get("targetIds"))
    target_names = _coerce_target_names(action.get("target_names") or action.get("targetNames"))
    area_preview = None
    if not target_ids:
        area_preview = _legendary_area_preview(
            action,
            actor=actor,
            trigger_entity_id=trigger_entity_id,
            trigger_entity_name=trigger_entity_name,
            positions=positions,
            target_candidates=target_candidates,
        )
        if area_preview:
            target_ids = area_preview["target_ids"]
            target_names = area_preview["target_names"]
    explicit_target_name = _first_text(action, "target_name", "targetName")
    if explicit_target_name and not target_names:
        target_names = [explicit_target_name]
    option = {
        "id": str(action.get("id") or action.get("name") or ""),
        "name": str(action.get("name") or "Legendary Action"),
        "cost": cost,
        "description": str(action.get("description") or action.get("effect") or ""),
        "remaining_after": max(0, remaining - cost),
    }
    if target_ids:
        option["target_ids"] = target_ids
        option["target_count"] = len(target_ids)
        if target_names:
            option["target_names"] = target_names
            option["target_name"] = _target_name_summary(target_names)
        else:
            option["target_name"] = f"{len(target_ids)} targets"
    if area_preview:
        option.update({
            "area_template": area_preview["area_template"],
            "area_range_ft": area_preview["area_range_ft"],
            "area_anchor_id": area_preview.get("area_anchor_id"),
            "area_anchor_name": area_preview.get("area_anchor_name"),
        })
    if _is_save_legendary_action(action):
        option["resolution"] = "save"
        if trigger_entity_id and not target_ids:
            option["target_id"] = str(trigger_entity_id)
        if trigger_entity_name and not target_names:
            option["target_name"] = str(trigger_entity_name)
        save_ability = _first_text(action, "saving_throw", "save", "save_ability", "saving_throw_ability")
        if save_ability:
            option["save_ability"] = save_ability
        save_dc = _first_int(action, "save_dc", "dc", "saving_throw_dc")
        if save_dc is not None:
            option["save_dc"] = save_dc
        damage_dice = _first_text(action, "damage_dice", "damage")
        if damage_dice:
            option["damage_dice"] = damage_dice
        damage_type = _first_text(action, "damage_type", "type")
        if damage_type:
            option["damage_type"] = damage_type
        option["half_on_save"] = _half_on_save(action)
        conditions = _legendary_conditions(action)
        if conditions:
            option["condition_on_failed_save"] = conditions[0]
            option["conditions_on_failed_save"] = conditions
        duration_rounds = _legendary_condition_duration(action)
        if duration_rounds is not None:
            option["condition_duration_rounds"] = duration_rounds
        push_distance = _legendary_push_distance_ft(action)
        if push_distance is not None:
            option["push_distance_ft"] = push_distance
        else:
            pull_distance = _legendary_pull_distance_ft(action)
            if pull_distance is not None:
                option["pull_distance_ft"] = pull_distance
    elif _is_attack_legendary_action(action):
        option["resolution"] = "attack"
        if trigger_entity_id and not target_ids:
            option["target_id"] = str(trigger_entity_id)
        if trigger_entity_name and not target_names:
            option["target_name"] = str(trigger_entity_name)
        attack_bonus = _first_int(action, "attack_bonus", "to_hit", "hit_bonus", "attack_mod")
        if attack_bonus is not None:
            option["attack_bonus"] = attack_bonus
        damage_dice = _first_text(action, "damage_dice", "damage")
        if damage_dice:
            option["damage_dice"] = damage_dice
        damage_type = _first_text(action, "damage_type", "type")
        if damage_type:
            option["damage_type"] = damage_type
    return option


def _legendary_area_preview(
    action: dict[str, Any],
    *,
    actor: dict[str, Any] | None,
    trigger_entity_id: str | None,
    trigger_entity_name: str | None,
    positions: dict[str, Any] | None,
    target_candidates: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    if not _is_area_legendary_action(action) or not actor or not positions or not target_candidates:
        return None

    actor_id = str(actor.get("id") or "")
    actor_position = _position_for(positions, actor_id)
    if not actor_id or not actor_position:
        return None

    alive: list[dict[str, Any]] = []
    for candidate in target_candidates:
        candidate_id = str(candidate.get("id") or "")
        if not candidate_id or candidate_id == actor_id:
            continue
        try:
            hp_current = int(candidate.get("hp_current", 0) or 0)
        except (TypeError, ValueError):
            hp_current = 0
        if hp_current <= 0 or not _position_for(positions, candidate_id):
            continue
        alive.append(candidate)
    if not alive:
        return None

    template_type = _legendary_area_template_type(action)
    range_ft = _legendary_area_range_ft(action)
    range_tiles = max(1, math.ceil(range_ft / 5))
    anchor_id = str(trigger_entity_id or "")
    anchor_position = _position_for(positions, anchor_id)
    if template_type == "aura":
        anchor_id = actor_id
        anchor_position = actor_position
    if not anchor_position:
        anchor = min(
            alive,
            key=lambda item: (
                _chebyshev_distance(actor_position, _position_for(positions, str(item.get("id") or "")) or actor_position),
                str(item.get("id") or ""),
            ),
        )
        anchor_id = str(anchor.get("id") or "")
        anchor_position = _position_for(positions, anchor_id)
    if not anchor_position:
        return None

    selected: list[dict[str, Any]] = []
    for candidate in alive:
        candidate_id = str(candidate.get("id") or "")
        target_position = _position_for(positions, candidate_id)
        if not target_position:
            continue
        if _point_in_legendary_area(
            actor_position=actor_position,
            anchor_position=anchor_position,
            target_position=target_position,
            template_type=template_type,
            range_tiles=range_tiles,
        ):
            selected.append(candidate)

    if not selected:
        return None

    selected.sort(key=lambda item: (
        0 if str(item.get("id") or "") == str(trigger_entity_id or "") else 1,
        _chebyshev_distance(actor_position, _position_for(positions, str(item.get("id") or "")) or actor_position),
        str(item.get("id") or ""),
    ))
    max_targets = _legendary_max_area_targets(action, default=len(selected))
    selected = selected[:max_targets]
    target_ids = [str(item.get("id")) for item in selected]
    target_names = [str(item.get("name") or item.get("id")) for item in selected]
    anchor_name = (
        str(trigger_entity_name or "")
        if anchor_id and str(anchor_id) == str(trigger_entity_id or "")
        else next((str(item.get("name") or item.get("id")) for item in alive if str(item.get("id")) == anchor_id), "")
    )
    return {
        "target_ids": target_ids,
        "target_names": target_names,
        "area_template": "radius" if template_type == "aura" else template_type,
        "area_range_ft": range_ft,
        "area_anchor_id": anchor_id or None,
        "area_anchor_name": anchor_name or None,
    }


def _is_area_legendary_action(action: dict[str, Any]) -> bool:
    if action.get("aoe") is True:
        return True
    if str(action.get("targets") or "").strip().lower() in {"multiple", "area", "aoe"}:
        return True
    if _first_text(action, "area_template", "template", "shape"):
        return True
    text = _legendary_area_text(action)
    return any(
        marker in text
        for marker in (
            "cone",
            "line",
            "radius",
            "sphere",
            "burst",
            "aura",
            "each creature",
            "all creatures",
            "area",
        )
    )


def _legendary_area_template_type(action: dict[str, Any]) -> str:
    explicit = _first_text(action, "area_template", "template", "shape").lower()
    text = " ".join([explicit, _legendary_area_text(action)])
    if "cone" in text:
        return "cone"
    if "line" in text:
        return "line"
    if "aura" in text:
        return "aura"
    if any(marker in text for marker in ("radius", "sphere", "burst", "area")):
        return "radius"
    return "radius"


def _legendary_area_range_ft(action: dict[str, Any]) -> int:
    direct = _first_int(
        action,
        "area_range_ft",
        "areaRangeFt",
        "area_radius_ft",
        "areaRadiusFt",
        "radius_ft",
        "radiusFt",
        "range_ft",
        "rangeFt",
        "length_ft",
        "lengthFt",
    )
    if direct is not None:
        return max(5, direct)
    text = " ".join(
        str(action.get(key) or "")
        for key in ("area", "targeting", "description", "effect", "extra_effects", "reach_or_range", "range")
    )
    distances = [int(match) for match in re.findall(r"(\d+)\s*(?:ft|feet|foot)", text, flags=re.IGNORECASE)]
    if distances:
        return max(5, max(distances))
    return 30


def _legendary_max_area_targets(action: dict[str, Any], *, default: int) -> int:
    value = _first_int(action, "max_targets", "maxTargets", "target_limit", "targetLimit")
    if value is None:
        return max(0, default)
    return max(0, value)


def _legendary_area_text(action: dict[str, Any]) -> str:
    return " ".join(
        str(action.get(key) or "")
        for key in ("area", "targeting", "description", "effect", "extra_effects", "reach_or_range", "range")
    ).lower()


def _position_for(positions: dict[str, Any], entity_id: str) -> dict[str, int] | None:
    raw = (positions or {}).get(str(entity_id))
    if not isinstance(raw, dict):
        return None
    try:
        return {"x": int(raw.get("x")), "y": int(raw.get("y"))}
    except (TypeError, ValueError):
        return None


def _point_in_legendary_area(
    *,
    actor_position: dict[str, int],
    anchor_position: dict[str, int],
    target_position: dict[str, int],
    template_type: str,
    range_tiles: int,
) -> bool:
    if template_type in {"radius", "aura"}:
        origin = actor_position if template_type == "aura" else anchor_position
        return _chebyshev_distance(origin, target_position) <= range_tiles

    dx = target_position["x"] - actor_position["x"]
    dy = target_position["y"] - actor_position["y"]
    distance = max(abs(dx), abs(dy))
    if distance <= 0 or distance > range_tiles:
        return False

    direction = _template_direction(actor_position, anchor_position)
    if direction == (0, 0):
        return False
    if template_type == "line":
        return _point_on_line_template(dx, dy, direction, range_tiles)
    if template_type == "cone":
        return _point_in_cone_template(dx, dy, direction, range_tiles)
    return False


def _template_direction(
    actor_position: dict[str, int],
    anchor_position: dict[str, int],
) -> tuple[int, int]:
    return (
        _sign(anchor_position["x"] - actor_position["x"]),
        _sign(anchor_position["y"] - actor_position["y"]),
    )


def _point_on_line_template(
    dx: int,
    dy: int,
    direction: tuple[int, int],
    range_tiles: int,
) -> bool:
    step_x, step_y = direction
    if step_x == 0:
        return dx == 0 and _same_direction(dy, step_y) and abs(dy) <= range_tiles
    if step_y == 0:
        return dy == 0 and _same_direction(dx, step_x) and abs(dx) <= range_tiles
    return (
        abs(dx) == abs(dy)
        and _same_direction(dx, step_x)
        and _same_direction(dy, step_y)
        and abs(dx) <= range_tiles
    )


def _point_in_cone_template(
    dx: int,
    dy: int,
    direction: tuple[int, int],
    range_tiles: int,
) -> bool:
    distance = max(abs(dx), abs(dy))
    if distance <= 0 or distance > range_tiles:
        return False
    dir_x, dir_y = direction
    magnitude = math.hypot(dx, dy)
    dir_magnitude = math.hypot(dir_x, dir_y)
    if not magnitude or not dir_magnitude:
        return False
    cosine = ((dx * dir_x) + (dy * dir_y)) / (magnitude * dir_magnitude)
    return cosine >= math.cos(math.radians(45)) - 1e-9


def _same_direction(value: int, direction: int) -> bool:
    return direction == 0 or (value != 0 and _sign(value) == direction)


def _sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _chebyshev_distance(a: dict[str, int], b: dict[str, int]) -> int:
    return max(abs(int(a["x"]) - int(b["x"])), abs(int(a["y"]) - int(b["y"])))


def _coerce_target_ids(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    seen: set[str] = set()
    ids: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ids.append(text)
    return ids


def _coerce_target_names(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        return []
    names: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if text:
            names.append(text)
    return names


def _target_name_summary(names: list[str]) -> str:
    clean = [str(name or "").strip() for name in names if str(name or "").strip()]
    if len(clean) <= 3:
        return ", ".join(clean)
    return f"{', '.join(clean[:3])}, and {len(clean) - 3} more"


def _legendary_conditions(action: dict[str, Any]) -> list[str]:
    conditions: list[str] = []
    for key in ("condition_on_failed_save", "condition_name", "condition"):
        condition = _first_text(action, key)
        if condition:
            conditions.append(condition)
    values = action.get("conditions_on_failed_save") or action.get("conditionsOnFailedSave")
    if isinstance(values, list):
        for value in values:
            text = str(value or "").strip()
            if text:
                conditions.append(text)
    return list(dict.fromkeys(conditions))


def _legendary_condition_duration(action: dict[str, Any]) -> int | None:
    return _first_int(
        action,
        "condition_duration_rounds",
        "conditionDurationRounds",
        "duration_rounds",
        "durationRounds",
        "condition_duration",
        "conditionDuration",
    )


def _legendary_action_id(name: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"legendary_{slug or index + 1}"


def _lair_action_id(name: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"lair_{slug or index + 1}"


def _normalize_action_cost(value: Any) -> int:
    try:
        return max(1, int(value or 1))
    except (TypeError, ValueError):
        digits = re.findall(r"\d+", str(value or ""))
        return max(1, int(digits[0])) if digits else 1


def _normalize_name(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _entry_initiative(entry: dict[str, Any] | None) -> int | None:
    if not isinstance(entry, dict):
        return None
    value = entry.get("initiative")
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        digits = re.findall(r"-?\d+", str(value))
        return int(digits[0]) if digits else None


def _is_attack_legendary_action(action: dict[str, Any]) -> bool:
    if _is_save_legendary_action(action):
        return False
    if str(action.get("resolution") or action.get("kind") or action.get("type") or "").lower() == "attack":
        return True
    return any(key in action for key in ("attack_bonus", "to_hit", "hit_bonus", "attack_mod"))


def _is_save_legendary_action(action: dict[str, Any]) -> bool:
    action_type = str(action.get("resolution") or action.get("kind") or action.get("type") or "").lower()
    if action_type in {"save", "saving_throw", "saving throw"}:
        return True
    has_save_dc = any(key in action for key in ("save_dc", "dc", "saving_throw_dc"))
    has_save_ability = any(key in action for key in ("saving_throw", "save", "save_ability", "saving_throw_ability"))
    return has_save_dc and has_save_ability


def _half_on_save(action: dict[str, Any]) -> bool:
    if "half_on_save" in action:
        return bool(action.get("half_on_save"))
    text = " ".join(str(action.get(key) or "") for key in ("description", "effect", "name")).lower()
    return "half" in text or "save for half" in text or "successful save" in text


def _first_text(action: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = action.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _first_int(action: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = action.get(key)
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)):
            return int(value)
        digits = re.findall(r"-?\d+", str(value))
        if digits:
            return int(digits[0])
    return None


def _legendary_push_distance_ft(action: dict[str, Any]) -> int | None:
    return _legendary_movement_distance_ft(
        action,
        feet_keys=("push_distance_ft", "pushDistanceFt", "push_ft", "pushFeet", "knockback_ft"),
        tile_keys=("push_tiles", "pushTiles"),
        distance_key="push_distance",
    )


def _legendary_pull_distance_ft(action: dict[str, Any]) -> int | None:
    return _legendary_movement_distance_ft(
        action,
        feet_keys=("pull_distance_ft", "pullDistanceFt", "pull_ft", "pullFeet"),
        tile_keys=("pull_tiles", "pullTiles"),
        distance_key="pull_distance",
    )


def _legendary_movement_distance_ft(
    action: dict[str, Any],
    *,
    feet_keys: tuple[str, ...],
    tile_keys: tuple[str, ...],
    distance_key: str,
) -> int | None:
    forced = action.get("forced_movement") if isinstance(action.get("forced_movement"), dict) else {}

    for key in feet_keys:
        value = action.get(key, forced.get(key))
        if value is None:
            continue
        try:
            return max(5, int(value))
        except (TypeError, ValueError):
            continue

    for key in tile_keys:
        value = action.get(key, forced.get(key))
        if value is None:
            continue
        try:
            return max(1, int(value)) * 5
        except (TypeError, ValueError):
            continue

    value = action.get(distance_key, forced.get(distance_key))
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return max(1, number) * 5 if number <= 4 else max(5, number)
