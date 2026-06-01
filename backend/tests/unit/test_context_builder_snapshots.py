from types import SimpleNamespace

from services.context_builder_snapshots import build_game_state_payload


def _character(
    *,
    char_id: str,
    name: str,
    mods: dict,
    proficient_skills: list[str] | None = None,
    feats: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=char_id,
        name=name,
        race="Human",
        char_class="Rogue",
        level=1,
        hp_current=8,
        derived={
            "hp_max": 8,
            "ability_modifiers": mods,
            "proficiency_bonus": 2,
        },
        spell_slots={},
        conditions=[],
        death_saves=None,
        concentration=None,
        known_spells=[],
        cantrips=[],
        proficient_skills=proficient_skills or [],
        proficient_saves=[],
        feats=feats or [],
        is_player=True,
        personality="",
        backstory="",
        speech_style="",
        combat_preference="",
        catchphrase="",
        equipment={},
        active_effects={},
        condition_durations={},
    )


def test_game_state_payload_includes_exploration_context_for_dm_input():
    session = SimpleNamespace(
        id="session-1",
        game_state={
            "dm_style": "classic",
            "location_graph": {
                "current_location_id": "yard",
                "nodes": [
                    {"id": "gate", "name": "Gatehouse", "visited": True},
                    {"id": "yard", "name": "Training Yard", "visited": True, "encounter_template_ids": ["enc_yard"]},
                    {"id": "vault", "name": "Vault", "visited": False},
                ],
                "edges": [
                    {"from": "gate", "to": "yard", "type": "sequence"},
                    {"from": "yard", "to": "vault", "type": "locked", "locked": True},
                ],
                "encounter_templates": [
                    {"id": "enc_yard", "location_id": "yard", "status": "available", "name": "Construct Patrol"},
                ],
            },
            "loot_pool": {
                "items": [
                    {"id": "loot_gold_0", "name": "25 gp", "category": "gold", "amount": 25, "status": "available"},
                    {
                        "id": "loot_gear_gate_token_1",
                        "name": "Gate Token",
                        "category": "gear",
                        "status": "claimed",
                        "claimed_by_name": "Scout",
                    },
                    {
                        "id": "loot_weapon_moonblade_2",
                        "name": "Moonblade",
                        "category": "weapon",
                        "status": "hidden",
                        "source": "magic_items",
                    },
                ],
            },
        },
        combat_active=False,
        current_scene="Entry",
        is_multiplayer=False,
    )
    scout = _character(
        char_id="scout",
        name="Scout",
        mods={"wis": 2, "int": 1, "dex": 4},
        proficient_skills=["perception", "stealth"],
    )
    sage = _character(
        char_id="sage",
        name="Sage",
        mods={"wis": 1, "int": 4, "dex": 0},
        proficient_skills=["investigation"],
        feats=[{"name": "Observant"}],
    )

    state = build_game_state_payload(session=session, characters=[scout, sage])

    assert state["characters"][1]["feats"] == [{"name": "Observant"}]
    assert state["exploration_context"]["character_passives"] == [
        {
            "character_id": "scout",
            "name": "Scout",
            "passive_perception": 14,
            "passive_investigation": 11,
            "passive_stealth": 16,
        },
        {
            "character_id": "sage",
            "name": "Sage",
            "passive_perception": 16,
            "passive_investigation": 21,
            "passive_stealth": 10,
        },
    ]
    assert state["exploration_context"]["party_best_passive"]["perception"] == {
        "character_id": "sage",
        "name": "Sage",
        "score": 16,
        "skill": "perception",
    }
    assert state["exploration_context"]["party_best_passive"]["investigation"]["score"] == 21
    assert state["exploration_context"]["party_best_passive"]["stealth"]["character_id"] == "scout"
    assert state["exploration_context"]["group_stealth"] == {
        "skill": "stealth",
        "success_rule": "at_least_half_members_meet_or_exceed_dc",
    }
    assert state["location_graph_context"]["current"]["name"] == "Training Yard"
    assert state["location_graph_context"]["exits"] == [
        {
            "location_id": "gate",
            "name": "Gatehouse",
            "description": "",
            "route_type": "sequence",
            "locked": False,
            "hidden": False,
            "one_way": False,
        },
        {
            "location_id": "vault",
            "name": "Vault",
            "description": "",
            "route_type": "locked",
            "locked": True,
            "hidden": False,
            "one_way": False,
        },
    ]
    assert state["location_graph_context"]["current_encounters"][0]["name"] == "Construct Patrol"
    assert state["reward_context"]["available_count"] == 1
    assert state["reward_context"]["claimed_count"] == 1
    assert state["reward_context"]["hidden_count"] == 1
    assert state["reward_context"]["available_loot"][0]["name"] == "25 gp"
    assert state["reward_context"]["claimed_loot"][0]["claimed_by_name"] == "Scout"
    assert state["reward_context"]["discoverable_loot_hints"][0]["id"] == "loot_weapon_moonblade_2"
