from services.combat_charmed_service import (
    charmed_harmful_spell_target_id,
    charmed_source_ids,
    is_charmed_by_target,
    spell_is_harmful_to_target,
)


def test_charmed_source_ids_accept_duration_metadata_shapes():
    durations = {
        "charmed": {"duration": 2, "source_id": "enemy-1"},
        "charmed_source_ids": ["enemy-2"],
        "charmer": {"casterId": "enemy-3"},
    }

    assert charmed_source_ids(durations) == {"enemy-1", "enemy-2", "enemy-3"}


def test_is_charmed_by_target_requires_charmed_condition_and_matching_source():
    durations = {"charmed": {"duration": 2, "source_id": "enemy-1"}}

    assert is_charmed_by_target(["charmed"], durations, "enemy-1") is True
    assert is_charmed_by_target(["charmed"], durations, "enemy-2") is False
    assert is_charmed_by_target(["poisoned"], durations, "enemy-1") is False


def test_charmed_harmful_spell_target_id_blocks_only_harmful_spells_against_charmer():
    durations = {"charmed": {"duration": 2, "source_id": "enemy-1"}}

    assert spell_is_harmful_to_target("Sacred Flame", {"type": "damage", "save": "dex"}) is True
    assert spell_is_harmful_to_target("Cure Wounds", {"type": "heal"}) is False
    assert spell_is_harmful_to_target("Hex", {"type": "utility", "name_en": "Hex"}) is True

    assert charmed_harmful_spell_target_id(
        ["charmed"],
        durations,
        spell_name="Sacred Flame",
        spell={"type": "damage", "save": "dex"},
        target_ids=["enemy-1"],
    ) == "enemy-1"
    assert charmed_harmful_spell_target_id(
        ["charmed"],
        durations,
        spell_name="Cure Wounds",
        spell={"type": "heal"},
        target_ids=["enemy-1"],
    ) is None
    assert charmed_harmful_spell_target_id(
        ["charmed"],
        durations,
        spell_name="Sacred Flame",
        spell={"type": "damage", "save": "dex"},
        target_ids=["enemy-2"],
    ) is None
