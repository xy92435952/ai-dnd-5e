from services.character_options_service import (
    build_character_options,
    build_starting_gear_pack_options,
)


class FakeSpellService:
    def get_cantrips_for_class(self, cls):
        return [{"name": f"{cls}-cantrip"}]

    def get_for_class(self, cls):
        return [{"name": f"{cls}-cantrip", "level": 0}, {"name": f"{cls}-spell", "level": 1}]


def test_build_character_options_includes_spell_metadata_for_spellcasters():
    options = build_character_options(FakeSpellService())

    assert "Wizard" in options["spellcaster_classes"]
    assert options["class_cantrips"]["Wizard"] == ["Wizard-cantrip"]
    assert options["class_spells"]["Wizard"] == ["Wizard-spell"]
    assert options["starting_cantrips_count"]["Wizard"] >= 0
    assert options["races"]
    assert options["class_skill_choices"]
    assert options["feats"]
    assert options["starting_gear_packs"]["Explorer's Pack"][0] == {
        "name": "Backpack",
        "zh": "背包",
        "quantity": 1,
    }
    assert {"name": "Torch", "zh": "火把", "quantity": 10} in options["starting_gear_packs"]["Explorer's Pack"]


def test_build_starting_gear_pack_options_labels_pack_contents():
    packs = build_starting_gear_pack_options()

    assert packs["Scholar's Pack"][-1] == {
        "name": "Small Knife",
        "zh": "小刀",
        "quantity": 1,
    }
