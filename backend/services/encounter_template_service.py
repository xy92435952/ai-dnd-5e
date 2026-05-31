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
    target = _target_difficulty(template)
    recommendation = _balance_recommendation(estimate.get("difficulty"), target)
    template["party_balance"] = {
        "target_difficulty": target,
        "estimated_difficulty": estimate.get("difficulty"),
        "recommended_adjustment": recommendation,
        "estimate": estimate,
    }
    return template


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
    return {
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
            {"name": str(monster.get("name")), "role": _enemy_role(monster)}
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


def _terrain_features(scene: dict[str, Any]) -> list[str]:
    explicit = _as_list(scene.get("terrain"))
    if explicit:
        return explicit
    text = _scene_text(scene)
    features = []
    if "difficult terrain" in text or "sparking" in text:
        features.append("difficult terrain")
    if "wall" in text or "cover" in text:
        features.append("low cover")
    return features or ["open ground"]


def _cover_features(scene: dict[str, Any]) -> list[str]:
    explicit = _as_list(scene.get("cover"))
    if explicit:
        return explicit
    text = _scene_text(scene)
    if "wall" in text:
        return ["low walls"]
    if "barricade" in text or "crate" in text:
        return ["scattered cover"]
    return []


def _objectives(scene: dict[str, Any]) -> list[str]:
    explicit = _as_list(scene.get("objectives") or scene.get("goals"))
    if explicit:
        return explicit
    return ["Secure the area and survive the threat"]


def _hazards(scene: dict[str, Any]) -> list[str]:
    explicit = _as_list(scene.get("hazards"))
    text = _scene_text(scene)
    inferred = []
    if "trap" in text or "tripwire" in text or "陷阱" in text:
        inferred.append("triggered trap")
    if "sparking" in text or "lightning" in text:
        inferred.append("unstable energy")
    return _dedupe_strings([*explicit, *inferred])


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


def _enemy_role(monster: dict[str, Any]) -> str:
    speed = _to_int(monster.get("speed"), 30)
    ac = _to_int(monster.get("ac"), 10)
    hp = _to_int(monster.get("hp"), 1)
    if monster.get("spell_slots") or monster.get("known_spells") or monster.get("prepared_spells"):
        return "caster"
    if speed >= 40:
        return "skirmisher"
    if ac >= 16 or hp >= 35:
        return "brute"
    return "frontliner"


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
