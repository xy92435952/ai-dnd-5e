from services.encounter_template_service import (
    attach_party_balance_to_template,
    attach_encounter_templates_to_graph,
    build_encounter_templates_from_module,
    mark_encounter_template_triggered,
    select_encounter_template,
    select_current_encounter_template,
)


def test_build_encounter_templates_links_monsters_to_combat_scene():
    parsed = {
        "scenes": [
            {"title": "Gatehouse", "description": "A tense welcome."},
            {
                "title": "Training Yard",
                "description": "Two constructs patrol near low walls and sparking difficult terrain.",
            },
        ],
        "monsters": [
            {"name": "Clockwork Training Construct", "cr": "1", "xp": 200, "ac": 14, "hp": 22},
            {"name": "Voltaic Spark", "cr": "1/2", "xp": 100, "speed": 40},
        ],
        "key_rewards": ["Gate Token"],
    }

    templates = build_encounter_templates_from_module(parsed, [
        {"id": "scene_0", "name": "Gatehouse"},
        {"id": "scene_1", "name": "Training Yard"},
    ])

    assert len(templates) == 1
    template = templates[0]
    assert template["location_id"] == "scene_1"
    assert template["status"] == "available"
    assert template["difficulty_hint"] == "moderate"
    assert template["enemy_names"] == ["Clockwork Training Construct", "Voltaic Spark"]
    assert template["initial_enemies"] == [
        {"name": "Clockwork Training Construct"},
        {"name": "Voltaic Spark"},
    ]
    assert template["cover"] == ["low walls"]
    assert "unstable energy" in template["hazards"]
    assert template["reward_hints"] == ["Gate Token"]


def test_attach_encounter_templates_to_graph_preserves_runtime_status():
    parsed = {
        "scenes": [{"title": "Cave", "description": "A goblin guard waits."}],
        "monsters": [{"name": "Goblin Guard", "cr": "1/4", "xp": 50}],
    }
    graph = {
        "current_location_id": "scene_0",
        "nodes": [{"id": "scene_0", "name": "Cave"}],
        "edges": [],
        "encounter_templates": [{
            "id": "encounter_scene_0_0",
            "status": "triggered",
        }],
    }

    updated = attach_encounter_templates_to_graph(graph, parsed)

    assert updated["encounter_templates"][0]["status"] == "triggered"
    assert updated["nodes"][0]["encounter_template_ids"] == ["encounter_scene_0_0"]


def test_select_and_mark_current_encounter_template():
    state = {
        "location_graph": {
            "current_location_id": "yard",
            "nodes": [{"id": "yard", "name": "Yard"}],
            "encounter_templates": [{
                "id": "encounter_yard_0",
                "location_id": "yard",
                "status": "available",
                "initial_enemies": [{"name": "Bandit"}],
            }],
        }
    }

    selected = select_current_encounter_template(state)
    assert selected["id"] == "encounter_yard_0"

    updated = mark_encounter_template_triggered(state, selected["id"])
    assert updated["location_graph"]["encounter_templates"][0]["status"] == "triggered"
    assert updated["location_graph"].get("selected_encounter_template_id") is None
    assert state["location_graph"]["encounter_templates"][0]["status"] == "available"


def test_attach_party_balance_to_template_estimates_party_fit():
    template = {
        "id": "encounter_yard_0",
        "location_id": "yard",
        "difficulty_hint": "moderate",
        "initial_enemies": [{"name": "Clockwork Construct"}],
    }
    parsed = {
        "monsters": [
            {"name": "Clockwork Construct", "cr": "1", "xp": 200},
        ],
    }

    balanced = attach_party_balance_to_template(
        template,
        party=[{"id": "pc-1", "level": 1}],
        parsed=parsed,
    )

    assert "party_balance" not in template
    assert balanced["party_balance"]["target_difficulty"] == "medium"
    assert balanced["party_balance"]["estimated_difficulty"] == "deadly"
    assert balanced["party_balance"]["recommended_adjustment"] == "reduce_or_stage_enemies"
    assert balanced["party_balance"]["estimate"]["party_size"] == 1


def test_select_encounter_template_prefers_selected_available_template():
    state = {
        "location_graph": {
            "current_location_id": "yard",
            "nodes": [{"id": "yard", "name": "Yard"}],
            "encounter_templates": [
                {
                    "id": "encounter_yard_0",
                    "location_id": "yard",
                    "status": "available",
                    "initial_enemies": [{"name": "Bandit"}],
                },
                {
                    "id": "encounter_yard_1",
                    "location_id": "yard",
                    "status": "available",
                    "initial_enemies": [{"name": "Guard"}],
                },
            ],
        }
    }

    updated, selected = select_encounter_template(state, "encounter_yard_1")

    assert selected["id"] == "encounter_yard_1"
    assert updated["location_graph"]["selected_encounter_template_id"] == "encounter_yard_1"
    assert updated["location_graph"]["encounter_templates"][1]["selected"] is True
    assert select_current_encounter_template(updated)["id"] == "encounter_yard_1"
    assert select_current_encounter_template(state)["id"] == "encounter_yard_0"


def test_select_encounter_template_rejects_other_location():
    state = {
        "location_graph": {
            "current_location_id": "yard",
            "nodes": [{"id": "yard", "name": "Yard"}, {"id": "vault", "name": "Vault"}],
            "encounter_templates": [{
                "id": "encounter_vault_0",
                "location_id": "vault",
                "status": "available",
            }],
        }
    }

    try:
        select_encounter_template(state, "encounter_vault_0")
    except ValueError as exc:
        assert "current location" in str(exc)
    else:
        raise AssertionError("expected other-location encounter selection to fail")
