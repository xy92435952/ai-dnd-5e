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
    assert template["enemy_roles"] == [
        {"name": "Clockwork Training Construct", "role": "striker"},
        {"name": "Voltaic Spark", "role": "skirmisher"},
    ]
    assert template["cover"] == ["low walls"]
    assert "unstable energy" in template["hazards"]
    assert template["reward_hints"] == ["Gate Token"]


def test_build_encounter_templates_infers_tactical_ai_roles():
    templates = build_encounter_templates_from_module({
        "scenes": [{
            "title": "Role Yard",
            "description": "A mixed enemy squad blocks the road.",
            "monsters": ["War Priest", "Web Adept", "Iron Guard", "Knife Dancer", "Ogre Mauler"],
        }],
        "monsters": [
            {"name": "War Priest", "prepared_spells": ["Healing Word"], "hp": 18, "ac": 14},
            {"name": "Web Adept", "known_spells": ["Web"], "hp": 16, "ac": 12},
            {"name": "Iron Guard", "hp": 42, "ac": 18},
            {"name": "Knife Dancer", "hp": 12, "ac": 13, "speed": 45},
            {"name": "Ogre Mauler", "hp": 26, "ac": 13, "multiattack": 2},
        ],
    }, [{"id": "role_yard"}])

    roles = {item["name"]: item["role"] for item in templates[0]["enemy_roles"]}

    assert roles == {
        "War Priest": "healer",
        "Web Adept": "controller",
        "Iron Guard": "defender",
        "Knife Dancer": "skirmisher",
        "Ogre Mauler": "striker",
    }


def test_build_encounter_templates_preserves_structured_hazard_metadata():
    parsed = {
        "scenes": [{
            "title": "Rune Hall",
            "description": "A cult guardian waits beside a fire jet trap.",
            "monsters": ["Cult Guardian"],
            "terrain": [{
                "name": "oil slick",
                "terrain": "difficult",
                "cells": ["12_5"],
            }],
            "cover": [{
                "name": "altar",
                "cover_level": "half",
                "cells": ["10_5"],
            }],
            "objectives": [{
                "name": "seal the rift",
                "cells": ["14_5"],
            }],
            "hazards": [{
                "name": "fire jet",
                "damage_dice": "2d6",
                "damage_type": "fire",
                "save_dc": 13,
                "save_ability": "dexterity",
                "half_on_save": True,
                "cells": ["13_5", {"x": 13, "y": 6}],
            }],
        }],
        "monsters": [
            {"name": "Cult Guardian", "cr": "1/2", "xp": 100},
        ],
    }

    templates = build_encounter_templates_from_module(parsed, [{"id": "rune_hall"}])

    hazard = templates[0]["hazards"][0]
    assert templates[0]["terrain"][0]["name"] == "oil slick"
    assert templates[0]["cover"][0]["cover_level"] == "half"
    assert templates[0]["objectives"][0]["cells"] == ["14_5"]
    assert hazard["name"] == "fire jet"
    assert hazard["damage_dice"] == "2d6"
    assert hazard["damage_type"] == "fire"
    assert hazard["save_dc"] == 13
    assert hazard["save_ability"] == "dexterity"
    assert hazard["half_on_save"] is True
    assert hazard["cells"] == ["13_5", {"x": 13, "y": 6}]


def test_build_encounter_templates_preserves_authored_target_difficulty():
    templates = build_encounter_templates_from_module({
        "scenes": [{
            "title": "Bandit Yard",
            "description": "A lone bandit blocks the gate.",
            "monsters": ["Bandit"],
            "target_difficulty": "moderate",
        }],
        "monsters": [
            {"name": "Bandit", "cr": "1/8", "xp": 25},
        ],
    }, [{"id": "yard"}])

    assert templates[0]["difficulty_hint"] == "light"
    assert templates[0]["target_difficulty"] == "medium"


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
    assert balanced["party_balance"]["action_adjusted_difficulty"] == "deadly"
    assert balanced["party_balance"]["environment_adjusted_difficulty"] == "deadly"
    assert balanced["party_balance"]["environment_pressure"]["pressure"] == "none"
    assert balanced["party_balance"]["recommended_adjustment"] == "reduce_or_stage_enemies"
    assert balanced["party_balance"]["estimate"]["party_size"] == 1
    assert balanced["party_balance"]["estimate"]["action_economy"]["pressure"] == "even"


