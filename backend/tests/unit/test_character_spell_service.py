import pytest

from services.character_spell_service import CharacterSpellError, build_prepared_spells_update


def test_spellbook_caster_prepares_known_spells_under_limit():
    result = build_prepared_spells_update(
        char_class="Wizard",
        known_spells=["magic-missile", "shield"],
        requested_spells=["magic-missile"],
        level=1,
        derived={
            "spell_ability": "int",
            "ability_modifiers": {"int": 3},
        },
    )

    assert result == {
        "prepared_spells": ["magic-missile"],
        "max_prepared": 4,
        "preparation_type": "spellbook",
    }


def test_spellbook_caster_rejects_spells_outside_spellbook():
    with pytest.raises(CharacterSpellError) as exc:
        build_prepared_spells_update(
            char_class="Wizard",
            known_spells=["magic-missile"],
            requested_spells=["shield"],
            level=1,
            derived={},
        )

    assert exc.value.status_code == 400
    assert "known spell list" in exc.value.detail


def test_prepared_caster_can_prepare_from_class_spell_list():
    result = build_prepared_spells_update(
        char_class="Cleric",
        known_spells=[],
        requested_spells=["Bless"],
        available_class_spells=["Bless", "Cure Wounds"],
        level=1,
        derived={
            "spell_ability": "wis",
            "ability_modifiers": {"wis": 3},
        },
    )

    assert result == {
        "prepared_spells": ["Bless"],
        "max_prepared": 4,
        "preparation_type": "prepared",
    }


def test_prepared_caster_rejects_spells_outside_class_spell_list():
    with pytest.raises(CharacterSpellError) as exc:
        build_prepared_spells_update(
            char_class="Cleric",
            known_spells=[],
            requested_spells=["Magic Missile"],
            available_class_spells=["Bless", "Cure Wounds"],
            level=1,
            derived={
                "spell_ability": "wis",
                "ability_modifiers": {"wis": 3},
            },
        )

    assert exc.value.status_code == 400
    assert "class spell list" in exc.value.detail


def test_half_prepared_caster_uses_half_level_for_prepared_limit():
    result = build_prepared_spells_update(
        char_class="Paladin",
        known_spells=[],
        requested_spells=["Bless", "Cure Wounds"],
        available_class_spells=["Bless", "Cure Wounds", "Command"],
        level=5,
        derived={
            "spell_ability": "cha",
            "ability_modifiers": {"cha": 2},
        },
    )

    assert result["max_prepared"] == 4
    assert result["prepared_spells"] == ["Bless", "Cure Wounds"]


def test_prepared_update_rejects_too_many_spells():
    with pytest.raises(CharacterSpellError) as exc:
        build_prepared_spells_update(
            char_class="Cleric",
            known_spells=[],
            requested_spells=["a", "b", "c"],
            available_class_spells=["a", "b", "c"],
            level=1,
            derived={
                "spell_ability": "wis",
                "ability_modifiers": {"wis": 1},
            },
        )

    assert exc.value.status_code == 400
    assert "Prepared spell limit is 2" in exc.value.detail


def test_known_spell_caster_cannot_prepare_a_daily_subset():
    with pytest.raises(CharacterSpellError) as exc:
        build_prepared_spells_update(
            char_class="Sorcerer",
            known_spells=["burning-hands", "shield"],
            requested_spells=["shield"],
            level=1,
            derived={
                "spell_ability": "cha",
                "ability_modifiers": {"cha": 3},
            },
        )

    assert exc.value.status_code == 400
    assert "Known-spell casters" in exc.value.detail


def test_known_spell_caster_accepts_all_known_spells_as_always_prepared():
    result = build_prepared_spells_update(
        char_class="Sorcerer",
        known_spells=["burning-hands", "shield"],
        requested_spells=["shield", "burning-hands"],
        level=1,
        derived={
            "spell_ability": "cha",
            "ability_modifiers": {"cha": 3},
        },
    )

    assert result == {
        "prepared_spells": ["burning-hands", "shield"],
        "max_prepared": 2,
        "preparation_type": "known",
    }
