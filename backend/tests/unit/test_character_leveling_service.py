import pytest

from services.dnd_rules import calc_derived, get_cantrips_count
from services import character_leveling_service
from services.spell_service import spell_service


BASE_SCORES = {"str": 16, "dex": 14, "con": 14, "int": 12, "wis": 12, "cha": 14}


def _advance_character_levels(
    *,
    char_class,
    target_level,
    subclass_choice=None,
    fighting_style_choice=None,
    initial_fighting_style=None,
):
    level = 1
    subclass = None
    fighting_style = initial_fighting_style
    derived = calc_derived(
        char_class,
        level,
        BASE_SCORES,
        subclass,
        fighting_style=fighting_style,
        race="Human",
    )
    hp_current = derived["hp_max"]
    spell_slots = dict(derived.get("spell_slots_max", {}))
    class_resources = {}

    while level < target_level:
        payload = {
            "char_class": char_class,
            "level": level,
            "ability_scores": BASE_SCORES,
            "derived": derived,
            "hp_current": hp_current,
            "spell_slots": spell_slots,
            "use_average_hp": True,
            "subclass": subclass,
            "fighting_style": fighting_style,
            "class_resources": class_resources,
            "race": "Human",
        }
        if subclass_choice and level + 1 == target_level:
            payload["subclass_choice"] = subclass_choice
        if fighting_style_choice and not fighting_style:
            payload["fighting_style_choice"] = fighting_style_choice

        update = character_leveling_service.build_level_up_update(**payload)
        level = update["new_level"]
        subclass = update["subclass"]
        fighting_style = update["fighting_style"]
        derived = update["derived"]
        hp_current = update["hp_current"]
        spell_slots = update["spell_slots"]
        class_resources = update["class_resources"]

    return update


def _progression_count(table, level):
    count = 0
    for threshold, value in sorted(table.items()):
        if level >= threshold:
            count = value
    return count


def _max_spell_rank(spell_slots_max):
    slot_levels = {
        "1st": 1,
        "2nd": 2,
        "3rd": 3,
        "4th": 4,
        "5th": 5,
        "6th": 6,
        "7th": 7,
        "8th": 8,
        "9th": 9,
    }
    return max(
        [
            slot_levels.get(slot_key, 0)
            for slot_key, count in (spell_slots_max or {}).items()
            if int(count or 0) > 0
        ]
        or [0]
    )


def _class_spell_details(char_class):
    return [
        {"name": spell["name"], "level": spell.get("level", 0)}
        for spell in spell_service.get_for_class(char_class)
        if spell.get("level", 0) > 0
    ]


def _legal_spell_names(char_class, max_level):
    return [
        spell["name"]
        for spell in _class_spell_details(char_class)
        if spell.get("level", 0) <= max_level
    ]


def _class_cantrip_names(char_class):
    return [
        spell["name"]
        for spell in spell_service.get_for_class(char_class)
        if spell.get("level", 0) == 0
    ]


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


def test_build_level_up_update_advances_class_resources_without_restoring_spent_uses():
    ability_scores = {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8}
    old_derived = calc_derived("Fighter", 1, ability_scores, None, race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Fighter",
        level=1,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        use_average_hp=True,
        class_resources={"second_wind_used": True},
        race="Human",
    )

    assert update["new_level"] == 2
    assert update["class_resources"]["second_wind_used"] is True
    assert update["class_resources"]["action_surge_used"] is False


def test_build_level_up_update_adds_only_new_barbarian_rage_uses():
    ability_scores = {"str": 16, "dex": 12, "con": 14, "int": 8, "wis": 10, "cha": 10}
    old_derived = calc_derived("Barbarian", 2, ability_scores, None, race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Barbarian",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        use_average_hp=True,
        class_resources={"rage_remaining": 0, "raging": False},
        subclass_choice="Berserker",
        race="Human",
    )

    assert update["new_level"] == 3
    assert update["class_resources"]["rage_remaining"] == 1
    assert update["class_resources"]["raging"] is False


def test_build_level_up_update_backfills_missing_resource_from_old_level_defaults():
    ability_scores = {"str": 16, "dex": 12, "con": 14, "int": 8, "wis": 10, "cha": 10}
    old_derived = calc_derived("Barbarian", 2, ability_scores, None, race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Barbarian",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        use_average_hp=True,
        class_resources={},
        subclass_choice="Berserker",
        race="Human",
    )

    assert update["class_resources"]["rage_remaining"] == 3
    assert update["class_resources"]["raging"] is False


