from services import character_leveling_service
from services.dnd_rules import calc_derived


def test_build_level_up_update_applies_asi_choices_and_recalculates_derived_stats():
    ability_scores = {"str": 16, "dex": 12, "con": 15, "int": 10, "wis": 10, "cha": 8}
    old_derived = calc_derived("Fighter", 3, ability_scores, "Champion", fighting_style="Defense", race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Fighter",
        level=3,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        use_average_hp=True,
        class_resources={"second_wind_used": False, "action_surge_used": False},
        subclass="Champion",
        fighting_style="Defense",
        race="Human",
        ability_score_increases={"str": 1, "con": 1},
    )

    assert update["new_level"] == 4
    assert update["is_asi_level"] is True
    assert update["ability_scores"]["str"] == 17
    assert update["ability_scores"]["con"] == 16
    assert update["derived"]["ability_modifiers"]["str"] == 3
    assert update["derived"]["ability_modifiers"]["con"] == 3
    assert update["derived"]["hp_max"] == 40
    assert update["hp_current"] == 36


def test_build_level_up_update_applies_feat_choice_and_recalculates_derived_stats():
    ability_scores = {"str": 16, "dex": 12, "con": 15, "int": 10, "wis": 10, "cha": 8}
    old_derived = calc_derived("Fighter", 3, ability_scores, "Champion", fighting_style="Defense", race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Fighter",
        level=3,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        use_average_hp=True,
        class_resources={"second_wind_used": False, "action_surge_used": False},
        subclass="Champion",
        fighting_style="Defense",
        race="Human",
        feat_choice={"name": "Tough"},
    )

    assert update["new_level"] == 4
    assert update["is_asi_level"] is True
    assert update["ability_scores"] == ability_scores
    assert len(update["feats"]) == 1
    assert update["feats"][0]["name"] == "Tough"
    assert update["derived"]["feat_effects"]["Tough"]["hp_per_level"] == 2
    assert update["derived"]["hp_max"] == 44
    assert update["hp_current"] == 36
