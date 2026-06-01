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

from services.encounter_template_service import attach_encounter_templates_to_graph, template_environment_pressure


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

    edges = _build_location_edges(parsed, scenes, nodes)
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
    route: dict[str, Any] | None = None,
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

    if previous_id and previous_id != target_id:
        route_metadata = _normalize_route_metadata(route)
        edge = _find_edge(edges, previous_id, target_id)
        if edge:
            edge.update(route_metadata)
        else:
            edges.append({
                "from": previous_id,
                "to": target_id,
                "type": route_metadata.pop("type", "discovered"),
                **route_metadata,
            })

    graph["current_location_id"] = target_id
    graph["nodes"] = nodes
    graph["edges"] = edges
    state["location_graph"] = graph
    return state


def _build_location_edges(
    parsed: dict[str, Any],
    scenes: list[Any],
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    node_lookup = _node_lookup(nodes)

    for index, route in enumerate(_top_level_routes(parsed)):
        _append_edge(edges, _edge_from_route(route, node_lookup, index=index))

    for scene_index, scene in enumerate(scenes):
        if not isinstance(scene, dict) or scene_index >= len(nodes):
            continue
        source_id = str(nodes[scene_index].get("id") or "")
        for exit_index, route in enumerate(_scene_routes(scene)):
            _append_edge(
                edges,
                _edge_from_route(
                    route,
                    node_lookup,
                    source_id=source_id,
                    index=exit_index,
                ),
            )

    for index in range(len(nodes) - 1):
        source = str(nodes[index]["id"])
        target = str(nodes[index + 1]["id"])
        if _has_edge_between(edges, source, target):
            continue
        edges.append({"from": source, "to": target, "type": "sequence"})
    return edges


def _top_level_routes(parsed: dict[str, Any]) -> list[Any]:
    routes: list[Any] = []
    for key in ("edges", "routes", "connections", "exits"):
        value = parsed.get(key)
        if isinstance(value, list):
            routes.extend(value)
        elif isinstance(value, dict):
            routes.extend(_dict_route_entries(value))
    return routes


def _scene_routes(scene: dict[str, Any]) -> list[Any]:
    routes: list[Any] = []
    for key in ("exits", "routes", "connections"):
        value = scene.get(key)
        if isinstance(value, list):
            routes.extend(value)
        elif isinstance(value, dict):
            routes.extend(_dict_route_entries(value))
    return routes


def _dict_route_entries(value: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    for target, metadata in value.items():
        entry = dict(metadata) if isinstance(metadata, dict) else {}
        entry.setdefault("to", target)
        entries.append(entry)
    return entries


def _edge_from_route(
    route: Any,
    node_lookup: dict[str, str],
    *,
    source_id: str | None = None,
    index: int = 0,
) -> dict[str, Any] | None:
    route_data = route if isinstance(route, dict) else {"to": route}
    source = source_id or _resolve_location_ref(
        _first_route_value(route_data, ("from", "source", "source_id", "from_scene", "from_location", "origin")),
        node_lookup,
    )
    target = _resolve_location_ref(
        _first_route_value(
            route_data,
            (
                "to",
                "target",
                "target_id",
                "to_scene",
                "target_scene",
                "destination",
                "destination_id",
                "target_name",
                "destination_name",
                "location",
                "location_id",
            ),
        ),
        node_lookup,
    )
    if not source or not target or source == target:
        return None

    metadata = _normalize_route_metadata(route_data)
    return {
        "id": str(route_data.get("id") or f"edge_{source}_{target}_{index}"),
        "from": source,
        "to": target,
        "type": metadata.pop("type", "route"),
        **metadata,
    }


def _node_lookup(nodes: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for index, node in enumerate(nodes):
        node_id = str(node.get("id") or f"scene_{index}")
        for value in (node_id, node.get("name"), node.get("title"), node.get("location")):
            key = _route_lookup_key(value)
            if key:
                lookup.setdefault(key, node_id)
    return lookup


def _resolve_location_ref(value: Any, node_lookup: dict[str, str]) -> str | None:
    key = _route_lookup_key(value)
    if not key:
        return None
    return node_lookup.get(key)


def _route_lookup_key(value: Any) -> str:
    if value is None:
        return ""
    return normalize_location_id(str(value), fallback="")


def _first_route_value(route: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = route.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _normalize_route_metadata(route: dict[str, Any] | None) -> dict[str, Any]:
    route = route if isinstance(route, dict) else {}
    if not route:
        return {}
    metadata: dict[str, Any] = {}
    route_type = str(
        route.get("route_type")
        or route.get("type")
        or route.get("kind")
        or "route"
    ).strip()
    status = str(route.get("status") or "").strip()
    metadata["type"] = route_type or "route"

    for key, aliases in {
        "label": ("label", "title"),
        "name": ("name",),
        "status": ("status",),
        "requires_key": ("requires_key", "key", "key_item", "requires"),
        "check_type": ("check_type", "skill", "skill_check"),
    }.items():
        value = _first_route_value(route, aliases)
        if value is not None:
            metadata[key] = str(value)

    dc = _first_route_value(route, ("dc", "check_dc", "difficulty"))
    if dc is not None:
        try:
            metadata["dc"] = int(dc)
        except (TypeError, ValueError):
            metadata["dc"] = str(dc)

    locked = (
        _as_bool(route.get("locked"))
        or bool(metadata.get("requires_key"))
        or status.lower() == "locked"
        or route_type.lower() == "locked"
    )
    hidden = (
        _as_bool(route.get("hidden"))
        or _as_bool(route.get("secret"))
        or status.lower() == "hidden"
        or route_type.lower() == "hidden"
    )
    one_way = _as_bool(route.get("one_way")) or _as_bool(route.get("oneWay")) or _as_bool(route.get("oneway"))

    if locked or "locked" in route:
        metadata["locked"] = locked
    if hidden or "hidden" in route or "secret" in route:
        metadata["hidden"] = hidden
    if one_way or "one_way" in route or "oneWay" in route or "oneway" in route:
        metadata["one_way"] = one_way
    return metadata


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "locked", "hidden", "secret", "one_way", "one-way"}


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
        exit_data = {
            "location_id": next_id,
            "name": str(node.get("name") or next_id),
            "description": str(node.get("description") or "")[:180],
            "route_type": str(edge.get("type") or "route"),
            "locked": bool(edge.get("locked") or edge.get("requires_key") or edge.get("status") == "locked" or edge.get("type") == "locked"),
            "hidden": bool(edge.get("hidden") or edge.get("secret") or edge.get("status") == "hidden" or edge.get("type") == "hidden"),
            "one_way": one_way,
        }
        for key in ("id", "label", "requires_key", "status", "dc", "check_type"):
            if edge.get(key) is not None:
                exit_data[key] = edge.get(key)
        exits.append(exit_data)

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
            for key in ("id", "from", "to", "type", "label", "name", "locked", "requires_key", "status", "one_way", "oneWay", "dc", "check_type")
            if key in edge
        })
        public_edges[-1].setdefault("id", f"edge_{index}")
        public_edges[-1].setdefault("from", source)
        public_edges[-1].setdefault("to", target)
        public_edges[-1].setdefault("type", "route")

    public_current_id = current_id if current_id in visible_ids else visible_nodes[0]["id"]
    public_graph = {
        "version": graph.get("version", LOCATION_GRAPH_VERSION),
        "current_location_id": public_current_id,
        "nodes": visible_nodes,
        "edges": public_edges,
    }
    public_templates = _public_encounter_templates(graph, visible_ids)
    if public_templates:
        public_graph["encounter_templates"] = public_templates
        public_template_ids = {str(template.get("id")) for template in public_templates}
        selected_template_id = str(graph.get("selected_encounter_template_id") or "")
        if selected_template_id in public_template_ids:
            public_graph["selected_encounter_template_id"] = selected_template_id
    return public_graph


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


def _append_edge(edges: list[dict[str, Any]], edge: dict[str, Any] | None) -> None:
    if not edge:
        return
    existing = _find_edge(edges, str(edge.get("from") or ""), str(edge.get("to") or ""))
    if existing:
        existing.update({
            key: value
            for key, value in edge.items()
            if key not in {"from", "to"} and value is not None
        })
        return
    edges.append(edge)


def _find_edge(edges: list[dict[str, Any]], source: str, target: str) -> dict[str, Any] | None:
    return next(
        (
            edge for edge in edges
            if str(edge.get("from") or "") == str(source)
            and str(edge.get("to") or "") == str(target)
        ),
        None,
    )


def _has_edge_between(edges: list[dict[str, Any]], source: str, target: str) -> bool:
    return bool(_find_edge(edges, source, target) or _find_edge(edges, target, source))


def _public_encounter_templates(
    graph: dict[str, Any],
    visible_location_ids: set[str],
) -> list[dict[str, Any]]:
    templates = graph.get("encounter_templates") if isinstance(graph.get("encounter_templates"), list) else []
    public_templates = []
    for template in templates:
        if not isinstance(template, dict) or not _is_public_template(template):
            continue
        location_id = str(template.get("location_id") or "")
        if location_id and location_id not in visible_location_ids:
            continue
        public_template = {
            key: template[key]
            for key in ("id", "location_id", "status", "selected", "name", "difficulty_hint", "xp_budget")
            if key in template
        }
        pressure = template_environment_pressure(template)
        if pressure.get("pressure") != "none":
            public_template["environment_pressure"] = pressure
        public_templates.append(public_template)
    return public_templates


def _is_public_template(template: dict[str, Any]) -> bool:
    status = str(template.get("status") or "hidden")
    return bool(
        template.get("selected")
        or template.get("discovered")
        or template.get("revealed")
        or template.get("public")
        or status in {"triggered", "claimed", "resolved"}
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
