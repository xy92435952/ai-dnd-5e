from services.location_graph_service import (
    apply_location_update,
    build_location_graph_from_module,
    ensure_location_graph_state,
    public_location_graph,
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