def test_build_level_up_update_expands_battle_master_superiority_dice_capacity():
    ability_scores = {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8}
    old_derived = calc_derived(
        "Fighter",
        6,
        ability_scores,
        "Battle Master",
        race="Human",
    )

    update = character_leveling_service.build_level_up_update(
        char_class="Fighter",
        level=6,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        use_average_hp=True,
        subclass="Battle Master",
        class_resources={
            "second_wind_used": True,
            "action_surge_used": True,
            "superiority_dice_remaining": 1,
        },
        race="Human",
    )

    assert update["new_level"] == 7
    assert update["class_resources"]["superiority_dice_remaining"] == 2
    assert update["class_resources"]["second_wind_used"] is True
    assert update["class_resources"]["action_surge_used"] is True


def test_build_level_up_update_applies_battle_master_subclass_and_maneuvers():
    ability_scores = {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8}
    old_derived = calc_derived("Fighter", 2, ability_scores, None, race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Fighter",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        use_average_hp=True,
        subclass_choice="Battle Master",
        maneuver_choices=["precision", "trip", "disarm"],
        class_resources={"second_wind_used": True, "action_surge_used": True},
        race="Human",
    )

    assert update["new_level"] == 3
    assert update["subclass"] == "Battle Master"
    assert update["derived"]["subclass_effects"]["battle_master"] is True
    assert update["class_resources"]["superiority_dice_remaining"] == 4
    assert update["class_resources"]["maneuvers_known"] == ["precision", "trip", "disarm"]
    assert update["maneuver_choices"] == ["precision", "trip", "disarm"]
    assert update["class_resources"]["second_wind_used"] is True
    assert update["class_resources"]["action_surge_used"] is True


def test_build_level_up_update_applies_fighting_style_choice_at_unlock():
    ability_scores = {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 14}
    old_derived = calc_derived("Paladin", 1, ability_scores, None, race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Paladin",
        level=1,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        use_average_hp=True,
        fighting_style_choice="Defense",
        race="Human",
    )

    assert update["new_level"] == 2
    assert update["fighting_style"] == "Defense"


@pytest.mark.parametrize(
    ("char_class", "target_level", "subclass_choice", "fighting_style_choice", "initial_style"),
    [
        ("Barbarian", 3, "Berserker", None, None),
        ("Bard", 3, "Lore", None, None),
        ("Druid", 2, "Moon", None, None),
        ("Fighter", 3, "Champion", None, "Defense"),
        ("Monk", 3, "Open Hand", None, None),
        ("Paladin", 3, "Devotion", "Defense", None),
        ("Ranger", 3, "Hunter", "Archery", None),
        ("Rogue", 3, "Thief", None, None),
        ("Wizard", 2, "Evocation", None, None),
    ],
)
def test_supported_classes_progress_through_subclass_unlock_with_required_choices(
    char_class,
    target_level,
    subclass_choice,
    fighting_style_choice,
    initial_style,
):
    update = _advance_character_levels(
        char_class=char_class,
        target_level=target_level,
        subclass_choice=subclass_choice,
        fighting_style_choice=fighting_style_choice,
        initial_fighting_style=initial_style,
    )

    assert update["new_level"] == target_level
    assert update["subclass"] == subclass_choice
    if fighting_style_choice:
        assert update["fighting_style"] == fighting_style_choice
    if initial_style:
        assert update["fighting_style"] == initial_style


def test_build_level_up_update_adds_tracked_battle_master_maneuvers_at_later_threshold():
    ability_scores = {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8}
    old_derived = calc_derived(
        "Fighter",
        6,
        ability_scores,
        "Battle Master",
        race="Human",
    )

    update = character_leveling_service.build_level_up_update(
        char_class="Fighter",
        level=6,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        use_average_hp=True,
        subclass="Battle Master",
        class_resources={
            "superiority_dice_remaining": 1,
            "maneuvers_known": ["precision", "trip", "disarm"],
        },
        maneuver_choices=["riposte", "menacing"],
        race="Human",
    )

    assert update["new_level"] == 7
    assert update["class_resources"]["maneuvers_known"] == [
        "precision",
        "trip",
        "disarm",
        "riposte",
        "menacing",
    ]
    assert update["maneuver_choices"] == ["riposte", "menacing"]
    assert update["class_resources"]["superiority_dice_remaining"] == 2


