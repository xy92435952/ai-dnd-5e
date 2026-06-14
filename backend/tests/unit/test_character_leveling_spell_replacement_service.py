import pytest

from services import character_leveling_service
from services.dnd_rules import calc_derived


def _sorcerer_kwargs():
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 16}
    old_derived = calc_derived("Sorcerer", 4, ability_scores, "Wild Magic", race="Human")
    return {
        "char_class": "Sorcerer",
        "level": 4,
        "ability_scores": ability_scores,
        "derived": old_derived,
        "hp_current": old_derived["hp_max"],
        "spell_slots": {"1st": 4, "2nd": 2},
        "use_average_hp": True,
        "subclass": "Wild Magic",
        "race": "Human",
        "known_spells": ["Mage Armor", "Shield", "Magic Missile", "Scorching Ray", "Misty Step"],
        "cantrips": ["Fire Bolt", "Mage Hand", "Light", "Ray of Frost", "Message"],
        "available_class_spells": [
            {"name": "Mage Armor", "level": 1},
            {"name": "Shield", "level": 1},
            {"name": "Magic Missile", "level": 1},
            {"name": "Scorching Ray", "level": 2},
            {"name": "Misty Step", "level": 2},
            {"name": "Burning Hands", "level": 1},
            {"name": "Charm Person", "level": 1},
        ],
        "available_class_cantrips": ["Fire Bolt", "Mage Hand", "Light", "Ray of Frost", "Message"],
    }


def test_build_level_up_update_replaces_known_caster_spell():
    update = character_leveling_service.build_level_up_update(
        **_sorcerer_kwargs(),
        spell_replacements=[{"old_spell": "Mage Armor", "new_spell": "Burning Hands"}],
    )

    assert update["new_level"] == 5
    assert update["known_spells"] == ["Burning Hands", "Shield", "Magic Missile", "Scorching Ray", "Misty Step"]
    assert update["learned_spells"] == []
    assert update["spell_replacements"] == [{"old_spell": "Mage Armor", "new_spell": "Burning Hands"}]
    assert update["preparation_type"] == "known"


def test_build_level_up_update_allows_known_spell_gain_and_replacement_together():
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 16}
    old_derived = calc_derived("Sorcerer", 2, ability_scores, "Wild Magic", race="Human")

    update = character_leveling_service.build_level_up_update(
        char_class="Sorcerer",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={"1st": 3},
        use_average_hp=True,
        subclass="Wild Magic",
        race="Human",
        known_spells=["Mage Armor", "Shield", "Magic Missile"],
        cantrips=["Fire Bolt", "Mage Hand", "Light", "Ray of Frost"],
        learned_spells=["Scorching Ray"],
        spell_replacements=[{"old_spell": "Mage Armor", "new_spell": "Burning Hands"}],
        available_class_spells=[
            {"name": "Mage Armor", "level": 1},
            {"name": "Shield", "level": 1},
            {"name": "Magic Missile", "level": 1},
            {"name": "Burning Hands", "level": 1},
            {"name": "Scorching Ray", "level": 2},
        ],
        available_class_cantrips=["Fire Bolt", "Mage Hand", "Light", "Ray of Frost"],
    )

    assert update["new_level"] == 3
    assert update["known_spells"] == ["Burning Hands", "Shield", "Magic Missile", "Scorching Ray"]
    assert update["learned_spells"] == ["Scorching Ray"]
    assert update["spell_replacements"] == [{"old_spell": "Mage Armor", "new_spell": "Burning Hands"}]


def test_build_level_up_update_rejects_invalid_spell_replacements():
    with pytest.raises(character_leveling_service.CharacterLevelingError) as too_many:
        character_leveling_service.build_level_up_update(
            **_sorcerer_kwargs(),
            spell_replacements=[
                {"old_spell": "Mage Armor", "new_spell": "Burning Hands"},
                {"old_spell": "Shield", "new_spell": "Charm Person"},
            ],
    )
    assert too_many.value.status_code == 400
    assert "Only one known spell replacement" in too_many.value.detail

    with pytest.raises(character_leveling_service.CharacterLevelingError) as unknown_old:
        character_leveling_service.build_level_up_update(
            **_sorcerer_kwargs(),
            spell_replacements=[{"old_spell": "Sleep", "new_spell": "Burning Hands"}],
    )
    assert unknown_old.value.status_code == 400
    assert "is not currently known" in unknown_old.value.detail

    with pytest.raises(character_leveling_service.CharacterLevelingError) as duplicate_new:
        character_leveling_service.build_level_up_update(
            **_sorcerer_kwargs(),
            spell_replacements=[{"old_spell": "Mage Armor", "new_spell": "Shield"}],
        )
    assert duplicate_new.value.status_code == 400
    assert "already known" in duplicate_new.value.detail

    wizard_scores = {"str": 8, "dex": 14, "con": 14, "int": 16, "wis": 12, "cha": 10}
    wizard_derived = calc_derived("Wizard", 4, wizard_scores, "Evocation", race="Human")
    with pytest.raises(character_leveling_service.CharacterLevelingError) as not_known_caster:
        character_leveling_service.build_level_up_update(
            char_class="Wizard",
            level=4,
            ability_scores=wizard_scores,
            derived=wizard_derived,
            hp_current=wizard_derived["hp_max"],
            spell_slots={"1st": 4, "2nd": 3},
            use_average_hp=True,
            subclass="Evocation",
            race="Human",
            known_spells=["Mage Armor", "Shield"],
            cantrips=["Fire Bolt", "Mage Hand", "Light", "Ray of Frost"],
            spell_replacements=[{"old_spell": "Mage Armor", "new_spell": "Burning Hands"}],
            available_class_spells=[{"name": "Burning Hands", "level": 1}],
            available_class_cantrips=["Fire Bolt", "Mage Hand", "Light", "Ray of Frost"],
    )
    assert not_known_caster.value.status_code == 400
    assert "Wizard cannot replace known spells" in not_known_caster.value.detail
