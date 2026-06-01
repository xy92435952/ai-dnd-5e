"""Encounter template helpers for module-driven exploration.

Templates are stored in ``Session.game_state.location_graph`` so this early
slice can evolve without a schema migration. They are deterministic summaries
of likely fights inferred from parsed module scenes and monsters.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from services.encounter_balance_service import estimate_encounter_difficulty, monster_xp


ENCOUNTER_TEMPLATE_VERSION = 1
DIFFICULTY_ORDER = ["none", "easy", "medium", "hard", "deadly"]
DIFFICULTY_RANK = {"none": 0, "easy": 1, "medium": 2, "hard": 3, "deadly": 4}
COMBAT_HINTS = {
    "ambush",
    "attack",
    "battle",
    "combat",
    "construct",
    "enemy",
    "fight",
    "guard",
    "monster",
    "patrol",
    "sentry",
    "threat",
    "trap",
    "遭遇",
    "伏击",
    "守卫",
    "怪物",
    "战斗",
    "巡逻",
    "敌人",
    "陷阱",
}
TACTICAL_ROLES = {"striker", "controller", "defender", "healer", "skirmisher"}
TACTICAL_ROLE_ALIASES = {
    "artillery": "striker",
    "assassin": "striker",
    "brute": "defender",
    "caster": "controller",
    "frontliner": "striker",
    "guardian": "defender",
    "lurker": "skirmisher",
    "soldier": "defender",
    "tank": "defender",
    "治疗": "healer",
    "治疗者": "healer",
    "守卫": "defender",
    "坦克": "defender",
    "控制": "controller",
    "控制者": "controller",
    "游击": "skirmisher",
    "突击": "striker",
}
HEALING_HINTS = {
    "cure wounds",
    "healing word",
    "heal",
    "mass cure",
    "lay on hands",
    "regenerate",
    "治疗",
    "治愈",
    "恢复",
}
CONTROL_HINTS = {
    "banish",
    "charm",
    "command",
    "confusion",
    "entangle",
    "fear",
    "hold",
    "hypnotic",
    "restrain",
    "slow",
    "stun",
    "web",
    "束缚",
    "恐惧",
    "魅惑",
    "定身",
    "减速",
    "震慑",
}


def build_encounter_templates_from_module(
    parsed: dict[str, Any] | None,
    nodes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    parsed = parsed or {}
    monsters = _valid_monsters(parsed)
    if not monsters:
        return []

    scenes = parsed.get("scenes") if isinstance(parsed.get("scenes"), list) else []
    templates: list[dict[str, Any]] = []

    for scene_index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        explicit = _explicit_scene_monsters(scene, monsters)
        matched = explicit or _matched_scene_monsters(scene, monsters)
        if matched:
            selected = matched if explicit else _expand_scene_roster(scene, matched, monsters)
            templates.append(_build_template(
                parsed=parsed,
                scene=scene,
                scene_index=scene_index,
                location_id=_node_id_for_scene(nodes, scene, scene_index),
                monsters=selected,
                template_index=len(templates),
                source="module_scene",
            ))

    if not templates:
        scene_index = _best_combat_scene_index(scenes)
        scene = scenes[scene_index] if scenes and scene_index < len(scenes) else {}
        templates.append(_build_template(
            parsed=parsed,
            scene=scene,
            scene_index=scene_index,
            location_id=_node_id_for_scene(nodes, scene, scene_index),
            monsters=monsters[:3],
            template_index=0,
            source="module_monsters",
        ))

    return templates


def attach_encounter_templates_to_graph(
    graph: dict[str, Any] | None,
    parsed: dict[str, Any] | None,
) -> dict[str, Any]:
    graph = deepcopy(graph or {})
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    existing = graph.get("encounter_templates") if isinstance(graph.get("encounter_templates"), list) else []
    templates = build_encounter_templates_from_module(parsed, nodes)
    templates = _preserve_template_runtime_fields(existing, templates)

    graph["encounter_templates"] = templates
    by_location: dict[str, list[str]] = {}
    for template in templates:
        location_id = str(template.get("location_id") or "")
        if not location_id:
            continue
        by_location.setdefault(location_id, []).append(template["id"])

    for node in nodes:
        node_id = str(node.get("id") or "")
        template_ids = by_location.get(node_id, [])
        if template_ids:
            node["encounter_template_ids"] = template_ids
        elif "encounter_template_ids" in node:
            node["encounter_template_ids"] = []

    return graph


def select_current_encounter_template(
    game_state: dict[str, Any] | None,
    parsed: dict[str, Any] | None = None,
    party: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    state = game_state or {}
    graph = state.get("location_graph") if isinstance(state.get("location_graph"), dict) else {}
    if parsed and not graph.get("encounter_templates"):
        graph = attach_encounter_templates_to_graph(graph, parsed)

    templates = graph.get("encounter_templates") if isinstance(graph.get("encounter_templates"), list) else []
    current_id = str(graph.get("current_location_id") or "")
    if not current_id:
        return None

    selected_id = str(graph.get("selected_encounter_template_id") or "")
    if selected_id:
        for template in templates:
            if (
                str(template.get("id")) == selected_id
                and str(template.get("location_id")) == current_id
                and template.get("status", "available") == "available"
            ):
                return attach_party_balance_to_template(template, party, parsed)

    for template in templates:
        if (
            str(template.get("location_id")) == current_id
            and template.get("status", "available") == "available"
        ):
            return attach_party_balance_to_template(template, party, parsed)
    return None


def attach_party_balance_to_template(
    template: dict[str, Any],
    party: list[dict[str, Any]] | None,
    parsed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    template = deepcopy(template)
    if not party:
        return template

    estimate = estimate_encounter_difficulty(
        party,
        _template_monsters_for_balance(template, parsed or {}),
    )
    environment_pressure = _environment_pressure(template)
    target = _target_difficulty(template)
    recommendation = _balance_recommendation(estimate.get("difficulty"), target)
    roster_tuning = _tune_initial_enemy_roster(template, party, parsed or {}, target)
    template["party_balance"] = {
        "target_difficulty": target,
        "estimated_difficulty": estimate.get("difficulty"),
        "action_adjusted_difficulty": estimate.get("difficulty_with_action_economy"),
        "environment_adjusted_difficulty": _environment_adjusted_difficulty(
            estimate.get("difficulty_with_action_economy"),
            environment_pressure,
        ),
        "environment_pressure": environment_pressure,
        "recommended_adjustment": recommendation,
        "estimate": estimate,
    }
    if roster_tuning:
        template["balanced_initial_enemies"] = roster_tuning["active_initial_enemies"]
        template["staged_initial_enemies"] = roster_tuning["staged_initial_enemies"]
        template["party_balance"]["roster_tuning"] = {
            "strategy": roster_tuning["strategy"],
            "active_count": len(roster_tuning["active_initial_enemies"]),
            "staged_count": len(roster_tuning["staged_initial_enemies"]),
            "added_count": len(roster_tuning.get("added_initial_enemies") or []),
            "estimated_difficulty_after_tuning": roster_tuning["estimate"].get("difficulty"),
            "estimate_after_tuning": roster_tuning["estimate"],
        }
    return template


def template_environment_pressure(template: dict[str, Any] | None) -> dict[str, Any]:
    """Return a public-safe aggregate of encounter environmental pressure."""
    return _environment_pressure(template or {})


def select_encounter_template(
    game_state: dict[str, Any] | None,
    template_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    state = deepcopy(game_state or {})
    graph = state.get("location_graph")
    if not isinstance(graph, dict):
        raise ValueError("location graph is not available")
    templates = graph.get("encounter_templates")
    if not isinstance(templates, list):
        raise ValueError("encounter templates are not available")

    current_id = str(graph.get("current_location_id") or "")
    selected_template = None
    for template in templates:
        if str(template.get("id")) == str(template_id):
            selected_template = template
            break
    if not selected_template:
        raise ValueError("encounter template not found")
    if selected_template.get("status", "available") != "available":
        raise ValueError("encounter template is not available")
    if current_id and str(selected_template.get("location_id")) != current_id:
        raise ValueError("encounter template is not at the current location")

    graph["selected_encounter_template_id"] = str(selected_template.get("id"))
    for template in templates:
        template["selected"] = str(template.get("id")) == str(selected_template.get("id"))
    state["location_graph"] = graph
    return state, deepcopy(selected_template)


def mark_encounter_template_triggered(
    game_state: dict[str, Any] | None,
    template_id: str | None,
) -> dict[str, Any]:
    state = deepcopy(game_state or {})
    if not template_id:
        return state
    graph = state.get("location_graph")
    if not isinstance(graph, dict):
        return state
    templates = graph.get("encounter_templates")
    if not isinstance(templates, list):
        return state

    for template in templates:
        if str(template.get("id")) == str(template_id):
            template["status"] = "triggered"
            template["selected"] = False
    if str(graph.get("selected_encounter_template_id") or "") == str(template_id):
        graph.pop("selected_encounter_template_id", None)
    state["location_graph"] = graph
    return state


def _template_monsters_for_balance(
    template: dict[str, Any],
    parsed: dict[str, Any],
) -> list[dict[str, Any]]:
    parsed_monsters = {
        str(monster.get("name")): monster
        for monster in _valid_monsters(parsed)
    }
    monsters = []
    for item in template.get("initial_enemies") or []:
        item = {"name": item} if isinstance(item, str) else item
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        monsters.append(parsed_monsters.get(name, item))

    if monsters:
        return monsters

    xp_budget = template.get("xp_budget")
    try:
        xp = int(xp_budget)
    except (TypeError, ValueError):
        xp = 0
    return [{"xp": xp}] if xp > 0 else []


def _tune_initial_enemy_roster(
    template: dict[str, Any],
    party: list[dict[str, Any]],
    parsed: dict[str, Any],
    target: str,
) -> dict[str, Any] | None:
    initial_items = list(template.get("initial_enemies") or [])
    if not initial_items:
        return None

    staged = _stage_extra_enemies_for_overbudget(initial_items, party, parsed, target)
    if staged:
        return staged
    return _add_minions_for_underbudget(initial_items, party, parsed, target)


def _stage_extra_enemies_for_overbudget(
    initial_items: list[Any],
    party: list[dict[str, Any]],
    parsed: dict[str, Any],
    target: str,
) -> dict[str, Any] | None:
    if len(initial_items) <= 1:
        return None

    target_rank = DIFFICULTY_RANK.get(target, DIFFICULTY_RANK["medium"])
    max_rank = min(DIFFICULTY_RANK["deadly"] - 1, target_rank + 1)
    active: list[Any] = []
    staged: list[Any] = []

    for item in initial_items:
        candidate = [*active, item]
        estimate = estimate_encounter_difficulty(
            party,
            _template_monsters_for_items(candidate, parsed),
        )
        candidate_rank = DIFFICULTY_RANK.get(str(estimate.get("difficulty") or "none"), 0)
        if not active or candidate_rank <= max_rank:
            active.append(item)
        else:
            staged.append(item)

    if not staged:
        return None

    tuned_estimate = estimate_encounter_difficulty(
        party,
        _template_monsters_for_items(active, parsed),
    )
    return {
        "strategy": "stage_extra_enemies",
        "active_initial_enemies": active,
        "staged_initial_enemies": staged,
        "estimate": tuned_estimate,
    }


def _add_minions_for_underbudget(
    initial_items: list[Any],
    party: list[dict[str, Any]],
    parsed: dict[str, Any],
    target: str,
) -> dict[str, Any] | None:
    target_rank = DIFFICULTY_RANK.get(target, DIFFICULTY_RANK["medium"])
    max_rank = min(DIFFICULTY_RANK["deadly"] - 1, target_rank + 1)
    active: list[Any] = list(initial_items)
    estimate = estimate_encounter_difficulty(
        party,
        _template_monsters_for_items(active, parsed),
    )
    current_rank = DIFFICULTY_RANK.get(str(estimate.get("difficulty") or "none"), 0)
    if current_rank <= 0 or current_rank >= target_rank:
        return None

    added: list[Any] = []
    for candidate in _underbudget_minion_candidates(initial_items, parsed):
        trial = [*active, candidate]
        trial_estimate = estimate_encounter_difficulty(
            party,
            _template_monsters_for_items(trial, parsed),
        )
        trial_rank = DIFFICULTY_RANK.get(str(trial_estimate.get("difficulty") or "none"), 0)
        if trial_rank < current_rank or trial_rank > max_rank:
            continue
        if trial_estimate.get("adjusted_xp", 0) <= estimate.get("adjusted_xp", 0):
            continue
        active.append(candidate)
        added.append(candidate)
        estimate = trial_estimate
        current_rank = trial_rank
        if current_rank >= target_rank:
            break

    if not added:
        return None
    return {
        "strategy": "add_minions",
        "active_initial_enemies": active,
        "staged_initial_enemies": [],
        "added_initial_enemies": added,
        "estimate": estimate,
    }


def _underbudget_minion_candidates(
    initial_items: list[Any],
    parsed: dict[str, Any],
) -> list[Any]:
    initial_monsters = _template_monsters_for_items(initial_items, parsed)
    initial_xps = [monster_xp(monster) for monster in initial_monsters if monster_xp(monster) > 0]
    if not initial_xps:
        return []

    max_candidate_xp = max(initial_xps)
    initial_names = {
        _normalize((item if isinstance(item, str) else item.get("name")))
        for item in initial_items
        if (item if isinstance(item, str) else item.get("name"))
    }
    candidates: list[Any] = []
    for monster in _valid_monsters(parsed):
        name = str(monster.get("name") or "")
        if not name or _normalize(name) in initial_names:
            continue
        if monster_xp(monster) <= max_candidate_xp:
            candidates.append({"name": name})

    cheapest_index = min(
        range(len(initial_monsters)),
        key=lambda index: monster_xp(initial_monsters[index]),
    )
    cheapest_item = deepcopy(initial_items[cheapest_index])
    while len(candidates) < 6:
        candidates.append(deepcopy(cheapest_item))
    return candidates


def _template_monsters_for_items(
    items: list[Any],
    parsed: dict[str, Any],
) -> list[dict[str, Any]]:
    return _template_monsters_for_balance({"initial_enemies": items}, parsed)


def _target_difficulty(template: dict[str, Any]) -> str:
    explicit = str(template.get("target_difficulty") or "").strip().lower()
    if explicit in DIFFICULTY_RANK:
        return explicit
    hint = str(template.get("difficulty_hint") or "").strip().lower()
    if hint == "light":
        return "easy"
    if hint == "dangerous":
        return "hard"
    return "medium"


def _scene_target_difficulty(scene: dict[str, Any]) -> str:
    value = str(
        scene.get("target_difficulty")
        or scene.get("difficulty")
        or scene.get("difficulty_target")
        or ""
    ).strip().lower()
    aliases = {
        "light": "easy",
        "moderate": "medium",
        "dangerous": "hard",
    }
    value = aliases.get(value, value)
    return value if value in DIFFICULTY_RANK and value != "none" else ""


def _balance_recommendation(estimated: Any, target: str) -> str:
    estimated_rank = DIFFICULTY_RANK.get(str(estimated or "none"), 0)
    target_rank = DIFFICULTY_RANK.get(target, DIFFICULTY_RANK["medium"])
    if estimated_rank == 0:
        return "needs_monster_xp"
    if estimated_rank >= DIFFICULTY_RANK["deadly"] and target_rank < DIFFICULTY_RANK["deadly"]:
        return "reduce_or_stage_enemies"
    if estimated_rank > target_rank + 1:
        return "reduce_enemy_count_or_xp"
    if estimated_rank < target_rank - 1:
        return "add_minion_or_objective_pressure"
    return "ok"


def _environment_pressure(template: dict[str, Any]) -> dict[str, Any]:
    hazards = _feature_values(template.get("hazards"))
    objectives = _feature_values(template.get("objectives"))
    cover = _feature_values(template.get("cover"))
    terrain = [
        item for item in _feature_values(template.get("terrain"))
        if _normalize(_feature_name(item)) not in {"open ground", "open"}
    ]
    authored_cells = sum(_feature_cell_count(item) for item in [*hazards, *objectives, *cover, *terrain])
    damaging_hazards = sum(1 for item in hazards if _is_damaging_hazard(item))

    score = (
        len(hazards) * 2
        + damaging_hazards
        + len(objectives)
        + min(len(cover) + len(terrain), 3)
        + min(authored_cells // 3, 2)
    )
    if score <= 0:
        pressure = "none"
    elif score <= 2:
        pressure = "light"
    elif score <= 5:
        pressure = "moderate"
    else:
        pressure = "heavy"

    return {
        "pressure": pressure,
        "score": score,
        "hazards": len(hazards),
        "damaging_hazards": damaging_hazards,
        "objectives": len(objectives),
        "cover": len(cover),
        "terrain": len(terrain),
        "authored_cells": authored_cells,
    }


def _environment_adjusted_difficulty(difficulty: Any, environment_pressure: dict[str, Any]) -> str:
    pressure = str(environment_pressure.get("pressure") or "none")
    shift = 1 if pressure in {"moderate", "heavy"} else 0
    return _shift_difficulty(str(difficulty or "none"), shift)


def _shift_difficulty(difficulty: str, shift: int) -> str:
    try:
        index = DIFFICULTY_ORDER.index(str(difficulty or "none"))
    except ValueError:
        index = 0
    index = max(0, min(len(DIFFICULTY_ORDER) - 1, index + shift))
    return DIFFICULTY_ORDER[index]


def _feature_values(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _feature_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(
            item.get("label")
            or item.get("name")
            or item.get("description")
            or item.get("terrain")
            or item.get("type")
            or item.get("kind")
            or ""
        )
    return str(item or "")


def _feature_cell_count(item: Any) -> int:
    if not isinstance(item, dict):
        return 0
    total = 0
    for key in ("cells", "cell", "positions", "position"):
        value = item.get(key)
        if not value:
            continue
        if isinstance(value, list):
            total += len(value)
        else:
            total += 1
    return total


def _is_damaging_hazard(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    return any(
        item.get(key)
        for key in (
            "damage_dice",
            "damage_type",
            "save_dc",
            "dc",
            "saving_throw_dc",
        )
    )


def _valid_monsters(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    monsters = parsed.get("monsters") if isinstance(parsed.get("monsters"), list) else []
    return [
        monster
        for monster in monsters
        if isinstance(monster, dict) and str(monster.get("name") or "").strip()
    ]


def _build_template(
    *,
    parsed: dict[str, Any],
    scene: dict[str, Any],
    scene_index: int,
    location_id: str,
    monsters: list[dict[str, Any]],
    template_index: int,
    source: str,
) -> dict[str, Any]:
    enemy_names = [str(monster.get("name")) for monster in monsters if monster.get("name")]
    location_name = str(scene.get("title") or scene.get("name") or scene.get("location") or "Encounter")
    xp_total = sum(monster_xp(monster) for monster in monsters)
    target_difficulty = _scene_target_difficulty(scene)
    template = {
        "version": ENCOUNTER_TEMPLATE_VERSION,
        "id": f"encounter_{_slug(location_id)}_{template_index}",
        "name": str(scene.get("encounter_name") or f"{location_name} Encounter"),
        "location_id": location_id,
        "location_name": location_name,
        "status": "available",
        "source": source,
        "difficulty_hint": _difficulty_hint(xp_total, len(monsters)),
        "xp_budget": xp_total,
        "enemy_names": enemy_names,
        "initial_enemies": [{"name": name} for name in enemy_names],
        "enemy_roles": [
            {"name": str(monster.get("name")), "role": infer_enemy_tactical_role(monster)}
            for monster in monsters
        ],
        "terrain": _terrain_features(scene),
        "cover": _cover_features(scene),
        "objectives": _objectives(scene),
        "hazards": _hazards(scene),
        "tactics": _tactics(monsters),
        "reward_hints": _reward_hints(parsed),
        "scene_index": scene_index,
    }
    if target_difficulty:
        template["target_difficulty"] = target_difficulty
    return template


def _node_id_for_scene(nodes: list[dict[str, Any]] | None, scene: dict[str, Any], scene_index: int) -> str:
    if nodes and scene_index < len(nodes):
        node_id = nodes[scene_index].get("id")
        if node_id:
            return str(node_id)
    return str(scene.get("id") or f"scene_{scene_index}")


def _explicit_scene_monsters(scene: dict[str, Any], monsters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    explicit_names: list[str] = []
    for key in ("monsters", "enemy_names", "enemies", "initial_enemies"):
        values = scene.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict):
                name = value.get("name")
            else:
                name = value
            if name:
                explicit_names.append(str(name))
    if not explicit_names:
        return []

    by_name = {_normalize(monster.get("name")): monster for monster in monsters}
    matched = [
        by_name[_normalize(name)]
        for name in explicit_names
        if _normalize(name) in by_name
    ]
    return _dedupe_monsters(matched)


def _matched_scene_monsters(scene: dict[str, Any], monsters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text = _scene_text(scene)
    if not text:
        return []
    matched = [
        monster
        for monster in monsters
        if _monster_matches_text(monster, text)
    ]
    if matched:
        return _dedupe_monsters(matched)
    if _has_combat_hint(text):
        return monsters[:1]
    return []


def _expand_scene_roster(
    scene: dict[str, Any],
    matched: list[dict[str, Any]],
    monsters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if _has_combat_hint(_scene_text(scene)):
        return _dedupe_monsters([*matched, *monsters[:3]])
    return matched


def _best_combat_scene_index(scenes: list[Any]) -> int:
    if not scenes:
        return 0
    scored: list[tuple[int, int]] = []
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        text = _scene_text(scene)
        score = sum(1 for hint in COMBAT_HINTS if hint in text)
        scored.append((score, index))
    if not scored:
        return max(0, len(scenes) - 1)
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if scored[0][0] > 0:
        return scored[0][1]
    return max(0, len(scenes) - 1)


def _preserve_template_runtime_fields(
    existing: list[dict[str, Any]],
    templates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing_by_id = {
        str(template.get("id")): template
        for template in existing
        if isinstance(template, dict) and template.get("id")
    }
    for template in templates:
        previous = existing_by_id.get(str(template.get("id")))
        if not previous:
            continue
        for key in ("status", "triggered_at", "resolved_at", "selected"):
            if key in previous:
                template[key] = previous[key]
    return templates


def _monster_matches_text(monster: dict[str, Any], text: str) -> bool:
    tokens = [
        token
        for token in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", str(monster.get("name") or "").lower())
        if len(token) >= 4 or re.search(r"[\u4e00-\u9fff]", token)
    ]
    return any(token and token in text for token in tokens)


def _scene_text(scene: dict[str, Any]) -> str:
    parts = [
        scene.get("id"),
        scene.get("title"),
        scene.get("name"),
        scene.get("location"),
        scene.get("description"),
        scene.get("summary"),
    ]
    choices = scene.get("choices")
    if isinstance(choices, list):
        parts.extend(choice.get("text") for choice in choices if isinstance(choice, dict))
    return " ".join(str(part or "") for part in parts).lower()


def _has_combat_hint(text: str) -> bool:
    return any(hint in text for hint in COMBAT_HINTS)


def _terrain_features(scene: dict[str, Any]) -> list[Any]:
    explicit = _feature_list(scene.get("terrain"), default_name="Terrain feature")
    if explicit:
        return explicit
    text = _scene_text(scene)
    features = []
    if "difficult terrain" in text or "sparking" in text:
        features.append("difficult terrain")
    if "wall" in text or "cover" in text:
        features.append("low cover")
    return features or ["open ground"]


def _cover_features(scene: dict[str, Any]) -> list[Any]:
    explicit = _feature_list(scene.get("cover"), default_name="Cover")
    if explicit:
        return explicit
    text = _scene_text(scene)
    if "wall" in text:
        return ["low walls"]
    if "barricade" in text or "crate" in text:
        return ["scattered cover"]
    return []


def _objectives(scene: dict[str, Any]) -> list[Any]:
    explicit = _feature_list(scene.get("objectives") or scene.get("goals"), default_name="Objective")
    if explicit:
        return explicit
    return ["Secure the area and survive the threat"]


def _hazards(scene: dict[str, Any]) -> list[Any]:
    explicit = _hazard_list(scene.get("hazards"))
    text = _scene_text(scene)
    inferred: list[Any] = []
    if "trap" in text or "tripwire" in text or "陷阱" in text:
        inferred.append("triggered trap")
    if "sparking" in text or "lightning" in text:
        inferred.append("unstable energy")
    return _dedupe_hazards([*explicit, *inferred])


def _reward_hints(parsed: dict[str, Any]) -> list[str]:
    rewards = _as_list(parsed.get("key_rewards"))
    if rewards:
        return rewards[:4]
    items = parsed.get("magic_items") if isinstance(parsed.get("magic_items"), list) else []
    return [
        str(item.get("name"))
        for item in items
        if isinstance(item, dict) and item.get("name")
    ][:4]


def _tactics(monsters: list[dict[str, Any]]) -> str:
    tactics = [
        str(monster.get("tactics")).strip()
        for monster in monsters
        if monster.get("tactics")
    ]
    if tactics:
        return " ".join(tactics[:2])
    return "Use the terrain and focus isolated targets."


def normalize_tactical_role(value: Any, fallback: str = "striker") -> str:
    raw = _normalize(value)
    if raw in TACTICAL_ROLES:
        return raw
    if raw in TACTICAL_ROLE_ALIASES:
        return TACTICAL_ROLE_ALIASES[raw]
    return fallback


def infer_enemy_tactical_role(monster: dict[str, Any] | None) -> str:
    monster = monster or {}
    explicit = (
        monster.get("tactical_role")
        or monster.get("combat_role")
        or monster.get("battlefield_role")
        or monster.get("role")
    )
    if explicit:
        normalized = normalize_tactical_role(explicit, fallback="")
        if normalized:
            return normalized

    spells_text = " ".join(
        str(spell)
        for spell in [
            *_as_list(monster.get("known_spells")),
            *_as_list(monster.get("prepared_spells")),
            *_as_list(monster.get("cantrips")),
        ]
    ).lower()
    actions_text = " ".join(
        " ".join(str(value) for value in action.values() if value not in (None, ""))
        for action in (monster.get("actions") or [])
        if isinstance(action, dict)
    ).lower()
    abilities_text = " ".join(
        " ".join(str(value) for value in ability.values() if value not in (None, ""))
        if isinstance(ability, dict) else str(ability)
        for ability in [
            *list(monster.get("special_abilities") or []),
            *list(monster.get("recharge_abilities") or []),
        ]
    ).lower()
    combined = " ".join([spells_text, actions_text, abilities_text])

    if any(hint in combined for hint in HEALING_HINTS):
        return "healer"
    if any(hint in combined for hint in CONTROL_HINTS) or _inflicts_control_condition(monster):
        return "controller"

    speed = _to_int(monster.get("speed"), 30)
    ac = _to_int(monster.get("ac"), 10)
    hp = _to_int(monster.get("hp"), 1)
    multiattack = _to_int(monster.get("multiattack") or monster.get("attacks_max"), 1)
    scores = monster.get("ability_scores") if isinstance(monster.get("ability_scores"), dict) else {}
    dex = _to_int(scores.get("dex"), 10)
    con = _to_int(scores.get("con"), 10)

    if speed >= 40:
        return "skirmisher"
    if ac >= 16 or hp >= 35 or con >= 16:
        return "defender"
    if multiattack >= 2 or dex >= 16 or _has_high_damage_action(monster):
        return "striker"
    return "striker"


def _inflicts_control_condition(monster: dict[str, Any]) -> bool:
    control_conditions = {
        "charmed",
        "frightened",
        "grappled",
        "paralyzed",
        "poisoned",
        "prone",
        "restrained",
        "stunned",
        "unconscious",
    }
    for action in (monster.get("actions") or []):
        if not isinstance(action, dict):
            continue
        effects = action.get("conditions") or action.get("condition") or action.get("inflicts")
        values = effects if isinstance(effects, list) else [effects]
        if any(_normalize(value) in control_conditions for value in values if value):
            return True
    return False


def _has_high_damage_action(monster: dict[str, Any]) -> bool:
    for action in monster.get("actions") or []:
        if not isinstance(action, dict):
            continue
        damage = str(action.get("damage_dice") or action.get("damage") or "")
        if re.search(r"\b[2-9]d(6|8|10|12)\b", damage.lower()):
            return True
    return False


def _difficulty_hint(xp_total: int, monster_count: int) -> str:
    if xp_total <= 0:
        return "unknown"
    if xp_total < 150 and monster_count <= 2:
        return "light"
    if xp_total < 500:
        return "moderate"
    return "dangerous"


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _feature_list(value: Any, *, default_name: str) -> list[Any]:
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    features: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            feature = _placed_feature_dict(item, default_name=default_name)
            if feature:
                features.append(feature)
            continue
        text = str(item).strip()
        if text:
            features.append(text)
    return _dedupe_hazards(features)


def _placed_feature_dict(item: dict[str, Any], *, default_name: str) -> dict[str, Any]:
    allowed = {
        "label",
        "name",
        "description",
        "terrain",
        "type",
        "kind",
        "category",
        "cover",
        "cover_level",
        "cover_bonus",
        "blocks_movement",
        "blocks_sight",
        "objective",
        "cells",
        "cell",
        "positions",
        "position",
    }
    feature = {
        key: value
        for key, value in item.items()
        if key in allowed and value not in (None, "")
    }
    if not feature:
        return {}
    if not any(feature.get(key) for key in ("label", "name", "description")):
        feature["name"] = default_name
    return feature


def _hazard_list(value: Any) -> list[Any]:
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    hazards: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            hazard = _hazard_dict(item)
            if hazard:
                hazards.append(hazard)
            continue
        text = str(item).strip()
        if text:
            hazards.append(text)
    return hazards


def _hazard_dict(item: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "label",
        "name",
        "description",
        "damage_dice",
        "damage_type",
        "save_dc",
        "dc",
        "saving_throw_dc",
        "save_ability",
        "saving_throw",
        "saving_throw_ability",
        "save",
        "half_on_save",
        "save_half",
        "half_damage_on_save",
        "no_damage_on_save",
        "negates_on_save",
        "cells",
        "cell",
        "positions",
        "position",
    }
    hazard = {
        key: value
        for key, value in item.items()
        if key in allowed and value not in (None, "")
    }
    if not hazard:
        return {}
    if not any(hazard.get(key) for key in ("label", "name", "description")):
        hazard["name"] = "Environmental hazard"
    return hazard


def _dedupe_monsters(monsters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for monster in monsters:
        name = _normalize(monster.get("name"))
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(monster)
    return out


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _dedupe_hazards(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for value in values:
        if isinstance(value, dict):
            key = _normalize(
                value.get("label")
                or value.get("name")
                or value.get("description")
                or value
            )
        else:
            key = _normalize(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _slug(value: Any) -> str:
    text = re.sub(r"[^0-9a-zA-Z]+", "_", str(value or "").lower()).strip("_")
    return text or "location"


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