def test_build_level_up_update_rejects_subclass_choice_before_unlock():
    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Fighter",
            level=1,
            ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8},
            derived={"hp_max": 20, "spell_slots_max": {}},
            hp_current=20,
            spell_slots={},
            use_average_hp=True,
            subclass_choice="Champion",
        )

    assert exc.value.status_code == 400
    assert "unlock at level 3" in exc.value.detail


def test_build_level_up_update_requires_subclass_choice_at_unlock():
    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Fighter",
            level=2,
            ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8},
            derived={"hp_max": 22, "spell_slots_max": {}},
            hp_current=22,
            spell_slots={},
            use_average_hp=True,
        )

    assert exc.value.status_code == 400
    assert "must choose a subclass" in exc.value.detail


def test_build_level_up_update_requires_fighting_style_choice_at_unlock():
    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Paladin",
            level=1,
            ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 14},
            derived={"hp_max": 12, "spell_slots_max": {}},
            hp_current=12,
            spell_slots={},
            use_average_hp=True,
        )

    assert exc.value.status_code == 400
    assert "must choose a fighting style" in exc.value.detail


def test_build_level_up_update_requires_battle_master_maneuvers_at_unlock():
    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Fighter",
            level=2,
            ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8},
            derived={"hp_max": 22, "spell_slots_max": {}},
            hp_current=22,
            spell_slots={},
            use_average_hp=True,
            subclass_choice="Battle Master",
        )

    assert exc.value.status_code == 400
    assert "must choose 3 new maneuver" in exc.value.detail


def test_build_level_up_update_requires_battle_master_maneuver_deficit_when_tracked():
    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Fighter",
            level=6,
            ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8},
            derived={"hp_max": 58, "spell_slots_max": {}},
            hp_current=58,
            spell_slots={},
            use_average_hp=True,
            subclass="Battle Master",
            class_resources={
                "superiority_dice_remaining": 1,
                "maneuvers_known": ["precision", "trip", "disarm"],
            },
        )

    assert exc.value.status_code == 400
    assert "must choose 2 new maneuver" in exc.value.detail


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


def test_build_level_up_update_canonicalizes_feat_choice_effects():
    ability_scores = {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8}
    old_derived = calc_derived(
        "Fighter",
        3,
        ability_scores,
        "Champion",
        fighting_style="Defense",
        race="Human",
    )

    update = character_leveling_service.build_level_up_update(
        char_class="Fighter",
        level=3,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        use_average_hp=True,
        subclass="Champion",
        fighting_style="Defense",
        feat_choice={
            "name": "Tough",
            "desc": "client supplied text",
            "effects": {"hp_per_level": 99, "no_surprise": True},
        },
        race="Human",
    )

    feat = update["feats"][0]
    assert feat["name"] == "Tough"
    assert feat["effects"] == {"hp_per_level": 2}
    assert "no_surprise" not in feat["effects"]
    assert update["derived"]["feat_effects"]["Tough"] == {"hp_per_level": 2}


def test_build_level_up_update_rejects_duplicate_feat_choice():
    ability_scores = {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8}
    old_derived = calc_derived(
        "Fighter",
        3,
        ability_scores,
        "Champion",
        fighting_style="Defense",
        feats=[{"name": "Alert"}],
        race="Human",
    )

    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Fighter",
            level=3,
            ability_scores=ability_scores,
            derived=old_derived,
            hp_current=old_derived["hp_max"],
            spell_slots={},
            use_average_hp=True,
            subclass="Champion",
            fighting_style="Defense",
            feats=[{"name": "Alert", "effects": {"initiative_bonus": 99}}],
            feat_choice={"name": "Alert"},
            race="Human",
        )

    assert exc.value.status_code == 400
    assert "Duplicate feat choice: Alert" in exc.value.detail


