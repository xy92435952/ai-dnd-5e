from types import SimpleNamespace

from services.combat_evasion_service import (
    has_evasion,
    resolve_save_damage,
    spell_half_on_save,
)


def test_has_evasion_for_level_seven_rogue_or_monk():
    assert has_evasion({"char_class": "Rogue", "level": 7}) is True
    assert has_evasion(SimpleNamespace(char_class="Monk", level=7, derived={})) is True
    assert has_evasion({"char_class": "Rogue", "level": 6}) is False


def test_resolve_save_damage_applies_evasion_success_and_failure_rules():
    target = {"char_class": "Rogue", "level": 7}

    success = resolve_save_damage(
        21,
        save_result={"success": True},
        save_ability="dex",
        half_on_save=True,
        target=target,
    )
    failure = resolve_save_damage(
        21,
        save_result={"success": False},
        save_ability="dex",
        half_on_save=True,
        target=target,
    )

    assert success == {
        "damage": 0,
        "evasion_applied": True,
        "evasion_failed_half": False,
    }
    assert failure == {
        "damage": 10,
        "evasion_applied": False,
        "evasion_failed_half": True,
    }


def test_resolve_save_damage_leaves_non_dex_saves_on_normal_half_damage():
    result = resolve_save_damage(
        21,
        save_result={"success": True},
        save_ability="con",
        half_on_save=True,
        target={"char_class": "Monk", "level": 7},
    )

    assert result["damage"] == 10
    assert result["evasion_applied"] is False


def test_spell_half_on_save_prefers_explicit_flag_then_description():
    assert spell_half_on_save({"half_on_save": False, "desc": "成功减半"}) is False
    assert spell_half_on_save({"desc": "DEX豁免失败受伤，成功减半"}) is True
    assert spell_half_on_save({"desc": "DEX豁免失败受伤，豁免无效"}) is False
