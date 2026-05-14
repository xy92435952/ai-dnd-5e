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
