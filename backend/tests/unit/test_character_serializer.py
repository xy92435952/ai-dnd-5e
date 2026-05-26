from types import SimpleNamespace

from services.character_serializer import serialize_character


def test_serialize_character_falls_back_to_safe_collections_and_derived_values():
    char = SimpleNamespace(
        id="char-1",
        is_player=True,
        name="测试角色",
        race="Human",
        char_class="Fighter",
        subclass=None,
        level=1,
        background="Soldier",
        alignment="中立善良",
        ability_scores={"str": 16},
        derived={"hp_max": 12, "ac": 16, "subclass_effects": {"crit_threshold": 19}},
        hp_current=7,
        spell_slots=None,
        known_spells=None,
        prepared_spells=None,
        cantrips=None,
        concentration=None,
        proficient_skills=None,
        proficient_saves=None,
        equipment=None,
        fighting_style="Defense",
        languages=None,
        tool_proficiencies=None,
        feats=None,
        conditions=None,
        death_saves=None,
        personality="沉默",
        speech_style="短句",
        combat_preference="防守",
        backstory="边境老兵",
        catchphrase="继续前进。",
        multiclass_info=None,
        condition_durations=None,
    )

    data = serialize_character(char)

    assert data["hp_max"] == 12
    assert data["ac"] == 16
    assert data["spell_slots"] == {}
    assert data["known_spells"] == []
    assert data["equipment"] == {}
    assert data["subclass_effects"] == {"crit_threshold": 19}


def test_serialize_character_uses_effective_hp_max_for_exhaustion():
    char = SimpleNamespace(
        id="char-2",
        is_player=True,
        name="Exhausted",
        race="Human",
        char_class="Fighter",
        subclass=None,
        level=1,
        background=None,
        alignment=None,
        ability_scores={},
        derived={"hp_max": 12, "ac": 16},
        hp_current=6,
        spell_slots=None,
        known_spells=None,
        prepared_spells=None,
        cantrips=None,
        concentration=None,
        proficient_skills=None,
        proficient_saves=None,
        equipment=None,
        fighting_style=None,
        languages=None,
        tool_proficiencies=None,
        feats=None,
        conditions=["exhaustion"],
        death_saves=None,
        personality=None,
        speech_style=None,
        combat_preference=None,
        backstory=None,
        catchphrase=None,
        multiclass_info=None,
        condition_durations={"exhaustion_level": 4},
    )

    data = serialize_character(char)

    assert data["hp_max"] == 6
    assert data["base_hp_max"] == 12
    assert data["derived"]["hp_max"] == 6
    assert data["derived"]["base_hp_max"] == 12
    assert char.derived["hp_max"] == 12
