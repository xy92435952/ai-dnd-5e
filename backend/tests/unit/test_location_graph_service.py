from services.location_graph_service import (
    apply_location_update,
    build_location_graph_from_module,
    ensure_location_graph_state,
    public_location_graph,
    tag_player_choices_with_location_exits,
)


def test_build_location_graph_from_module_scenes():
    graph = build_location_graph_from_module({
        "scenes": [
            {"title": "Rain at the Gatehouse", "description": "Storm and tripwire."},
            {"name": "Training Yard", "description": "Construct patrols."},
        ],
        "monsters": [{"name": "Training Construct", "cr": "1/4", "xp": 50}],
    })

    assert graph["current_location_id"] == "scene_0"
    assert [node["name"] for node in graph["nodes"]] == [
        "Rain at the Gatehouse",
        "Training Yard",
    ]
    assert graph["nodes"][0]["visited"] is True
    assert graph["nodes"][1]["visited"] is False
    assert graph["edges"] == [{"from": "scene_0", "to": "scene_1", "type": "sequence"}]
    assert graph["encounter_templates"][0]["location_id"] == "scene_1"
    assert graph["nodes"][1]["encounter_template_ids"] == ["encounter_scene_1_0"]


def test_build_location_graph_from_module_preserves_authored_route_metadata():
    graph = build_location_graph_from_module({
        "scenes": [
            {
                "id": "gate",
                "title": "Gatehouse",
                "exits": [
                    {
                        "to": "vault",
                        "type": "locked",
                        "label": "Ironbound Door",
                        "requires_key": "Gate Token",
                        "one_way": True,
                        "dc": 14,
                        "check_type": "athletics",
                    }
                ],
            },
            {"id": "vault", "title": "Vault"},
        ],
    })

    assert graph["edges"] == [
        {
            "id": "edge_gate_vault_0",
            "from": "gate",
            "to": "vault",
            "type": "locked",
            "label": "Ironbound Door",
            "requires_key": "Gate Token",
            "check_type": "athletics",
            "dc": 14,
            "locked": True,
            "one_way": True,
        }
    ]


def test_apply_location_update_moves_to_existing_scene_and_marks_visited():
    state = ensure_location_graph_state({}, {
        "scenes": [
            {"title": "Gatehouse"},
            {"title": "Training Yard"},
        ]
    })

    updated = apply_location_update(
        state,
        {},
        location_name="Training Yard",
    )

    assert updated["location_graph"]["current_location_id"] == "scene_1"
    assert updated["location_graph"]["nodes"][1]["visited"] is True


def test_apply_location_update_adds_discovered_runtime_location():
    updated = apply_location_update(
        {"location_graph": build_location_graph_from_module({"setting": "Road"})},
        {},
        location_name="Hidden Shrine",
    )

    graph = updated["location_graph"]
    assert graph["current_location_id"] == "hidden_shrine"
    assert graph["nodes"][-1]["name"] == "Hidden Shrine"
    assert graph["edges"][-1] == {
        "from": "scene_0",
        "to": "hidden_shrine",
        "type": "discovered",
    }


def test_apply_location_update_persists_runtime_route_metadata():
    updated = apply_location_update(
        {"location_graph": build_location_graph_from_module({"setting": "Road"})},
        {},
        location_name="Hidden Shrine",
        route={
            "type": "hidden",
            "label": "Cracked stair",
            "hidden": True,
            "one_way": True,
            "requires_key": "Moon Sigil",
            "dc": 16,
            "check_type": "investigation",
        },
    )

    graph = updated["location_graph"]
    assert graph["edges"][-1] == {
        "from": "scene_0",
        "to": "hidden_shrine",
        "type": "hidden",
        "label": "Cracked stair",
        "requires_key": "Moon Sigil",
        "check_type": "investigation",
        "dc": 16,
        "locked": True,
        "hidden": True,
        "one_way": True,
    }


def test_public_location_graph_hides_future_nodes_and_encounters():
    graph = build_location_graph_from_module({
        "scenes": [
            {"title": "Gatehouse", "description": "Stone entry."},
            {"title": "Training Yard", "description": "Low walls."},
            {"title": "Vault", "description": "Sealed door."},
        ],
        "monsters": [{"name": "Vault Guard", "cr": "1/2", "xp": 100}],
    })

    public = public_location_graph(graph)

    assert [node["name"] for node in public["nodes"]] == ["Gatehouse"]
    assert public["current_location_id"] == "scene_0"
    assert public["edges"] == []
    assert "encounter_templates" not in public


def test_public_location_graph_preserves_selected_encounter_template_id():
    public = public_location_graph({
        "current_location_id": "yard",
        "selected_encounter_template_id": "encounter_yard_0",
        "nodes": [{"id": "yard", "name": "Yard", "visited": True}],
        "edges": [],
        "encounter_templates": [{
            "id": "encounter_yard_0",
            "location_id": "yard",
            "status": "available",
            "selected": True,
            "enemy_names": ["Hidden Guard"],
            "tactics": "Hidden plan",
        }],
    })

    assert public["selected_encounter_template_id"] == "encounter_yard_0"
    assert public["encounter_templates"] == [{
        "id": "encounter_yard_0",
        "location_id": "yard",
        "status": "available",
        "selected": True,
    }]


