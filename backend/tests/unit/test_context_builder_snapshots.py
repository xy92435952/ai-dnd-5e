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
        game_state={"dm_style": "classic"},
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
