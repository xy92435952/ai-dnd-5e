from services.character_options_service import (
    build_background_equipment_options,
    build_character_options,
    build_starting_gear_pack_options,
)


class FakeSpellService:
    def get_all(self):
        return [
            {"name": "burning-hands-zh", "name_en": "Burning Hands", "level": 1},
            {"name": "command-zh", "name_en": "Command", "level": 1},
        ]

    def get_cantrips_for_class(self, cls):
        return [{"name": f"{cls}-cantrip"}]

    def get_for_class(self, cls):
        return [{"name": f"{cls}-cantrip", "level": 0}, {"name": f"{cls}-spell", "level": 1}]


def test_build_character_options_includes_spell_metadata_for_spellcasters():
    options = build_character_options(FakeSpellService())

    assert "Wizard" in options["spellcaster_classes"]
    assert options["class_cantrips"]["Wizard"] == ["Wizard-cantrip"]
    assert options["class_spells"]["Wizard"] == ["Wizard-spell"]
    assert options["class_spell_details"]["Wizard"] == [{"name": "Wizard-spell", "level": 1}]
    assert options["magic_initiate_spell_options"]["Wizard"] == {
        "cantrips": [{"name": "Wizard-cantrip", "name_en": None}],
        "spells": [{"name": "Wizard-spell", "name_en": None}],
    }
    assert options["starting_cantrips_count"]["Wizard"] >= 0
    assert options["races"]
    assert options["class_skill_choices"]
    assert options["feats"]
    assert options["subclass_unlock_levels"]["Fighter"] == 3
    assert "Battle Master" in options["subclass_options"]["Fighter"]
    assert options["subclass_bonus_spell_details"]["Fiend"]["1"] == [
        {"name": "burning-hands-zh", "name_en": "Burning Hands", "level": 1},
        {"name": "command-zh", "name_en": "Command", "level": 1},
    ]
    assert "precision" in options["maneuvers"]
    assert options["battle_master_maneuvers_known_by_level"][3] == 3
    assert options["starting_gear_packs"]["Explorer's Pack"][0] == {
        "name": "Backpack",
        "zh": "背包",
        "quantity": 1,
    }
    assert {"name": "Torch", "zh": "火把", "quantity": 10} in options["starting_gear_packs"]["Explorer's Pack"]
    assert options["background_equipment"]["士兵"]["gold"] == 10
    assert {"name": "Insignia of Rank", "zh": "军衔徽记", "quantity": 1} in options["background_equipment"]["士兵"]["items"]


def test_build_starting_gear_pack_options_labels_pack_contents():
    packs = build_starting_gear_pack_options()

    assert packs["Scholar's Pack"][-1] == {
        "name": "Small Knife",
        "zh": "小刀",
        "quantity": 1,
    }


def test_build_background_equipment_options_labels_items_and_gold():
    backgrounds = build_background_equipment_options()

    assert backgrounds["学者"]["gold"] == 10
    assert {"name": "Quill", "zh": "羽毛笔", "quantity": 1} in backgrounds["学者"]["items"]
    assert backgrounds["Sage"]["items"] == backgrounds["学者"]["items"]