def test_public_location_graph_hides_selected_template_id_for_hidden_location():
    public = public_location_graph({
        "current_location_id": "gate",
        "selected_encounter_template_id": "encounter_vault_0",
        "nodes": [
            {"id": "gate", "name": "Gatehouse", "visited": True},
            {"id": "vault", "name": "Secret Vault", "visited": False},
        ],
        "edges": [{"from": "gate", "to": "vault", "type": "hidden", "hidden": True}],
        "encounter_templates": [{
            "id": "encounter_vault_0",
            "location_id": "vault",
            "status": "available",
            "selected": True,
            "name": "Vault Ambush",
            "enemy_names": ["Moonlit Warden"],
        }],
    })

    assert [node["name"] for node in public["nodes"]] == ["Gatehouse"]
    assert public["edges"] == []
    assert "encounter_templates" not in public
    assert "selected_encounter_template_id" not in public


def test_public_location_graph_exposes_safe_environment_pressure_only():
    public = public_location_graph({
        "current_location_id": "yard",
        "nodes": [{"id": "yard", "name": "Yard", "visited": True}],
        "edges": [],
        "encounter_templates": [{
            "id": "encounter_yard_0",
            "location_id": "yard",
            "status": "available",
            "selected": True,
            "name": "Yard Patrol",
            "enemy_names": ["Hidden Guard"],
            "tactics": "Hidden plan",
            "terrain": [{"name": "oil slick", "cells": ["1_1"]}],
            "cover": [{"name": "barricade", "cells": ["2_1"]}],
            "objectives": [{"name": "hold the gate", "cells": ["3_1"]}],
            "hazards": [{
                "name": "fire jet",
                "damage_dice": "2d6",
                "save_dc": 13,
                "cells": ["4_1", "4_2"],
            }],
        }],
    })

    template = public["encounter_templates"][0]
    assert template["environment_pressure"] == {
        "pressure": "heavy",
        "score": 7,
        "hazards": 1,
        "damaging_hazards": 1,
        "objectives": 1,
        "cover": 1,
        "terrain": 1,
        "authored_cells": 5,
    }
    assert "enemy_names" not in template
    assert "tactics" not in template
    assert "hazards" not in template


def test_tag_player_choices_with_location_exits_converts_matching_strings():
    state = {
        "location_graph": {
            "version": 1,
            "current_location_id": "gate",
            "nodes": [
                {"id": "gate", "name": "Gatehouse", "visited": True},
                {"id": "yard", "name": "Training Yard", "visited": False},
            ],
            "edges": [{"from": "gate", "to": "yard", "type": "sequence"}],
        },
    }

    tagged = tag_player_choices_with_location_exits(
        [
            "Ask the guard",
            "Ask the guard about the Training Yard",
            "Go to the Training Yard",
        ],
        state,
    )

    assert tagged[0] == "Ask the guard"
    assert tagged[1] == "Ask the guard about the Training Yard"
    assert tagged[2]["text"] == "Go to the Training Yard"
    assert tagged[2]["choice_type"] == "movement"
    assert tagged[2]["location_exit"] == {
        "target_location_id": "yard",
        "target_location_name": "Training Yard",
        "route_type": "sequence",
        "locked": False,
        "hidden": False,
        "one_way": False,
    }
    assert tagged[2]["tags"] == [{"label": "Exit", "kind": "location_exit"}]


def test_tag_player_choices_with_location_exits_preserves_existing_choice_fields():
    state = {
        "location_graph": {
            "version": 1,
            "current_location_id": "gate",
            "nodes": [
                {"id": "gate", "name": "Gatehouse", "visited": True},
                {"id": "vault", "name": "Sealed Vault", "visited": False},
            ],
            "edges": [
                {
                    "from": "gate",
                    "to": "vault",
                    "type": "locked",
                    "locked": True,
                    "one_way": True,
                    "requires_key": "Bronze Key",
                    "check_type": "thieves_tools",
                    "dc": 15,
                },
            ],
        },
    }

    tagged = tag_player_choices_with_location_exits(
        [
            {
                "text": "Force the Sealed Vault door",
                "choice_type": "danger",
                "skill_check": True,
                "tags": [{"label": "Athletics", "kind": "athletic", "dc": 15}],
            }
        ],
        state,
    )

    assert tagged[0]["choice_type"] == "danger"
    assert tagged[0]["skill_check"] is True
    assert tagged[0]["tags"] == [
        {"label": "Athletics", "kind": "athletic", "dc": 15},
        {"label": "Exit", "kind": "location_exit"},
    ]
    assert tagged[0]["location_exit"]["target_location_id"] == "vault"
    assert tagged[0]["location_exit"]["locked"] is True
    assert tagged[0]["location_exit"]["one_way"] is True
    assert tagged[0]["location_exit"]["requires_key"] == "Bronze Key"
    assert tagged[0]["location_exit"]["check_type"] == "thieves_tools"
    assert tagged[0]["location_exit"]["dc"] == 15


def test_tag_player_choices_with_location_exits_does_not_expose_hidden_exits():
    state = {
        "location_graph": {
            "version": 1,
            "current_location_id": "gate",
            "nodes": [
                {"id": "gate", "name": "Gatehouse", "visited": True},
                {"id": "vault", "name": "Secret Vault", "visited": False},
            ],
            "edges": [{"from": "gate", "to": "vault", "type": "hidden", "hidden": True}],
        },
    }

    tagged = tag_player_choices_with_location_exits(["Go to the Secret Vault"], state)

    assert tagged == ["Go to the Secret Vault"]