def test_build_level_up_update_enforces_war_caster_spellcasting_prerequisite():
    ability_scores = {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8}
    old_derived = calc_derived(
        "Fighter",
        3,
        ability_scores,
        "Champion",
        fighting_style="Defense",
        race="Human",
    )

    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Fighter",
            level=3,
            ability_scores=ability_scores,
            derived=old_derived,
            hp_current=old_derived["hp_max"],
            spell_slots={},
            use_average_hp=True,
            subclass="Champion",
            fighting_style="Defense",
            feat_choice={"name": "War Caster"},
            race="Human",
        )

    assert exc.value.status_code == 400
    assert "War Caster requires" in exc.value.detail


def test_build_level_up_update_allows_war_caster_for_spellcaster():
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 16, "wis": 12, "cha": 10}
    old_derived = calc_derived("Wizard", 3, ability_scores, None, race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Wizard",
        level=3,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots=dict(old_derived.get("spell_slots_max", {})),
        use_average_hp=True,
        known_spells=["Magic Missile"],
        cantrips=["Fire Bolt"],
        feat_choice={"name": "War Caster", "effects": {"concentration_advantage": False}},
        race="Human",
    )

    feat = update["feats"][0]
    assert feat["name"] == "War Caster"
    assert feat["prereq"] == "Spellcasting"
    assert feat["effects"] == {"concentration_advantage": True}
    assert update["derived"]["feat_effects"]["War Caster"] == {"concentration_advantage": True}


def test_build_level_up_update_adds_requested_wizard_spellbook_spells():
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 16, "wis": 12, "cha": 10}
    old_derived = calc_derived("Wizard", 2, ability_scores, None, race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Wizard",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={"1st": 1},
        use_average_hp=True,
        known_spells=["Magic Missile"],
        cantrips=["Fire Bolt", "Mage Hand", "Light"],
        learned_spells=["Shield", "Shatter"],
        available_class_spells=[
            {"name": "Magic Missile", "level": 1},
            {"name": "Shield", "level": 1},
            {"name": "Shatter", "level": 2},
            {"name": "Fireball", "level": 3},
        ],
        available_class_cantrips=["Fire Bolt", "Mage Hand", "Light", "Ray of Frost"],
        race="Human",
    )

    assert update["new_level"] == 3
    assert update["known_spells"] == ["Magic Missile", "Shield", "Shatter"]
    assert update["learned_spells"] == ["Shield", "Shatter"]
    assert update["cantrips"] == ["Fire Bolt", "Mage Hand", "Light"]
    assert update["preparation_type"] == "spellbook"


def test_build_level_up_update_rejects_spells_above_next_level_slots():
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 16, "wis": 12, "cha": 10}
    old_derived = calc_derived("Wizard", 2, ability_scores, None, race="Human")

    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Wizard",
            level=2,
            ability_scores=ability_scores,
            derived=old_derived,
            hp_current=old_derived["hp_max"],
            spell_slots={"1st": 1},
            use_average_hp=True,
            known_spells=["Magic Missile"],
            cantrips=["Fire Bolt", "Mage Hand", "Light"],
            learned_spells=["Fireball"],
            available_class_spells=[
                {"name": "Magic Missile", "level": 1},
                {"name": "Fireball", "level": 3},
            ],
            available_class_cantrips=["Fire Bolt", "Mage Hand", "Light"],
            race="Human",
        )

    assert exc.value.status_code == 400
    assert "max allowed is 2" in exc.value.detail


def test_build_level_up_update_adds_cantrip_when_threshold_increases():
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 16, "wis": 12, "cha": 10}
    old_derived = calc_derived("Wizard", 3, ability_scores, None, race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Wizard",
        level=3,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={"1st": 1, "2nd": 1},
        use_average_hp=True,
        known_spells=["Magic Missile"],
        cantrips=["Fire Bolt", "Mage Hand", "Light"],
        learned_cantrips=["Ray of Frost"],
        available_class_spells=[{"name": "Shield", "level": 1}],
        available_class_cantrips=["Fire Bolt", "Mage Hand", "Light", "Ray of Frost"],
        race="Human",
    )

    assert update["new_level"] == 4
    assert update["cantrips"] == ["Fire Bolt", "Mage Hand", "Light", "Ray of Frost"]
    assert update["learned_cantrips"] == ["Ray of Frost"]


