import pytest

from services.combat_spell_roll_service import (
    CombatSpellRollError,
    build_spell_ability_context,
    build_spell_roll_preview,
    validate_spell_turn_state,
)


def test_validate_spell_turn_state_rejects_leveled_spell_after_action_used():
    with pytest.raises(CombatSpellRollError) as exc:
        validate_spell_turn_state({"action_used": True}, is_cantrip=False)

    assert exc.value.status_code == 400
    assert "行动已用尽" in exc.value.detail


def test_validate_spell_turn_state_allows_cantrip_after_action_used():
    assert validate_spell_turn_state({"action_used": True}, is_cantrip=True)["action_used"] is True


def test_build_spell_roll_preview_prefers_upcast_damage_dice():
    preview = build_spell_roll_preview(
        spell_name="burning-hands",
        spell_level=2,
        spell={"type": "damage", "damage_dice": "3d6", "save": "dex", "aoe": True, "concentration": False},
        calc_upcast_dice=lambda name, level: "4d6",
    )

    assert preview["damage_dice"] == "4d6"
    assert preview["heal_dice"] == ""
    assert preview["save_type"] == "dex"
    assert preview["is_aoe"] is True


def test_build_spell_ability_context_uses_spell_ability_modifier():
    context = build_spell_ability_context({
        "spell_ability": "wis",
        "ability_modifiers": {"wis": 4},
        "spell_save_dc": 16,
    })

    assert context == {"spell_mod": 4, "spell_save_dc": 16}
