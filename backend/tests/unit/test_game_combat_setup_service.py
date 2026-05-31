def test_build_enemy_from_module_preserves_spellcasting_fields():
    from services.game_combat_setup_service import build_enemy_from_module

    enemy = build_enemy_from_module({
        "name": "Cult Mage",
        "hp": 18,
        "ac": 12,
        "ability_scores": {"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 11},
        "actions": [{
            "name": "Dagger",
            "type": "melee_attack",
            "attack_bonus": 4,
            "damage_dice": "1d4+2",
            "damage_type": "piercing",
        }],
        "known_spells": ["Web"],
        "prepared_spells": ["Shield"],
        "cantrips": ["Fire Bolt"],
        "spell_slots": {"1st": 2, "2nd": 1},
        "spell_ability": "int",
        "spell_save_dc": 13,
        "multiattack": 2,
        "legendary_resistances": 3,
        "legendary_actions": [{"name": "Tail Attack", "cost": 2}],
        "legendary_actions_per_round": 3,
        "condition_immunities": ["charmed"],
        "vulnerabilities": ["radiant"],
        "recharge_abilities": [{
            "name": "Fire Breath",
            "recharge": "5-6",
            "description": "A cone of flame.",
        }],
    })

    assert enemy["known_spells"] == ["Web"]
    assert enemy["prepared_spells"] == ["Shield"]
    assert enemy["cantrips"] == ["Fire Bolt"]
    assert enemy["spell_slots"] == {"1st": 2, "2nd": 1}
    assert enemy["spell_ability"] == "int"
    assert enemy["spell_save_dc"] == 13
    assert enemy["concentration"] is None
    assert enemy["attack_bonus"] == 4
    assert enemy["multiattack"] == 2
    assert enemy["attacks_max"] == 2
    assert enemy["legendary_resistances"] == 3
    assert enemy["legendary_resistances_remaining"] == 3
    assert enemy["legendary_actions"][0]["name"] == "Tail Attack"
    assert enemy["legendary_actions"][0]["cost"] == 2
    assert enemy["legendary_action_uses"] == 3
    assert enemy["legendary_action_uses_remaining"] == 3
    assert enemy["condition_immunities"] == ["charmed"]
    assert enemy["vulnerabilities"] == ["radiant"]
    assert enemy["recharge_abilities"][0]["name"] == "Fire Breath"
    assert enemy["recharge_abilities"][0]["threshold"] == 5
    assert enemy["recharge_abilities"][0]["available"] is True
    assert enemy["derived"]["spell_ability"] == "int"
    assert enemy["derived"]["spell_save_dc"] == 13
    assert enemy["derived"]["ability_modifiers"]["int"] == 3


def test_grid_data_from_encounter_template_places_authored_hazard_cells():
    from services.game_combat_setup_service import _grid_data_from_encounter_template

    grid = _grid_data_from_encounter_template({
        "id": "encounter_rune_hall_0",
        "name": "Rune Hall Encounter",
        "cover": [{
            "name": "altar",
            "cover_level": "half",
            "cells": ["10_5"],
        }],
        "terrain": [{
            "name": "oil slick",
            "terrain": "difficult",
            "cells": ["12_5"],
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
    })

    assert grid["10_5"]["terrain"] == "wall"
    assert grid["10_5"]["cover_level"] == "half"
    assert grid["12_5"]["terrain"] == "difficult"
    assert grid["14_5"]["terrain"] == "objective"
    assert grid["_encounter_template"]["hazards"][0]["name"] == "fire jet"
    assert grid["13_5"]["terrain"] == "hazard"
    assert grid["13_5"]["damage_dice"] == "2d6"
    assert grid["13_5"]["save_dc"] == 13
    assert grid["13_6"]["save_ability"] == "dexterity"


async def test_init_combat_stores_encounter_balance(db_session, sample_session, sample_module, sample_character):
    from services.game_combat_setup_service import init_combat

    await init_combat(
        session=sample_session,
        initial_enemies=[{"name": "Goblin", "cr": "1/4", "xp": 50, "hp": 7}],
        characters=[sample_character],
        module=sample_module,
        db=db_session,
    )

    balance = sample_session.game_state["encounter_balance"]
    assert balance["party_size"] == 1
    assert balance["monster_count"] == 1
    assert balance["base_xp"] == 50
    assert balance["difficulty"] in {"easy", "medium", "hard", "deadly"}


async def test_init_combat_uses_current_location_encounter_template(
    db_session,
    sample_session,
    sample_module,
    sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified
    from sqlalchemy import select

    from models import CombatState
    from services.game_combat_setup_service import init_combat
    from services.location_graph_service import build_location_graph_from_module

    parsed = {
        "scenes": [
            {"title": "Gatehouse", "description": "A tense welcome."},
            {
                "title": "Training Yard",
                "description": "A clockwork construct patrols low walls and sparking difficult terrain.",
            },
        ],
        "monsters": [
            {"name": "Clockwork Construct", "cr": "1", "xp": 200, "hp": 22, "ac": 14},
        ],
    }
    graph = build_location_graph_from_module(parsed)
    graph["current_location_id"] = "scene_1"
    sample_module.parsed_content = parsed
    sample_session.game_state = {"location_graph": graph}
    flag_modified(sample_session, "game_state")

    await init_combat(
        session=sample_session,
        initial_enemies=[],
        characters=[sample_character],
        module=sample_module,
        db=db_session,
    )

    assert sample_session.game_state["enemies"][0]["name"] == "Clockwork Construct"
    assert sample_session.game_state["last_encounter_template_id"] == "encounter_scene_1_0"
    assert sample_session.game_state["last_encounter_template_balance"]["estimate"]["party_size"] == 1
    assert sample_session.game_state["last_encounter_template_balance"]["estimated_difficulty"] == "deadly"
    assert sample_session.game_state["location_graph"]["encounter_templates"][0]["status"] == "triggered"

    combat = (
        await db_session.execute(select(CombatState).where(CombatState.session_id == sample_session.id))
    ).scalar_one()
    enemy_id = sample_session.game_state["enemies"][0]["id"]
    assert combat.entity_positions[enemy_id] == {"x": 15, "y": 6}
    assert combat.grid_data["_encounter_template"]["id"] == "encounter_scene_1_0"
    assert combat.grid_data["10_4"] == "wall"
    assert combat.grid_data["11_6"] == "difficult"


async def test_init_combat_uses_tuned_encounter_template_roster(
    db_session,
    sample_session,
    sample_module,
    sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    from services.game_combat_setup_service import init_combat
    from services.location_graph_service import build_location_graph_from_module

    parsed = {
        "scenes": [{
            "title": "Goblin Yard",
            "description": "Three goblins guard the narrow yard.",
            "monsters": ["Goblin Scout", "Goblin Cutter", "Goblin Lookout"],
        }],
        "monsters": [
            {"name": "Goblin Scout", "cr": "1/4", "xp": 50, "hp": 7, "ac": 13},
            {"name": "Goblin Cutter", "cr": "1/4", "xp": 50, "hp": 7, "ac": 13},
            {"name": "Goblin Lookout", "cr": "1/4", "xp": 50, "hp": 7, "ac": 13},
        ],
    }
    graph = build_location_graph_from_module(parsed)
    graph["current_location_id"] = "scene_0"
    sample_module.parsed_content = parsed
    sample_session.game_state = {"location_graph": graph}
    flag_modified(sample_module, "parsed_content")
    flag_modified(sample_session, "game_state")

    await init_combat(
        session=sample_session,
        initial_enemies=[],
        characters=[sample_character],
        module=sample_module,
        db=db_session,
    )

    assert [enemy["name"] for enemy in sample_session.game_state["enemies"]] == ["Goblin Scout"]
    assert [item["name"] for item in sample_session.game_state["last_encounter_template_staged_enemies"]] == [
        "Goblin Cutter",
        "Goblin Lookout",
    ]
    tuning = sample_session.game_state["last_encounter_template_balance"]["roster_tuning"]
    assert tuning["strategy"] == "stage_extra_enemies"
    assert tuning["estimated_difficulty_after_tuning"] == "hard"
    assert sample_session.game_state["encounter_balance"]["difficulty"] == "hard"


async def test_init_combat_adds_minions_for_underbudget_encounter_template(
    db_session,
    sample_session,
    sample_module,
    sample_character,
):
    from types import SimpleNamespace

    from sqlalchemy.orm.attributes import flag_modified

    from services.game_combat_setup_service import init_combat
    from services.location_graph_service import build_location_graph_from_module

    parsed = {
        "scenes": [{
            "title": "Bandit Yard",
            "description": "A lone bandit blocks the gate.",
            "monsters": ["Bandit"],
            "target_difficulty": "medium",
        }],
        "monsters": [
            {"name": "Bandit", "cr": "1/8", "xp": 25, "hp": 11, "ac": 12},
        ],
    }
    graph = build_location_graph_from_module(parsed)
    graph["current_location_id"] = "scene_0"
    sample_module.parsed_content = parsed
    sample_session.game_state = {"location_graph": graph}
    flag_modified(sample_module, "parsed_content")
    flag_modified(sample_session, "game_state")
    party = [
        sample_character,
        SimpleNamespace(id="pc-2", name="Ally 2", derived={"initiative": 1}, is_player=True, level=1),
        SimpleNamespace(id="pc-3", name="Ally 3", derived={"initiative": 1}, is_player=True, level=1),
        SimpleNamespace(id="pc-4", name="Ally 4", derived={"initiative": 1}, is_player=True, level=1),
    ]

    await init_combat(
        session=sample_session,
        initial_enemies=[],
        characters=party,
        module=sample_module,
        db=db_session,
    )

    assert [enemy["name"] for enemy in sample_session.game_state["enemies"]] == [
        "Bandit",
        "Bandit",
        "Bandit",
        "Bandit",
    ]
    tuning = sample_session.game_state["last_encounter_template_balance"]["roster_tuning"]
    assert tuning["strategy"] == "add_minions"
    assert tuning["added_count"] == 3
    assert sample_session.game_state["encounter_balance"]["difficulty"] == "medium"


async def test_init_combat_prefers_selected_encounter_template(
    db_session,
    sample_session,
    sample_module,
    sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    from services.game_combat_setup_service import init_combat

    sample_module.parsed_content = {
        "monsters": [
            {"name": "Bandit", "cr": "1/8", "xp": 25, "hp": 11, "ac": 12},
            {"name": "Guard", "cr": "1/8", "xp": 25, "hp": 11, "ac": 16},
        ],
    }
    sample_session.game_state = {
        "location_graph": {
            "current_location_id": "yard",
            "selected_encounter_template_id": "encounter_yard_1",
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
                    "selected": True,
                    "initial_enemies": [{"name": "Guard"}],
                },
            ],
        }
    }
    flag_modified(sample_module, "parsed_content")
    flag_modified(sample_session, "game_state")

    await init_combat(
        session=sample_session,
        initial_enemies=[],
        characters=[sample_character],
        module=sample_module,
        db=db_session,
    )

    assert sample_session.game_state["enemies"][0]["name"] == "Guard"
    assert sample_session.game_state["last_encounter_template_id"] == "encounter_yard_1"
    assert sample_session.game_state["location_graph"].get("selected_encounter_template_id") is None
    assert sample_session.game_state["location_graph"]["encounter_templates"][1]["status"] == "triggered"
