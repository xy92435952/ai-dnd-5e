from types import SimpleNamespace

from services.combat_reaction_service import (
    build_pending_attack_reaction,
    calculate_counterspell_result,
    calculate_hellish_rebuke_damage,
    calculate_reaction_save,
    calculate_shield_prevention,
    calculate_uncanny_dodge_prevention,
    character_knows_counterspell,
    choose_counterspell_slot,
    restore_prevented_damage,
)


def test_build_pending_attack_reaction_captures_attack_events():
    pending = build_pending_attack_reaction(
        attacker_id="enemy-1",
        attacker_name="Goblin",
        target_id="hero-1",
        attack_events=[
            {
                "attack_total": 17,
                "target_ac": 15,
                "damage": 6,
                "hp_before": 10,
                "hp_after": 4,
                "temporary_hp_before": 5,
                "temporary_hp_after": 0,
                "wild_shape_hp_before": 7,
                "wild_shape_hp_after": 6,
                "class_resources_before": {
                    "temporary_hp": 5,
                    "temporary_hp_source": "armor_of_agathys",
                    "armor_of_agathys_active": True,
                    "wild_shape_active": "Wolf",
                    "wild_shape_hp": 7,
                },
                "conditions_before": ["armor_of_agathys"],
                "condition_durations_before": {"armor_of_agathys": 600},
                "hit": True,
            },
        ],
    )

    assert pending["attacker_id"] == "enemy-1"
    assert pending["target_id"] == "hero-1"
    assert pending["incoming_damage"] == 6
    assert pending["target_hp_before_damage"] == 10
    assert pending["target_temporary_hp_before_damage"] == 5
    assert pending["target_wild_shape_hp_before_damage"] == 7
    assert pending["target_class_resources_before_damage"]["armor_of_agathys_active"] is True
    assert pending["target_conditions_before_damage"] == ["armor_of_agathys"]
    assert pending["target_condition_durations_before_damage"] == {"armor_of_agathys": 600}
    assert pending["events"][0]["attack_total"] == 17


def test_shield_prevention_only_blocks_attacks_under_plus_five_ac():
    pending = {
        "events": [
            {"attack_total": 17, "target_ac": 15, "damage": 6, "hit": True},
            {"attack_total": 20, "target_ac": 15, "damage": 4, "hit": True},
        ],
    }

    result = calculate_shield_prevention(pending)

    assert result == {"damage_prevented": 6, "blocked_attacks": 1}


def test_uncanny_dodge_halves_first_qualifying_hit():
    pending = {
        "events": [
            {"attack_total": 17, "target_ac": 15, "damage": 7, "hit": True},
            {"attack_total": 18, "target_ac": 15, "damage": 4, "hit": True},
        ],
    }

    result = calculate_uncanny_dodge_prevention(pending)

    assert result == {
        "original_damage": 7,
        "reduced_damage": 3,
        "damage_prevented": 4,
    }


def test_reaction_save_uses_saving_throw_before_ability_modifier():
    result = calculate_reaction_save(
        {
            "saving_throws": {"dex": 5},
            "ability_modifiers": {"dex": 2},
        },
        ability="dex",
        dc=13,
        d20=8,
    )

    assert result == {
        "ability": "dex",
        "dc": 13,
        "d20": 8,
        "other_roll": None,
        "modifier": 5,
        "condition_modifier": 0,
        "roll_modifiers": [],
        "total": 13,
        "success": True,
        "advantage": False,
        "disadvantage": False,
        "exhaustion_disadvantage": False,
        "condition_disadvantage_reasons": [],
        "auto_fail": False,
        "auto_fail_reasons": [],
    }


def test_reaction_save_respects_auto_fail_conditions():
    result = calculate_reaction_save(
        {
            "saving_throws": {"dex": 30},
            "ability_modifiers": {"dex": 30},
        },
        ability="dex",
        dc=13,
        d20=20,
        conditions=["stunned"],
    )

    assert result["total"] == 50
    assert result["success"] is False
    assert result["auto_fail"] is True
    assert result["auto_fail_reasons"] == ["stunned"]


def test_hellish_rebuke_halves_damage_on_successful_dex_save():
    save_detail = {"success": True}

    result = calculate_hellish_rebuke_damage(17, save_detail)

    assert result == {
        "rolled_damage": 17,
        "damage_dealt": 8,
        "save_success": True,
    }


def test_hellish_rebuke_deals_full_damage_on_failed_save():
    save_detail = {"success": False}

    result = calculate_hellish_rebuke_damage(17, save_detail)

    assert result == {
        "rolled_damage": 17,
        "damage_dealt": 17,
        "save_success": False,
    }