def test_build_level_up_update_rejects_prepared_caster_leveled_spell_learning():
    ability_scores = {"str": 10, "dex": 12, "con": 14, "int": 10, "wis": 16, "cha": 10}
    old_derived = calc_derived("Cleric", 2, ability_scores, None, race="Human")

    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Cleric",
            level=2,
            ability_scores=ability_scores,
            derived=old_derived,
            hp_current=old_derived["hp_max"],
            spell_slots={"1st": 1},
            use_average_hp=True,
            known_spells=[],
            cantrips=["Sacred Flame", "Guidance", "Light"],
            learned_spells=["Bless"],
            available_class_spells=[{"name": "Bless", "level": 1}],
            available_class_cantrips=["Sacred Flame", "Guidance", "Light"],
            race="Human",
        )

    assert exc.value.status_code == 400
    assert "can learn 0 leveled spell" in exc.value.detail


def test_build_level_up_update_uses_known_caster_progression_capacity():
    ability_scores = {"str": 8, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 16}
    old_derived = calc_derived("Warlock", 9, ability_scores, None, race="Human")

    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Warlock",
            level=9,
            ability_scores=ability_scores,
            derived=old_derived,
            hp_current=old_derived["hp_max"],
            spell_slots={"5th": 1},
            use_average_hp=True,
            known_spells=["Hellish Rebuke"],
            cantrips=["Eldritch Blast"],
            learned_spells=["Hex"],
            available_class_spells=[
                {"name": "Hellish Rebuke", "level": 1},
                {"name": "Hex", "level": 1},
            ],
            available_class_cantrips=["Eldritch Blast"],
            race="Human",
        )

    assert "can learn 0 leveled spell" in exc.value.detail

    update = character_leveling_service.build_level_up_update(
        char_class="Warlock",
        level=10,
        ability_scores=ability_scores,
        derived=calc_derived("Warlock", 10, ability_scores, None, race="Human"),
        hp_current=old_derived["hp_max"],
        spell_slots={"5th": 1},
        use_average_hp=True,
        known_spells=["Hellish Rebuke"],
        cantrips=["Eldritch Blast"],
        learned_spells=["Hex"],
        available_class_spells=[
            {"name": "Hellish Rebuke", "level": 1},
            {"name": "Hex", "level": 1},
        ],
        available_class_cantrips=["Eldritch Blast"],
        race="Human",
    )

    assert update["new_level"] == 11
    assert update["known_spells"] == ["Hellish Rebuke", "Hex"]


@pytest.mark.parametrize(
    "char_class,old_level",
    [
        ("Bard", 9),
        ("Ranger", 8),
        ("Sorcerer", 9),
        ("Warlock", 12),
    ],
)
def test_known_casters_follow_higher_level_spell_learning_progression_with_real_spell_lists(
    char_class,
    old_level,
):
    ability_scores = {"str": 10, "dex": 14, "con": 14, "int": 10, "wis": 16, "cha": 16}
    old_derived = calc_derived(char_class, old_level, ability_scores, None, race="Human")
    new_derived = calc_derived(char_class, old_level + 1, ability_scores, None, race="Human")
    old_known_count = _progression_count(
        character_leveling_service.SPELLS_KNOWN[char_class],
        old_level,
    )
    new_known_count = _progression_count(
        character_leveling_service.SPELLS_KNOWN[char_class],
        old_level + 1,
    )
    learn_count = new_known_count - old_known_count
    old_cantrip_count = get_cantrips_count(char_class, old_level)
    new_cantrip_count = get_cantrips_count(char_class, old_level + 1)
    cantrip_gain = new_cantrip_count - old_cantrip_count
    legal_spells = _legal_spell_names(
        char_class,
        _max_spell_rank(new_derived.get("spell_slots_max", {})),
    )
    cantrip_names = _class_cantrip_names(char_class)
    known_spells = legal_spells[:old_known_count]
    learned_spells = legal_spells[old_known_count:old_known_count + learn_count]
    cantrips = cantrip_names[:old_cantrip_count]
    learned_cantrips = cantrip_names[old_cantrip_count:old_cantrip_count + cantrip_gain]

    update = character_leveling_service.build_level_up_update(
        char_class=char_class,
        level=old_level,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots=dict(old_derived.get("spell_slots_max", {})),
        use_average_hp=True,
        known_spells=known_spells,
        cantrips=cantrips,
        learned_spells=learned_spells,
        learned_cantrips=learned_cantrips,
        available_class_spells=_class_spell_details(char_class),
        available_class_cantrips=cantrip_names,
        race="Human",
    )

    assert learn_count > 0
    assert update["new_level"] == old_level + 1
    assert update["known_spells"] == [*known_spells, *learned_spells]
    assert update["learned_spells"] == learned_spells
    assert len(update["known_spells"]) == new_known_count
    if cantrip_gain:
        assert update["cantrips"] == [*cantrips, *learned_cantrips]
        assert update["learned_cantrips"] == learned_cantrips


