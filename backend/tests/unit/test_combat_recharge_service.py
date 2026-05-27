from services.combat_recharge_service import (
    choose_recharge_ability,
    mark_recharge_ability_used,
    normalize_recharge_abilities,
    parse_recharge_threshold,
    refresh_recharge_abilities_at_turn_start,
)


def test_parse_recharge_threshold_accepts_common_statblock_shapes():
    assert parse_recharge_threshold("Recharge 5-6") == 5
    assert parse_recharge_threshold("recharges on 6") == 6
    assert parse_recharge_threshold("5-6") == 5
    assert parse_recharge_threshold(4) == 4
    assert parse_recharge_threshold("at will") is None
    assert parse_recharge_threshold(True) is None


def test_normalize_recharge_abilities_collects_explicit_and_action_data():
    monster = {
        "recharge_abilities": [{
            "name": "Frost Breath",
            "recharge": "5-6",
            "description": "Cold cone.",
        }],
        "actions": [{
            "name": "Fire Breath",
            "type": "special",
            "recharge": "Recharge 6",
            "damage_dice": "4d6",
            "damage_type": "fire",
        }],
        "special_abilities": [{
            "name": "Keen Smell",
            "description": "Advantage on smell checks.",
        }],
    }

    abilities = normalize_recharge_abilities(monster)

    assert [ability["name"] for ability in abilities] == ["Frost Breath", "Fire Breath"]
    assert abilities[0]["threshold"] == 5
    assert abilities[0]["available"] is True
    assert abilities[1]["threshold"] == 6
    assert abilities[1]["damage_dice"] == "4d6"
    assert abilities[1]["source"] == "action"


def test_refresh_recharge_abilities_rolls_only_unavailable_abilities():
    enemy = {
        "id": "dragon-1",
        "recharge_abilities": [
            {"id": "breath", "name": "Breath Weapon", "threshold": 5, "available": False},
            {"id": "gaze", "name": "Terrifying Gaze", "threshold": 6, "available": True},
        ],
    }

    result = refresh_recharge_abilities_at_turn_start(enemy, roll_d6=lambda: 5)

    assert result["changed"] is True
    assert result["events"] == [{
        "ability_id": "breath",
        "name": "Breath Weapon",
        "roll": 5,
        "threshold": 5,
        "recharged": True,
    }]
    assert enemy["recharge_abilities"][0]["available"] is True
    assert enemy["recharge_abilities"][0]["last_recharge_roll"] == 5
    assert enemy["recharge_abilities"][1].get("last_recharge_roll") is None


def test_refresh_recharge_abilities_keeps_failed_roll_unavailable():
    enemy = {
        "actions": [{
            "name": "Acid Spray",
            "type": "special",
            "recharge": "5-6",
            "available": False,
        }],
    }

    result = refresh_recharge_abilities_at_turn_start(enemy, roll_d6=lambda: 4)

    assert result["events"][0]["recharged"] is False
    assert enemy["recharge_abilities"][0]["available"] is False
    assert enemy["recharge_abilities"][0]["last_recharge_roll"] == 4


def test_choose_recharge_ability_prefers_available_requested_action_name():
    enemy = {
        "recharge_abilities": [
            {"id": "breath", "name": "Breath Weapon", "threshold": 5, "available": False},
            {"id": "gaze", "name": "Terrifying Gaze", "threshold": 6, "available": True},
        ],
    }

    assert choose_recharge_ability(enemy, action_name="Breath Weapon") is None
    chosen = choose_recharge_ability(enemy, action_name="Terrifying Gaze")

    assert chosen["id"] == "gaze"


def test_mark_recharge_ability_used_sets_available_false():
    enemy = {
        "recharge_abilities": [{
            "id": "breath",
            "name": "Breath Weapon",
            "threshold": 5,
            "available": True,
            "last_recharge_roll": 6,
        }],
    }

    assert mark_recharge_ability_used(enemy, "breath") is True
    assert enemy["recharge_abilities"][0]["available"] is False
    assert "last_recharge_roll" not in enemy["recharge_abilities"][0]