def test_restore_prevented_damage_caps_at_pre_attack_hp():
    character = SimpleNamespace(
        hp_current=3,
        derived={"hp_max": 12},
        class_resources={},
        conditions=[],
        death_saves=None,
    )

    result = restore_prevented_damage(
        character,
        {"target_hp_before_damage": 8},
        damage_prevented=10,
    )

    assert character.hp_current == 8
    assert result == {
        "hp_before_reaction": 3,
        "hp_after_reaction": 8,
        "hp_restored": 5,
    }


def test_restore_prevented_damage_restores_temporary_hp_and_armor_state_after_hp():
    character = SimpleNamespace(
        hp_current=8,
        derived={"hp_max": 12},
        class_resources={},
        conditions=[],
        condition_durations={},
        death_saves=None,
    )

    result = restore_prevented_damage(
        character,
        {
            "target_hp_before_damage": 10,
            "target_temporary_hp_before_damage": 5,
            "target_class_resources_before_damage": {
                "temporary_hp": 5,
                "temporary_hp_source": "armor_of_agathys",
                "armor_of_agathys_active": True,
                "armor_of_agathys_damage": 5,
                "armor_of_agathys_spell_level": 1,
            },
            "target_conditions_before_damage": ["armor_of_agathys"],
            "target_condition_durations_before_damage": {"armor_of_agathys": 600},
        },
        damage_prevented=6,
    )

    assert character.hp_current == 10
    assert character.class_resources["temporary_hp"] == 4
    assert character.class_resources["temporary_hp_source"] == "armor_of_agathys"
    assert character.class_resources["armor_of_agathys_active"] is True
    assert "armor_of_agathys" in character.conditions
    assert character.condition_durations["armor_of_agathys"] == 600
    assert result["hp_restored"] == 2
    assert result["temporary_hp_restored"] == 4
    assert result["temporary_hp_after_reaction"] == 4


def test_restore_prevented_damage_restores_wild_shape_after_hp_and_temp_hp():
    character = SimpleNamespace(
        hp_current=8,
        derived={"hp_max": 12},
        class_resources={"temporary_hp": 1, "temporary_hp_source": "generic"},
        conditions=[],
        condition_durations={},
        death_saves=None,
    )

    result = restore_prevented_damage(
        character,
        {
            "target_hp_before_damage": 10,
            "target_temporary_hp_before_damage": 3,
            "target_wild_shape_hp_before_damage": 7,
            "target_class_resources_before_damage": {
                "temporary_hp": 3,
                "temporary_hp_source": "generic",
                "wild_shape_active": "Wolf",
                "wild_shape_hp": 7,
            },
        },
        damage_prevented=8,
    )

    assert character.hp_current == 10
    assert character.class_resources["temporary_hp"] == 3
    assert character.class_resources["wild_shape_active"] == "Wolf"
    assert character.class_resources["wild_shape_hp"] == 4
    assert result["hp_restored"] == 2
    assert result["temporary_hp_restored"] == 2
    assert result["wild_shape_hp_restored"] == 4
    assert result["wild_shape_hp_after_reaction"] == 4


def test_character_knows_counterspell_matches_english_and_chinese_names():
    assert character_knows_counterspell(SimpleNamespace(
        known_spells=["反制法术"],
        prepared_spells=[],
    ))
    assert character_knows_counterspell(SimpleNamespace(
        known_spells=[],
        prepared_spells=["counterspell"],
    ))


def test_choose_counterspell_slot_prefers_lowest_automatic_slot():
    assert choose_counterspell_slot({"3rd": 1, "5th": 1}, 3) == ("3rd", 3)
    assert choose_counterspell_slot({"3rd": 1, "5th": 1}, 5) == ("5th", 5)
    assert choose_counterspell_slot({"3rd": 1}, 5) == ("3rd", 3)
    assert choose_counterspell_slot({"2nd": 1}, 3) is None


def test_counterspell_result_auto_succeeds_when_slot_covers_spell_level():
    result = calculate_counterspell_result(
        countered_spell_level=3,
        counterspell_slot_level=3,
        caster_derived={"spell_ability": "int", "ability_modifiers": {"int": -1}},
        roll_dice_func=lambda _expr: {"rolls": [1], "total": 1},
    )

    assert result["success"] is True
    assert result["automatic"] is True
    assert result["d20"] is None


def test_counterspell_result_rolls_for_higher_level_spells():
    result = calculate_counterspell_result(
        countered_spell_level=5,
        counterspell_slot_level=3,
        caster_derived={"spell_ability": "int", "ability_modifiers": {"int": 4}},
        roll_dice_func=lambda _expr: {"rolls": [10], "total": 10},
    )

    assert result == {
        "success": False,
        "automatic": False,
        "dc": 15,
        "d20": 10,
        "modifier": 4,
        "total": 14,
    }