def test_wizard_higher_level_spellbook_and_cantrip_progression_uses_real_options():
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 18, "wis": 12, "cha": 10}
    old_level = 9
    old_derived = calc_derived("Wizard", old_level, ability_scores, None, race="Human")
    new_derived = calc_derived("Wizard", old_level + 1, ability_scores, None, race="Human")
    legal_spells = _legal_spell_names(
        "Wizard",
        _max_spell_rank(new_derived.get("spell_slots_max", {})),
    )
    cantrip_names = _class_cantrip_names("Wizard")
    old_cantrip_count = get_cantrips_count("Wizard", old_level)
    new_cantrip_count = get_cantrips_count("Wizard", old_level + 1)
    known_spells = legal_spells[:8]
    learned_spells = legal_spells[8:10]
    cantrips = cantrip_names[:old_cantrip_count]
    learned_cantrips = cantrip_names[old_cantrip_count:new_cantrip_count]

    update = character_leveling_service.build_level_up_update(
        char_class="Wizard",
        level=old_level,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots=dict(old_derived.get("spell_slots_max", {})),
        use_average_hp=True,
        known_spells=known_spells,
        cantrips=cantrips,
        learned_spells=learned_spells,
        learned_cantrips=learned_cantrips,
        available_class_spells=_class_spell_details("Wizard"),
        available_class_cantrips=cantrip_names,
        race="Human",
    )

    assert update["new_level"] == 10
    assert update["known_spells"] == [*known_spells, *learned_spells]
    assert update["learned_spells"] == learned_spells
    assert update["cantrips"] == [*cantrips, *learned_cantrips]
    assert update["learned_cantrips"] == learned_cantrips
    assert update["preparation_type"] == "spellbook"


def test_build_level_up_update_replaces_known_caster_spell():
    ability_scores = {"str": 8, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 16}
    old_derived = calc_derived("Sorcerer", 2, ability_scores, None, race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Sorcerer",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={"1st": 1},
        use_average_hp=True,
        known_spells=["Burning Hands", "Shield"],
        cantrips=["Fire Bolt"],
        spell_replacements=[{"old_spell": "Burning Hands", "new_spell": "Mage Armor"}],
        available_class_spells=[
            {"name": "Burning Hands", "level": 1},
            {"name": "Shield", "level": 1},
            {"name": "Mage Armor", "level": 1},
        ],
        available_class_cantrips=["Fire Bolt"],
        race="Human",
    )

    assert update["new_level"] == 3
    assert update["known_spells"] == ["Mage Armor", "Shield"]
    assert update["spell_replacements"] == [
        {"old_spell": "Burning Hands", "new_spell": "Mage Armor"}
    ]


def test_build_level_up_update_allows_known_spell_gain_and_replacement_together():
    ability_scores = {"str": 8, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 16}
    old_derived = calc_derived("Sorcerer", 2, ability_scores, None, race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Sorcerer",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={"1st": 1},
        use_average_hp=True,
        known_spells=["Burning Hands", "Shield", "Mage Armor"],
        cantrips=["Fire Bolt"],
        learned_spells=["Shatter"],
        spell_replacements=[{"old_spell": "Burning Hands", "new_spell": "Magic Missile"}],
        available_class_spells=[
            {"name": "Burning Hands", "level": 1},
            {"name": "Shield", "level": 1},
            {"name": "Mage Armor", "level": 1},
            {"name": "Magic Missile", "level": 1},
            {"name": "Shatter", "level": 2},
        ],
        available_class_cantrips=["Fire Bolt"],
        race="Human",
    )

    assert update["known_spells"] == ["Magic Missile", "Shield", "Mage Armor", "Shatter"]
    assert update["learned_spells"] == ["Shatter"]


