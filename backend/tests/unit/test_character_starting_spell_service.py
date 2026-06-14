import pytest

from services.character_starting_spell_service import (
    CharacterStartingSpellError,
    validate_starting_spell_choices,
)


class FakeSpellService:
    def get_all(self):
        return [
            {"name": "burning-hands-zh", "name_en": "Burning Hands", "level": 1},
            {"name": "command-zh", "name_en": "Command", "level": 1},
            {"name": "scorching-ray-zh", "name_en": "Scorching Ray", "level": 2},
        ]

    def get_cantrips_for_class(self, cls):
        if cls == "Warlock":
            return [
                {"name": "eldritch-blast-zh", "level": 0},
                {"name": "chill-touch-zh", "level": 0},
            ]
        if cls == "Wizard":
            return [
                {"name": "fire-bolt-zh", "level": 0},
                {"name": "mage-hand-zh", "level": 0},
                {"name": "light-zh", "level": 0},
            ]
        return []

    def get_for_class(self, cls):
        if cls == "Warlock":
            return [
                {"name": "eldritch-blast-zh", "level": 0},
                {"name": "hex-zh", "level": 1},
                {"name": "armor-of-agathys-zh", "level": 1},
                {"name": "misty-step-zh", "level": 2},
            ]
        if cls == "Wizard":
            return [
                {"name": "fire-bolt-zh", "level": 0},
                {"name": "magic-missile-zh", "level": 1},
                {"name": "shield-zh", "level": 1},
                {"name": "mage-armor-zh", "level": 1},
                {"name": "detect-magic-zh", "level": 1},
                {"name": "sleep-zh", "level": 1},
                {"name": "burning-hands-zh", "level": 1},
                {"name": "fireball-zh", "level": 3},
            ]
        return []


def test_validates_starting_spells_with_subclass_expanded_list():
    result = validate_starting_spell_choices(
        spell_service=FakeSpellService(),
        char_class="Warlock",
        subclass="Fiend",
        level=1,
        derived={"spell_slots_max": {"1st": 1}},
        cantrips=["eldritch-blast-zh", "chill-touch-zh"],
        known_spells=["hex-zh", "command-zh"],
    )

    assert result == {
        "cantrips": ["eldritch-blast-zh", "chill-touch-zh"],
        "known_spells": ["hex-zh", "command-zh"],
    }


def test_rejects_duplicate_starting_cantrips():
    with pytest.raises(CharacterStartingSpellError) as exc:
        validate_starting_spell_choices(
            spell_service=FakeSpellService(),
            char_class="Warlock",
            subclass="Fiend",
            level=1,
            derived={"spell_slots_max": {"1st": 1}},
            cantrips=["eldritch-blast-zh", "eldritch-blast-zh"],
            known_spells=["hex-zh", "command-zh"],
        )

    assert exc.value.status_code == 400
    assert "Duplicate choices" in exc.value.detail


def test_rejects_starting_cantrip_outside_class_list():
    with pytest.raises(CharacterStartingSpellError) as exc:
        validate_starting_spell_choices(
            spell_service=FakeSpellService(),
            char_class="Warlock",
            subclass="Fiend",
            level=1,
            derived={"spell_slots_max": {"1st": 1}},
            cantrips=["eldritch-blast-zh", "fire-bolt-zh"],
            known_spells=["hex-zh", "command-zh"],
        )

    assert exc.value.status_code == 400
    assert "not a Warlock cantrip" in exc.value.detail


def test_rejects_starting_spell_above_current_spell_rank():
    with pytest.raises(CharacterStartingSpellError) as exc:
        validate_starting_spell_choices(
            spell_service=FakeSpellService(),
            char_class="Wizard",
            subclass=None,
            level=1,
            derived={"spell_slots_max": {"1st": 2}},
            cantrips=["fire-bolt-zh", "mage-hand-zh", "light-zh"],
            known_spells=[
                "magic-missile-zh",
                "shield-zh",
                "mage-armor-zh",
                "detect-magic-zh",
                "sleep-zh",
                "fireball-zh",
            ],
        )

    assert exc.value.status_code == 400
    assert "requires level 3" in exc.value.detail


def test_rejects_starting_spells_for_non_caster():
    with pytest.raises(CharacterStartingSpellError) as exc:
        validate_starting_spell_choices(
            spell_service=FakeSpellService(),
            char_class="Fighter",
            subclass=None,
            level=1,
            derived={"spell_slots_max": {}},
            cantrips=[],
            known_spells=["hex-zh"],
        )

    assert exc.value.status_code == 400
    assert "does not choose starting spells" in exc.value.detail