def test_attach_party_balance_to_template_records_environment_pressure():
    template = {
        "id": "encounter_rune_hall_0",
        "location_id": "rune_hall",
        "difficulty_hint": "light",
        "initial_enemies": [{"name": "Bandit"}],
        "terrain": [{"name": "oil slick", "terrain": "difficult", "cells": ["12_5"]}],
        "cover": [{"name": "altar", "cover_level": "half", "cells": ["10_5"]}],
        "objectives": [{"name": "seal the rift", "cells": ["14_5"]}],
        "hazards": [{
            "name": "fire jet",
            "damage_dice": "2d6",
            "save_dc": 13,
            "cells": ["13_5", {"x": 13, "y": 6}],
        }],
    }
    parsed = {
        "monsters": [
            {"name": "Bandit", "cr": "1/8", "xp": 25},
        ],
    }

    balanced = attach_party_balance_to_template(
        template,
        party=[{"id": "pc-1", "level": 1}],
        parsed=parsed,
    )

    pressure = balanced["party_balance"]["environment_pressure"]
    assert pressure == {
        "pressure": "heavy",
        "score": 7,
        "hazards": 1,
        "damaging_hazards": 1,
        "objectives": 1,
        "cover": 1,
        "terrain": 1,
        "authored_cells": 5,
    }
    assert balanced["party_balance"]["estimated_difficulty"] == "easy"
    assert balanced["party_balance"]["environment_adjusted_difficulty"] == "medium"


def test_attach_party_balance_to_template_stages_extra_enemies_for_small_party():
    template = {
        "id": "encounter_yard_0",
        "location_id": "yard",
        "difficulty_hint": "moderate",
        "initial_enemies": [
            {"name": "Goblin Scout"},
            {"name": "Goblin Cutter"},
            {"name": "Goblin Lookout"},
        ],
    }
    parsed = {
        "monsters": [
            {"name": "Goblin Scout", "cr": "1/4", "xp": 50},
            {"name": "Goblin Cutter", "cr": "1/4", "xp": 50},
            {"name": "Goblin Lookout", "cr": "1/4", "xp": 50},
        ],
    }

    balanced = attach_party_balance_to_template(
        template,
        party=[{"id": "pc-1", "level": 1}],
        parsed=parsed,
    )

    assert [item["name"] for item in balanced["balanced_initial_enemies"]] == ["Goblin Scout"]
    assert [item["name"] for item in balanced["staged_initial_enemies"]] == [
        "Goblin Cutter",
        "Goblin Lookout",
    ]
    tuning = balanced["party_balance"]["roster_tuning"]
    assert tuning["strategy"] == "stage_extra_enemies"
    assert tuning["estimated_difficulty_after_tuning"] == "hard"


def test_attach_party_balance_to_template_adds_minions_for_underbudget_party():
    template = {
        "id": "encounter_yard_0",
        "location_id": "yard",
        "difficulty_hint": "moderate",
        "initial_enemies": [{"name": "Bandit"}],
    }
    parsed = {
        "monsters": [
            {"name": "Bandit", "cr": "1/8", "xp": 25},
        ],
    }

    balanced = attach_party_balance_to_template(
        template,
        party=[
            {"id": "pc-1", "level": 1},
            {"id": "pc-2", "level": 1},
            {"id": "pc-3", "level": 1},
            {"id": "pc-4", "level": 1},
        ],
        parsed=parsed,
    )

    assert [item["name"] for item in balanced["balanced_initial_enemies"]] == [
        "Bandit",
        "Bandit",
        "Bandit",
        "Bandit",
    ]
    assert balanced["staged_initial_enemies"] == []
    tuning = balanced["party_balance"]["roster_tuning"]
    assert tuning["strategy"] == "add_minions"
    assert tuning["active_count"] == 4
    assert tuning["added_count"] == 3
    assert tuning["estimated_difficulty_after_tuning"] == "medium"


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
