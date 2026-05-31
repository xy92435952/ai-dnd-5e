"""Location graph helpers for exploration sessions.

The first slice intentionally keeps the graph lightweight and stored inside
``Session.game_state`` so it can evolve without a migration. Module scenes form
the initial route, and runtime scene-vibe updates can move the current location
or add discovered places.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from services.encounter_template_service import attach_encounter_templates_to_graph


LOCATION_GRAPH_VERSION = 1
EXIT_ACTION_RE = re.compile(
    r"(go to|head to|enter|leave|travel|move|cross|follow|approach|return|"
    r"open|force|unlock|climb|前往|进入|离开|穿过|走向|返回|通过|推开|打开|"
    r"撬开|强行|翻越|沿着)",
    re.IGNORECASE,
)


def normalize_location_id(value: str | None, *, fallback: str = "location") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", text).strip("_")
    return text or fallback


def build_location_graph_from_module(parsed: dict[str, Any] | None) -> dict[str, Any]:
    parsed = parsed or {}
    scenes = parsed.get("scenes") if isinstance(parsed.get("scenes"), list) else []
    nodes: list[dict[str, Any]] = []

    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        name = (
            scene.get("title")
            or scene.get("name")
            or scene.get("location")
            or f"Scene {index + 1}"
        )
        node_id = str(scene.get("id") or f"scene_{index}")
        nodes.append({
            "id": node_id,
            "name": str(name),
            "description": str(scene.get("description") or "")[:500],
            "order": len(nodes),
            "source": "module_scene",
            "visited": len(nodes) == 0,
        })

    if not nodes:
        setting = parsed.get("setting") or "Starting Area"
        nodes.append({
            "id": "scene_0",
            "name": str(setting),
            "description": str(parsed.get("plot_summary") or "")[:500],
            "order": 0,
            "source": "module_setting",
            "visited": True,
        })

    edges = [
        {"from": nodes[index]["id"], "to": nodes[index + 1]["id"], "type": "sequence"}
        for index in range(len(nodes) - 1)
    ]
    graph = {
        "version": LOCATION_GRAPH_VERSION,
        "current_location_id": nodes[0]["id"],
        "nodes": nodes,
        "edges": edges,
    }
    return attach_encounter_templates_to_graph(graph, parsed)


def ensure_location_graph_state(
    game_state: dict[str, Any] | None,
    parsed: dict[str, Any] | None,
) -> dict[str, Any]:
    state = deepcopy(game_state or {})
    graph = state.get("location_graph")
    if not _is_valid_graph(graph):
        state["location_graph"] = build_location_graph_from_module(parsed)
    else:
        state["location_graph"] = attach_encounter_templates_to_graph(graph, parsed)
    return state


def apply_location_update(
    game_state: dict[str, Any] | None,
    parsed: dict[str, Any] | None,
    *,
    location_name: str | None = None,
    location_id: str | None = None,
) -> dict[str, Any]:
    state = ensure_location_graph_state(game_state, parsed)
    if not location_name and not location_id:
        return state

    graph = deepcopy(state["location_graph"])
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    previous_id = graph.get("current_location_id")

    target_id = location_id or _find_node_id_by_name(nodes, location_name)
    if not target_id:
        target_id = normalize_location_id(location_name, fallback=f"location_{len(nodes)}")

    node = next((item for item in nodes if item.get("id") == target_id), None)
    if node is None:
        node = {
            "id": target_id,
            "name": str(location_name or target_id),
            "description": "",
            "order": len(nodes),
            "source": "runtime_discovery",
            "visited": True,
        }
        nodes.append(node)
    else:
        node["visited"] = True
        if location_name and not node.get("name"):
            node["name"] = str(location_name)

    if previous_id and previous_id != target_id and not _has_edge(edges, previous_id, target_id):
        edges.append({"from": previous_id, "to": target_id, "type": "discovered"})

    graph["current_location_id"] = target_id
    graph["nodes"] = nodes
    graph["edges"] = edges
    state["location_graph"] = graph
    return state


def build_location_graph_context(game_state: dict[str, Any] | None) -> dict[str, Any]:
    graph = (game_state or {}).get("location_graph")
    if not _is_valid_graph(graph):
        return {}

    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    templates = [
        item for item in list(graph.get("encounter_templates") or [])
        if isinstance(item, dict) and item.get("status") != "resolved"
    ]
    current_id = str(
        graph.get("current_location_id")
        or next((node.get("id") for node in nodes if node.get("visited")), nodes[0].get("id"))
    )
    current = next((node for node in nodes if str(node.get("id")) == current_id), nodes[0])
    node_by_id = {str(node.get("id")): node for node in nodes}

    exits = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if source == current_id:
            next_id = target
            one_way = bool(edge.get("one_way") or edge.get("oneWay"))
        elif target == current_id and not (edge.get("one_way") or edge.get("oneWay")):
            next_id = source
            one_way = False
        else:
            continue
        node = node_by_id.get(next_id)
        if not node:
            continue
        exits.append({
            "location_id": next_id,
            "name": str(node.get("name") or next_id),
            "description": str(node.get("description") or "")[:180],
            "route_type": str(edge.get("type") or "route"),
            "locked": bool(edge.get("locked") or edge.get("requires_key") or edge.get("status") == "locked" or edge.get("type") == "locked"),
            "hidden": bool(edge.get("hidden") or edge.get("secret") or edge.get("status") == "hidden" or edge.get("type") == "hidden"),
            "one_way": one_way,
        })

    current_template_ids = {
        str(item) for item in current.get("encounter_template_ids") or []
    }
    encounters = []
    for template in templates:
        if str(template.get("location_id")) != current_id and str(template.get("id")) not in current_template_ids:
            continue
        encounters.append({
            "id": str(template.get("id") or ""),
            "name": str(template.get("name") or "Encounter"),
            "status": str(template.get("status") or "available"),
            "difficulty_hint": str(template.get("difficulty_hint") or ""),
            "enemy_names": list(template.get("enemy_names") or [])[:6],
        })

    return {
        "current": {
            "location_id": current_id,
            "name": str(current.get("name") or current_id),
            "description": str(current.get("description") or "")[:240],
            "visited": bool(current.get("visited")),
        },
        "exits": exits[:8],
        "current_encounters": encounters[:4],
        "visited_count": len([node for node in nodes if node.get("visited")]) or 1,
        "total_count": len(nodes),
    }


def tag_player_choices_with_location_exits(
    player_choices: Any,
    game_state: dict[str, Any] | None,
) -> list[Any]:
    if not isinstance(player_choices, list):
        return []

    context = build_location_graph_context(game_state)
    exits = [
        item for item in list(context.get("exits") or [])
        if isinstance(item, dict) and not item.get("hidden")
    ]
    if not exits:
        return list(player_choices)

    tagged_choices = []
    for choice in player_choices:
        text = _choice_text(choice)
        if not _choice_can_be_location_exit(choice, text):
            tagged_choices.append(choice)
            continue
        exit_data = _match_choice_to_exit(text, exits)
        if not exit_data:
            tagged_choices.append(choice)
            continue
        tagged_choices.append(_tag_choice_with_exit(choice, text, exit_data))
    return tagged_choices


def public_location_graph(graph: dict[str, Any] | None) -> dict[str, Any]:
    if not _is_valid_graph(graph):
        return {}

    raw_nodes = [
        node for node in list(graph.get("nodes") or [])
        if isinstance(node, dict)
    ]
    if not raw_nodes:
        return {}

    current_id = str(
        graph.get("current_location_id")
        or next((node.get("id") for node in raw_nodes if node.get("visited")), raw_nodes[0].get("id"))
    )
    visible_nodes = []
    for index, node in enumerate(raw_nodes):
        node_id = str(node.get("id") or f"location_{index}")
        if not _is_public_node(node, node_id, current_id):
            continue
        visible_nodes.append({
            "id": node_id,
            "name": str(node.get("name") or f"Location {len(visible_nodes) + 1}"),
            "description": str(node.get("description") or "")[:500],
            "order": node.get("order", index),
            "source": str(node.get("source") or ""),
            "visited": bool(node.get("visited") or node_id == current_id),
        })

    if not visible_nodes:
        node = next(
            (item for item in raw_nodes if str(item.get("id") or "") == current_id),
            raw_nodes[0],
        )
        visible_nodes.append({
            "id": str(node.get("id") or current_id or "location_0"),
            "name": str(node.get("name") or "Current Location"),
            "description": str(node.get("description") or "")[:500],
            "order": node.get("order", 0),
            "source": str(node.get("source") or ""),
            "visited": True,
        })

    visible_ids = {str(node["id"]) for node in visible_nodes}
    public_edges = []
    for index, edge in enumerate(list(graph.get("edges") or [])):
        if not isinstance(edge, dict) or _is_hidden_edge(edge):
            continue
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if source not in visible_ids or target not in visible_ids:
            continue
        public_edges.append({
            key: edge[key]
            for key in ("id", "from", "to", "type", "label", "name", "locked", "requires_key", "status", "one_way", "oneWay")
            if key in edge
        })
        public_edges[-1].setdefault("id", f"edge_{index}")
        public_edges[-1].setdefault("from", source)
        public_edges[-1].setdefault("to", target)
        public_edges[-1].setdefault("type", "route")

    public_current_id = current_id if current_id in visible_ids else visible_nodes[0]["id"]
    return {
        "version": graph.get("version", LOCATION_GRAPH_VERSION),
        "current_location_id": public_current_id,
        "nodes": visible_nodes,
        "edges": public_edges,
    }


def _is_valid_graph(graph: Any) -> bool:
    return (
        isinstance(graph, dict)
        and isinstance(graph.get("nodes"), list)
        and len(graph.get("nodes") or []) > 0
    )


def _find_node_id_by_name(nodes: list[dict[str, Any]], location_name: str | None) -> str | None:
    if not location_name:
        return None
    normalized = normalize_location_id(location_name)
    for node in nodes:
        if normalize_location_id(node.get("name")) == normalized:
            return str(node.get("id"))
    return None


def _has_edge(edges: list[dict[str, Any]], source: str, target: str) -> bool:
    return any(
        edge.get("from") == source and edge.get("to") == target
        for edge in edges
    )


def _choice_text(choice: Any) -> str:
    if isinstance(choice, str):
        return choice.strip()
    if isinstance(choice, dict):
        return str(choice.get("text") or "").strip()
    return ""


def _choice_can_be_location_exit(choice: Any, text: str) -> bool:
    if isinstance(choice, dict) and isinstance(choice.get("location_exit"), dict):
        return True
    if isinstance(choice, dict):
        explicit = str(
            choice.get("choice_type")
            or choice.get("action_type")
            or choice.get("type")
            or choice.get("intent")
            or ""
        ).strip().lower()
        if explicit in {"movement", "move", "travel", "navigation", "route"}:
            return True
    return bool(EXIT_ACTION_RE.search(text or ""))


def _match_choice_to_exit(
    choice_text: str,
    exits: list[dict[str, Any]],
) -> dict[str, Any] | None:
    normalized_text = _normalize_choice_match(choice_text)
    if not normalized_text:
        return None

    best_exit = None
    best_score = 0
    for exit_data in exits:
        target_name = _normalize_choice_match(exit_data.get("name"))
        target_id = _normalize_choice_match(exit_data.get("location_id"))
        score = 0
        if _usable_exit_match_token(target_name) and target_name in normalized_text:
            score = 100 + len(target_name)
        elif _usable_exit_match_token(target_id) and target_id in normalized_text:
            score = 20 + len(target_id)
        if score > best_score:
            best_exit = exit_data
            best_score = score
    return best_exit


def _tag_choice_with_exit(
    choice: Any,
    text: str,
    exit_data: dict[str, Any],
) -> dict[str, Any]:
    tagged = dict(choice) if isinstance(choice, dict) else {"text": text}
    tagged["text"] = str(tagged.get("text") or text)
    if not any(tagged.get(key) for key in ("choice_type", "action_type", "type", "intent")):
        tagged["choice_type"] = "movement"
    tagged["location_exit"] = {
        "target_location_id": str(exit_data.get("location_id") or ""),
        "target_location_name": str(exit_data.get("name") or ""),
        "route_type": str(exit_data.get("route_type") or "route"),
        "locked": bool(exit_data.get("locked")),
        "hidden": bool(exit_data.get("hidden")),
        "one_way": bool(exit_data.get("one_way")),
    }
    tagged["tags"] = _append_location_exit_tag(tagged.get("tags"))
    return tagged


def _append_location_exit_tag(tags: Any) -> list[Any]:
    normalized = list(tags) if isinstance(tags, list) else []
    if any(
        isinstance(tag, dict) and str(tag.get("kind") or "") == "location_exit"
        for tag in normalized
    ):
        return normalized
    return [*normalized, {"label": "Exit", "kind": "location_exit"}]


def _normalize_choice_match(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", str(value or "").lower())


def _usable_exit_match_token(value: str) -> bool:
    return len(value) >= 2


def _is_public_node(node: dict[str, Any], node_id: str, current_id: str) -> bool:
    return bool(
        node.get("visited")
        or node.get("discovered")
        or node.get("revealed")
        or node.get("public")
        or str(node_id) == str(current_id)
    )


def _is_hidden_edge(edge: dict[str, Any]) -> bool:
    return bool(
        edge.get("hidden")
        or edge.get("secret")
        or edge.get("status") == "hidden"
        or edge.get("type") == "hidden"
    )
