from services.combat_legendary_resistance_service import (
    initialize_legendary_resistances,
    legendary_resistance_remaining,
    maybe_use_legendary_resistance,
    normalize_legendary_resistance_uses,
)


def test_normalize_legendary_resistance_uses_reads_common_shapes():
    assert normalize_legendary_resistance_uses(3) == 3
    assert normalize_legendary_resistance_uses("3/day") == 3
    assert normalize_legendary_resistance_uses("Legendary Resistance (3/Day)") == 3
    assert normalize_legendary_resistance_uses(None) == 0
    assert normalize_legendary_resistance_uses(True) == 0


def test_initialize_legendary_resistances_uses_explicit_remaining_count():
    enemy = {"legendary_resistances": 3, "legendary_resistances_remaining": 2}

    result = initialize_legendary_resistances(enemy)

    assert result == {"uses": 3, "remaining": 2}
    assert legendary_resistance_remaining(enemy) == 2


def test_maybe_use_legendary_resistance_turns_failed_save_into_success():
    enemy = {"legendary_resistances": 3, "legendary_resistances_remaining": 1}
    save = {"success": False, "d20": 4, "total": 9, "dc": 15}

    updated = maybe_use_legendary_resistance(enemy, save, reason="spell_save")

    assert updated["success"] is True
    assert updated["original_success"] is False
    assert updated["legendary_resistance_used"] is True
    assert updated["legendary_resistance_remaining"] == 0
    assert updated["legendary_resistance_reason"] == "spell_save"
    assert enemy["legendary_resistances_remaining"] == 0


def test_maybe_use_legendary_resistance_ignores_success_or_empty_pool():
    success = {"success": True, "d20": 20}
    enemy = {"legendary_resistances": 3, "legendary_resistances_remaining": 1}

    assert maybe_use_legendary_resistance(enemy, success) == success
    assert enemy["legendary_resistances_remaining"] == 1

    failed = {"success": False, "d20": 2}
    spent_enemy = {"legendary_resistances": 3, "legendary_resistances_remaining": 0}
    assert maybe_use_legendary_resistance(spent_enemy, failed) == failed
