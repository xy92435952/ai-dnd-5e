import pytest

from services.combat_attack_roll_service import (
    CombatAttackRollError,
    apply_d20_override,
    build_pending_attack,
    consume_attack_turn_state,
    validate_attack_turn_state,
)


def test_validate_attack_turn_state_rejects_action_spent_after_max_attacks():
    with pytest.raises(CombatAttackRollError) as exc:
        validate_attack_turn_state(
            {"attacks_made": 1, "action_used": True},
            max_attacks=1,
            is_offhand=False,
        )

    assert exc.value.status_code == 400
    assert "行动已用尽" in exc.value.detail


def test_validate_attack_turn_state_rejects_offhand_before_main_attack():
    with pytest.raises(CombatAttackRollError) as exc:
        validate_attack_turn_state(
            {"attacks_made": 0, "action_used": False, "bonus_action_used": False},
            max_attacks=1,
            is_offhand=True,
        )

    assert exc.value.status_code == 400
    assert "副手攻击需要先完成" in exc.value.detail


def test_validate_attack_turn_state_allows_offhand_after_main_attack_limit():
    turn_state = validate_attack_turn_state(
        {"attacks_made": 1, "action_used": True, "bonus_action_used": False},
        max_attacks=1,
        is_offhand=True,
    )

    assert turn_state["attacks_made"] == 1
    assert turn_state["action_used"] is True
    assert turn_state["bonus_action_used"] is False


def test_validate_attack_turn_state_allows_offhand_before_extra_attack_spent():
    turn_state = validate_attack_turn_state(
        {"attacks_made": 1, "action_used": False, "bonus_action_used": False},
        max_attacks=2,
        is_offhand=True,
    )

    assert turn_state["attacks_made"] == 1
    assert turn_state["action_used"] is False
    assert turn_state["bonus_action_used"] is False


def test_apply_d20_override_recomputes_crit_fumble_and_hit():
    result = apply_d20_override(
        {
            "attack_bonus": 5,
            "target_ac": 18,
            "d20": 7,
            "attack_total": 12,
            "hit": False,
            "is_crit": False,
            "is_fumble": False,
        },
        d20_value=20,
        crit_threshold=19,
    )

    assert result["d20"] == 20
    assert result["attack_total"] == 25
    assert result["is_crit"] is True
    assert result["is_fumble"] is False
    assert result["hit"] is True


def test_consume_attack_turn_state_sets_action_when_attack_count_reaches_max():
    ts = {"attacks_made": 0, "action_used": False, "bonus_action_used": False}
    pending = {"pending_attack_id": "pa-1"}

    updated = consume_attack_turn_state(
        ts,
        max_attacks=1,
        is_offhand=False,
        pending_attack=pending,
    )

    assert updated["attacks_made"] == 1
    assert updated["action_used"] is True
    assert updated["pending_attack"] == pending


def test_consume_attack_turn_state_offhand_spends_bonus_without_main_attack_count():
    ts = {"attacks_made": 1, "action_used": True, "bonus_action_used": False}
    pending = {"pending_attack_id": "pa-off"}

    updated = consume_attack_turn_state(
        ts,
        max_attacks=1,
        is_offhand=True,
        pending_attack=pending,
    )

    assert updated["attacks_made"] == 1
    assert updated["action_used"] is True
    assert updated["bonus_action_used"] is True
    assert updated["pending_attack"] == pending


def test_build_pending_attack_preserves_attack_contract_fields():
    pending = build_pending_attack(
        pending_attack_id="pa-1",
        attacker_id="char-1",
        target_id="enemy-1",
        target_name="哥布林",
        target_is_enemy=True,
        attacker_name="战士",
        attack_roll={"hit": True, "is_crit": False},
        is_ranged=False,
        is_offhand=False,
        cover_bonus=0,
        ranged_penalty=False,
        feat_power_active=True,
        feat_power_bonus_damage=10,
        advantage=True,
        disadvantage=False,
        is_raging=True,
        target_conditions=["hexed"],
        damage_dice="1d8+3",
        hit_die=8,
        dmg_mod=3,
    )

    assert pending["pending_attack_id"] == "pa-1"
    assert pending["hit"] is True
    assert pending["is_crit"] is False
    assert pending["feat_power_attack"] is True
    assert pending["feat_power_bonus_dmg"] == 10
    assert pending["target_conditions"] == ["hexed"]
