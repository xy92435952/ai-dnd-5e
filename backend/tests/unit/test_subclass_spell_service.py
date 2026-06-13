from services.subclass_spell_service import (
    available_spells_with_subclass_bonus,
    resolved_subclass_bonus_spell_details,
    subclass_bonus_spell_key,
)


class FakeSpellService:
    def get_all(self):
        return [
            {"name": "burning-hands-zh", "name_en": "Burning Hands", "level": 1},
            {"name": "command-zh", "name_en": "Command", "level": 1},
            {"name": "scorching-ray-zh", "name_en": "Scorching Ray", "level": 2},
        ]

    def get_for_class(self, cls):
        return [{"name": f"{cls}-spell", "name_en": f"{cls} Spell", "level": 1}]


def test_subclass_bonus_spell_key_accepts_player_facing_aliases():
    assert subclass_bonus_spell_key("Fiend") == "The Fiend"
    assert subclass_bonus_spell_key("The Fiend") == "The Fiend"


def test_resolved_subclass_bonus_spell_details_maps_name_en_to_registry_names():
    spells = resolved_subclass_bonus_spell_details(FakeSpellService(), "Fiend", level=1)

    assert spells == [
        {"name": "burning-hands-zh", "name_en": "Burning Hands", "level": 1},
        {"name": "command-zh", "name_en": "Command", "level": 1},
    ]


def test_available_spells_with_subclass_bonus_merges_class_and_bonus_spells():
    spells = available_spells_with_subclass_bonus(
        FakeSpellService(),
        "Warlock",
        "Fiend",
        level=3,
    )

    assert [spell["name"] for spell in spells] == [
        "Warlock-spell",
        "burning-hands-zh",
        "command-zh",
        "scorching-ray-zh",
    ]
