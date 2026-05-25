from types import SimpleNamespace

from services.combat_reaction_service import (
    build_pending_attack_reaction,
    calculate_hellish_rebuke_damage,
    calculate_reaction_save,
    calculate_shield_prevention,
    calculate_uncanny_dodge_prevention,
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
                "hit": True,
            },
        ],
    )

    assert pending["attacker_id"] == "enemy-1"
    assert pending["target_id"] == "hero-1"
    assert pending["incoming_damage"] == 6
    assert pending["target_hp_before_damage"] == 10
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
        "modifier": 5,
        "total": 13,
        "success": True,
    }


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
