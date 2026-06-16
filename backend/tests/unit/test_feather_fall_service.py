from types import SimpleNamespace

import pytest

from services.feather_fall_service import (
    FeatherFallError,
    apply_feather_fall_damage_prevention,
    build_feather_fall_reaction_option,
    character_can_cast_feather_fall,
    character_knows_feather_fall,
    is_fall_damage_event,
    resolve_feather_fall_reaction,
)


def _caster(**overrides):
    data = {
        "id": "bard-1",
        "name": "Lyra",
        "char_class": "Bard",
        "known_spells": ["Feather Fall"],
        "prepared_spells": [],
        "spell_slots": {"1st": 1, "2nd": 1},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_detects_fall_damage_metadata_without_matching_generic_bludgeoning():
    assert is_fall_damage_event({
        "name": "Hidden pit",
        "damage_type": "bludgeoning",
        "damage": 12,
    }) is True
    assert is_fall_damage_event({
        "label": "Collapsed ledge",
        "fall_distance_ft": 40,
        "damage": 14,
    }) is True
    assert is_fall_damage_event({
        "label": "Stone hammer trap",
        "damage_type": "bludgeoning",
        "damage": 9,
    }) is False


def test_character_knows_feather_fall_from_english_or_chinese_alias():
    assert character_knows_feather_fall(_caster(known_spells=["feather-fall"])) is True
    assert character_knows_feather_fall(_caster(known_spells=["\u8dcc\u843d\u4e4b\u7fbd"])) is True
    assert character_knows_feather_fall(_caster(known_spells=["Shield"])) is False


def test_build_reaction_option_reports_slot_and_prevented_damage():
    caster = _caster(spell_slots={"1st": 0, "2nd": 2})
    event = {"label": "Falling shaft", "damage_type": "falling", "final_damage": 16}

    option = build_feather_fall_reaction_option(
        caster,
        event,
        targets=[{"id": "hero-1", "name": "Hero"}],
    )

    assert option == {
        "id": "feather_fall",
        "name": "Feather Fall",
        "type": "feather_fall",
        "trigger": "fall_damage",
        "cost": "2nd spell slot + reaction",
        "slot_level": "2nd",
        "slot_level_number": 2,
        "slots_remaining": 2,
        "damage_before": 16,
        "damage_after": 0,
        "damage_prevented": 16,
        "max_targets": 5,
        "target_ids": ["hero-1"],
    }


def test_resolve_feather_fall_spends_lowest_slot_and_reaction():
    caster = _caster(spell_slots={"1st": 0, "2nd": 1})
    reaction_state = {}
    event = {"label": "Falling shaft", "damage_type": "fall", "damage": 11}

    result = resolve_feather_fall_reaction(
        caster=caster,
        fall_event=event,
        targets=[{"id": "hero-1", "name": "Hero"}],
        reaction_state=reaction_state,
    )

    assert caster.spell_slots == {"1st": 0, "2nd": 0}
    assert reaction_state["reaction_used"] is True
    assert reaction_state["feather_fall"]["damage_prevented"] == 11
    assert result["slot_level"] == "2nd"
    assert result["damage_before"] == 11
    assert result["damage_after"] == 0
    assert result["damage_prevented"] == 11
    assert result["target_ids"] == ["hero-1"]
    assert result["target_names"] == ["Hero"]


def test_resolve_feather_fall_rejects_missing_spell_slot_or_spent_reaction():
    assert character_can_cast_feather_fall(_caster(spell_slots={"1st": 0})) is False

    with pytest.raises(FeatherFallError, match="Reaction already used"):
        resolve_feather_fall_reaction(
            caster=_caster(),
            fall_event={"label": "Falling shaft", "damage_type": "fall", "damage": 8},
            reaction_state={"reaction_used": True},
        )


def test_resolve_feather_fall_caps_targets_at_five_creatures():
    targets = [{"id": f"hero-{index}"} for index in range(6)]

    with pytest.raises(FeatherFallError, match="at most five"):
        resolve_feather_fall_reaction(
            caster=_caster(),
            fall_event={"label": "Falling shaft", "damage_type": "fall", "damage": 8},
            targets=targets,
        )


def test_apply_feather_fall_damage_prevention_keeps_original_event_metadata():
    event = {"label": "Falling shaft", "damage_type": "fall", "damage": 11}
    prevented = {
        "type": "feather_fall",
        "damage_prevented": 11,
        "slot_level": "1st",
    }

    result = apply_feather_fall_damage_prevention(event, prevented)

    assert result["label"] == "Falling shaft"
    assert result["damage_type"] == "fall"
    assert result["damage"] == 0
    assert result["final_damage"] == 0
    assert result["feather_fall"] == prevented
