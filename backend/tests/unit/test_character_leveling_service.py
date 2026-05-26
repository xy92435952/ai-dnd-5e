import pytest

from services.dnd_rules import calc_derived
from services import character_leveling_service


def test_build_level_up_update_adds_new_spell_slots_without_refilling_spent_slots():
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 16, "wis": 12, "cha": 10}
    old_derived = calc_derived("Wizard", 2, ability_scores, None, race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Wizard",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={"1st": 0},
        use_average_hp=True,
        race="Human",
        proficient_skills=["奥秘", "调查"],
    )

    assert update["new_level"] == 3
    assert update["spell_slots"]["1st"] == 1
    assert update["spell_slots"]["2nd"] == 2


def test_build_level_up_update_rejects_levels_above_twenty():
    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Fighter",
            level=20,
            ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8},
            derived={"hp_max": 180, "spell_slots_max": {}},
            hp_current=180,
            spell_slots={},
            use_average_hp=True,
        )

    assert exc.value.status_code == 400
    assert "最高等级20" in exc.value.detail


def test_build_level_up_update_caps_current_hp_at_exhaustion_max():
    update = character_leveling_service.build_level_up_update(
        char_class="Fighter",
        level=1,
        ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8},
        derived={"hp_max": 12, "spell_slots_max": {}},
        hp_current=12,
        spell_slots={},
        use_average_hp=True,
        condition_durations={"exhaustion_level": 4},
    )

    assert update["derived"]["hp_max"] > update["hp_current"]
    assert update["hp_current"] == update["derived"]["hp_max"] // 2


def test_build_level_up_update_validates_asi_total_increase():
    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Fighter",
            level=3,
            ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8},
            derived={"hp_max": 30, "spell_slots_max": {}},
            hp_current=30,
            spell_slots={},
            use_average_hp=True,
            ability_score_increases={"str": 2, "con": 1},
        )

    assert exc.value.status_code == 400
    assert "最多增加2点" in exc.value.detail