def test_build_level_up_update_rejects_invalid_spell_replacements():
    ability_scores = {"str": 10, "dex": 12, "con": 14, "int": 10, "wis": 16, "cha": 10}
    old_derived = calc_derived("Cleric", 2, ability_scores, None, race="Human")

    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Cleric",
            level=2,
            ability_scores=ability_scores,
            derived=old_derived,
            hp_current=old_derived["hp_max"],
            spell_slots={"1st": 1},
            use_average_hp=True,
            known_spells=["Bless"],
            cantrips=["Sacred Flame"],
            spell_replacements=[{"old_spell": "Bless", "new_spell": "Cure Wounds"}],
            available_class_spells=[
                {"name": "Bless", "level": 1},
                {"name": "Cure Wounds", "level": 1},
            ],
            available_class_cantrips=["Sacred Flame"],
            race="Human",
        )

    assert exc.value.status_code == 400
    assert "cannot replace known spells" in exc.value.detail

    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Sorcerer",
            level=2,
            ability_scores={"str": 8, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 16},
            derived=calc_derived("Sorcerer", 2, {"str": 8, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 16}, None, race="Human"),
            hp_current=14,
            spell_slots={"1st": 1},
            use_average_hp=True,
            known_spells=["Shield"],
            cantrips=["Fire Bolt"],
            spell_replacements=[{"old_spell": "Burning Hands", "new_spell": "Mage Armor"}],
            available_class_spells=[
                {"name": "Burning Hands", "level": 1},
                {"name": "Shield", "level": 1},
                {"name": "Mage Armor", "level": 1},
            ],
            available_class_cantrips=["Fire Bolt"],
            race="Human",
        )

    assert "not currently known" in exc.value.detail

    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Sorcerer",
            level=2,
            ability_scores={"str": 8, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 16},
            derived=calc_derived("Sorcerer", 2, {"str": 8, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 16}, None, race="Human"),
            hp_current=14,
            spell_slots={"1st": 1},
            use_average_hp=True,
            known_spells=["Burning Hands", "Shield"],
            cantrips=["Fire Bolt"],
            spell_replacements=[{"old_spell": "Burning Hands", "new_spell": "Shield"}],
            available_class_spells=[
                {"name": "Burning Hands", "level": 1},
                {"name": "Shield", "level": 1},
            ],
            available_class_cantrips=["Fire Bolt"],
            race="Human",
        )

    assert "already known" in exc.value.detail

    sorcerer_scores = {"str": 8, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 16}
    sorcerer_derived = calc_derived("Sorcerer", 2, sorcerer_scores, None, race="Human")
    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Sorcerer",
            level=2,
            ability_scores=sorcerer_scores,
            derived=sorcerer_derived,
            hp_current=14,
            spell_slots={"1st": 1},
            use_average_hp=True,
            known_spells=["Burning Hands", "Shield", "Mage Armor"],
            cantrips=["Fire Bolt"],
            learned_spells=["Burning Hands"],
            spell_replacements=[{"old_spell": "Burning Hands", "new_spell": "Magic Missile"}],
            available_class_spells=[
                {"name": "Burning Hands", "level": 1},
                {"name": "Shield", "level": 1},
                {"name": "Mage Armor", "level": 1},
                {"name": "Magic Missile", "level": 1},
            ],
            available_class_cantrips=["Fire Bolt"],
            race="Human",
        )

    assert "cannot also be learned again" in exc.value.detail

    with pytest.raises(character_leveling_service.CharacterLevelingError) as exc:
        character_leveling_service.build_level_up_update(
            char_class="Sorcerer",
            level=2,
            ability_scores=sorcerer_scores,
            derived=sorcerer_derived,
            hp_current=14,
            spell_slots={"1st": 1},
            use_average_hp=True,
            known_spells=["Burning Hands", "Shield", "Mage Armor"],
            cantrips=["Fire Bolt"],
            learned_spells=["Magic Missile"],
            spell_replacements=[{"old_spell": "Burning Hands", "new_spell": "Magic Missile"}],
            available_class_spells=[
                {"name": "Burning Hands", "level": 1},
                {"name": "Shield", "level": 1},
                {"name": "Mage Armor", "level": 1},
                {"name": "Magic Missile", "level": 1},
            ],
            available_class_cantrips=["Fire Bolt"],
            race="Human",
        )

    assert "cannot also be selected as learned spells" in exc.value.detail
