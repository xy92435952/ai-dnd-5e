from services.enemy_inspect_service import (
    ALL_STATS,
    apply_enemy_inspect_result,
    build_enemy_inspect_snapshot,
    default_enemy_inspect_dc,
)


def _enemy():
    return {
        "id": "enemy-1",
        "name": "Veiled Stalker",
        "cr": "2",
        "speed": 40,
        "resistances": ["necrotic"],
        "immunities": ["poison"],
        "vulnerabilities": ["radiant"],
        "condition_immunities": ["poisoned"],
        "actions": [{"name": "Shadow Strike"}],
        "special_abilities": [{"name": "Shadow Blend"}],
        "tactics": "Flank isolated casters.",
    }


def test_inspect_success_reveals_skill_specific_stats():
    enemies, target, revealed = apply_enemy_inspect_result(
        [_enemy()],
        "enemy-1",
        skill="investigation",
        dc=13,
        check_result={"d20": 13, "total": 14, "success": True},
        character_id="char-1",
        character_name="Tester",
    )

    assert target is not None
    assert "actions" in revealed
    assert "resistances" in target["knowledge_state"]["by_character"]["char-1"]["revealed_stats"]
    assert enemies[0]["knowledge_state"]["by_character"]["char-1"]["last_inspect"]["success"] is True
    public_snapshot = build_enemy_inspect_snapshot(enemies[0])
    assert "actions" not in public_snapshot
    snapshot = build_enemy_inspect_snapshot(enemies[0], viewer_character_id="char-1")
    assert snapshot["actions"] == [{"name": "Shadow Strike"}]
    assert snapshot["resistances"] == ["necrotic"]
    assert "tactics" not in snapshot
    other_snapshot = build_enemy_inspect_snapshot(enemies[0], viewer_character_id="char-2")
    assert "actions" not in other_snapshot
    assert "resistances" not in other_snapshot


def test_high_margin_or_natural_twenty_identifies_all_stats():
    enemies, target, revealed = apply_enemy_inspect_result(
        [_enemy()],
        "enemy-1",
        skill="perception",
        dc=12,
        check_result={"d20": 20, "total": 21, "success": True},
        character_id="char-1",
        character_name="Tester",
    )

    assert revealed == [ALL_STATS]
    assert target["knowledge_state"]["by_character"]["char-1"]["identified"] is True
    snapshot = build_enemy_inspect_snapshot(enemies[0], viewer_character_id="char-1")
    assert snapshot["revealed_stats"] == [ALL_STATS]
    assert snapshot["tactics"] == "Flank isolated casters."
    assert snapshot["special_abilities"] == [{"name": "Shadow Blend"}]
    public_snapshot = build_enemy_inspect_snapshot(enemies[0])
    assert "tactics" not in public_snapshot


def test_failed_inspect_records_attempt_without_revealing_stats():
    enemies, target, revealed = apply_enemy_inspect_result(
        [_enemy()],
        "enemy-1",
        skill="perception",
        dc=15,
        check_result={"d20": 4, "total": 5, "success": False},
        character_id="char-1",
        character_name="Tester",
    )

    assert revealed == []
    assert target["knowledge_state"]["by_character"]["char-1"]["inspected"] is True
    snapshot = build_enemy_inspect_snapshot(enemies[0], viewer_character_id="char-1")
    assert "actions" not in snapshot
    assert "resistances" not in snapshot
    assert "revealed_stats" not in snapshot


def test_default_inspect_dc_scales_with_cr():
    assert default_enemy_inspect_dc({"cr": "1/2"}) == 11
    assert default_enemy_inspect_dc({"cr": "8"}) == 18
    assert default_enemy_inspect_dc({"cr": "99"}) == 20
