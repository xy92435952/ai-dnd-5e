import pytest

from services.combat_spell_roll_service import (
    CombatSpellRollError,
    build_spell_ability_context,
    build_spell_roll_preview,
    spell_action_cost,
    spell_requires_attack_roll,
    validate_spell_turn_state,
)


def test_validate_spell_turn_state_rejects_leveled_spell_after_action_used():
    with pytest.raises(CombatSpellRollError) as exc:
        validate_spell_turn_state({"action_used": True}, is_cantrip=False)

    assert exc.value.status_code == 400
    assert "行动已用尽" in exc.value.detail


def test_validate_spell_turn_state_rejects_action_cantrip_after_action_used():
    with pytest.raises(CombatSpellRollError) as exc:
        validate_spell_turn_state({"action_used": True}, is_cantrip=True)

    assert exc.value.status_code == 400
    assert "行动已用尽" in exc.value.detail


def test_validate_spell_turn_state_uses_bonus_action_budget():
    turn_state = {"action_used": True, "bonus_action_used": False}

    assert validate_spell_turn_state(turn_state, action_cost="bonus") is turn_state

    with pytest.raises(CombatSpellRollError) as exc:
        validate_spell_turn_state({"bonus_action_used": True}, action_cost="bonus")

    assert exc.value.status_code == 400
    assert "附赠动作已用尽" in exc.value.detail


def test_validate_spell_turn_state_rejects_reaction_spells():
    with pytest.raises(CombatSpellRollError) as exc:
        validate_spell_turn_state({}, action_cost="reaction")

    assert exc.value.status_code == 400
    assert "反应法术" in exc.value.detail


def test_spell_action_cost_reads_casting_time():
    assert spell_action_cost({"casting_time": "bonus_action"}) == "bonus"
    assert spell_action_cost({"casting_time": "reaction"}) == "reaction"
    assert spell_action_cost({"casting_time": "action"}) == "action"
    assert spell_action_cost({}) == "action"


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

    assert context == {"spell_mod": 4, "spell_save_dc": 16, "spell_attack_bonus": 4}


def test_build_spell_ability_context_includes_spell_attack_bonus_when_available():
    context = build_spell_ability_context({
        "spell_ability": "int",
        "ability_modifiers": {"int": 3},
        "proficiency_bonus": 2,
        "spell_save_dc": 13,
    })

    assert context["spell_attack_bonus"] == 5


def test_spell_requires_attack_roll_for_non_save_damage_spells_except_auto_hit():
    assert spell_requires_attack_roll("Fire Bolt", {"type": "damage", "save": None}) is True
    assert spell_requires_attack_roll("Sacred Flame", {"type": "damage", "save": "dex"}) is False
    assert spell_requires_attack_roll("Magic Missile", {"type": "damage", "save": None}) is False
