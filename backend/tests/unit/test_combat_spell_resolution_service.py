import pytest

from services.combat_spell_resolution_service import (
    CombatSpellResolutionError,
    apply_spell_critical_damage,
    build_spell_mechanical_narration,
    build_spell_resolution_context,
    consume_spell_slot_for_confirmation,
    resolve_spell_roll_amount,
)


def test_consume_spell_slot_for_confirmation_skips_cantrip():
    slots = {"1st": 1}

    result = consume_spell_slot_for_confirmation(
        current_slots=slots,
        spell_level=0,
        is_cantrip=True,
        consume_slot=lambda *_args: (_ for _ in ()).throw(AssertionError("should not consume")),
    )

    assert result == slots


def test_consume_spell_slot_for_confirmation_raises_slot_error():
    with pytest.raises(CombatSpellResolutionError) as exc:
        consume_spell_slot_for_confirmation(
            current_slots={"1st": 0},
            spell_level=1,
            is_cantrip=False,
            consume_slot=lambda slots, level: (slots, "没有可用的1环法术位"),
        )

    assert exc.value.status_code == 400
    assert "没有可用" in exc.value.detail


def test_build_spell_resolution_context_reads_bonus_healing():
    context = build_spell_resolution_context({
        "spell_ability": "cha",
        "ability_modifiers": {"cha": 4},
        "spell_save_dc": 15,
        "bonus_healing": True,
    })

    assert context == {"spell_mod": 4, "spell_save_dc": 15, "bonus_healing": True}


def test_resolve_spell_roll_amount_applies_frontend_override_for_damage():
    amount, dice = resolve_spell_roll_amount(
        spell_type="damage",
        spell_name="Magic Missile",
        spell_level=1,
        spell_mod=3,
        bonus_healing=False,
        damage_values=[1, 2, 3],
        resolve_damage=lambda name, level, mod: (10, {"base_roll": {"rolls": [4, 3, 0], "total": 7}, "total": 10}),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert amount == 6
    assert dice["total"] == 6
    assert dice["base_roll"]["rolls"] == [1, 2, 3]


def test_resolve_spell_roll_amount_keeps_spell_flat_bonus_when_overriding_damage():
    amount, dice = resolve_spell_roll_amount(
        spell_type="damage",
        spell_name="Magic Missile",
        spell_level=1,
        spell_mod=3,
        bonus_healing=False,
        damage_values=[1, 2, 3],
        resolve_damage=lambda name, level, mod: (10, {"base_roll": {"rolls": [4, 3, 0], "bonus": 3, "total": 10}, "total": 10}),
        resolve_heal=lambda *_args: (_ for _ in ()).throw(AssertionError("should not heal")),
    )

    assert amount == 9
    assert dice["total"] == 9


def test_apply_spell_critical_damage_doubles_dice_not_flat_bonus():
    amount, dice = apply_spell_critical_damage(
        9,
        {"base_roll": {"notation": "1d10+3", "rolls": [6], "total": 9}, "total": 9},
        is_crit=True,
        roll_dice=lambda expr: {"notation": expr, "rolls": [4], "total": 4},
    )

    assert amount == 13
    assert dice["crit_extra"] == 4
    assert dice["crit_rolls"][0]["notation"] == "1d10"
    assert dice["total"] == 13


def test_build_spell_mechanical_narration_summarizes_aoe_damage():
    narration = build_spell_mechanical_narration(
        caster_name="梅林",
        spell_name="Burning Hands",
        spell_level=1,
        is_cantrip=False,
        is_aoe=True,
        aoe_results=[
            {"target_name": "哥布林A"},
            {"target_name": "哥布林B"},
        ],
        result_damage=8,
        result_heal=0,
        spell_type="damage",
        save_detail=None,
        condition_name=None,
    )

    assert "梅林" in narration
    assert "Burning Hands" in narration
    assert "哥布林A、哥布林B" in narration
    assert "单目标最高 8 点伤害" in narration
