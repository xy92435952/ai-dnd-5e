from services.combat_enemy_ammunition_service import (
    consume_enemy_attack_action_resource,
    select_enemy_attack_action,
    select_enemy_multiattack_actions,
)


def test_enemy_ranged_action_consumes_tracked_ammunition():
    enemy = {
        "actions": [
            {
                "name": "Shortbow",
                "type": "ranged_attack",
                "properties": ["ammunition", "range(80/320)"],
                "ammo": 2,
            }
        ]
    }

    selection = select_enemy_attack_action(enemy, preferred_is_ranged=True)
    resource = consume_enemy_attack_action_resource(selection.action)

    assert selection.action["ammo"] == 1
    assert resource == {
        "weapon": "Shortbow",
        "action_name": "Shortbow",
        "resource_type": "ammunition",
        "consumed": True,
        "enemy_resource": True,
        "ammo_remaining": 1,
    }


def test_enemy_thrown_action_consumes_tracked_quantity_and_disables_empty_action():
    enemy = {
        "actions": [
            {
                "name": "Javelin",
                "type": "ranged_attack",
                "properties": ["thrown(30/120)"],
                "quantity": 1,
            }
        ]
    }

    selection = select_enemy_attack_action(enemy, preferred_is_ranged=True)
    resource = consume_enemy_attack_action_resource(selection.action)

    assert selection.action["quantity"] == 0
    assert selection.action["available"] is False
    assert resource["resource_type"] == "thrown_weapon"
    assert resource["quantity_remaining"] == 0
    assert resource["weapon_removed"] is True


def test_enemy_empty_ranged_action_falls_back_to_available_melee():
    enemy = {
        "actions": [
            {
                "name": "Shortbow",
                "type": "ranged_attack",
                "properties": ["ammunition", "range(80/320)"],
                "ammo": 0,
            },
            {
                "name": "Scimitar",
                "type": "melee_attack",
            },
        ]
    }

    selection = select_enemy_attack_action(enemy, preferred_is_ranged=True)

    assert selection.action["name"] == "Scimitar"
    assert selection.is_ranged is False
    assert selection.switched_from_ranged is True


def test_enemy_empty_tracked_resource_reports_unavailable_when_no_fallback():
    enemy = {
        "actions": [
            {
                "name": "Shortbow",
                "type": "ranged_attack",
                "properties": ["ammunition", "range(80/320)"],
                "ammo": 0,
            }
        ]
    }

    selection = select_enemy_attack_action(enemy, preferred_is_ranged=True)

    assert selection.action is None
    assert selection.unavailable_resource == {
        "weapon": "Shortbow",
        "action_name": "Shortbow",
        "resource_type": "ammunition",
        "consumed": False,
        "enemy_resource": True,
        "ammo_remaining": 0,
        "unavailable": True,
    }


def test_enemy_adjacent_target_prefers_available_melee_over_ranged_action():
    enemy = {
        "actions": [
            {
                "name": "Shortbow",
                "type": "ranged_attack",
                "properties": ["ammunition", "range(80/320)"],
                "ammo": 1,
            },
            {
                "name": "Claws",
                "type": "melee_attack",
                "reach": 5,
            },
        ]
    }

    selection = select_enemy_attack_action(
        enemy,
        preferred_is_ranged=True,
        target_distance_tiles=1,
    )

    assert selection.action["name"] == "Claws"
    assert selection.is_ranged is False
    assert enemy["actions"][0]["ammo"] == 1


def test_enemy_prefers_higher_damage_authored_action_with_same_reach():
    enemy = {
        "actions": [
            {
                "name": "Scratch",
                "type": "melee_attack",
                "damage_dice": "1d4",
                "reach": 5,
            },
            {
                "name": "Heavy Claw",
                "type": "melee_attack",
                "damage_dice": "1d10+3",
                "reach": 5,
            },
        ]
    }

    selection = select_enemy_attack_action(
        enemy,
        preferred_is_ranged=False,
        target_distance_tiles=1,
    )

    assert selection.action["name"] == "Heavy Claw"
    assert selection.is_ranged is False
    assert selection.selection_reason == "adjacent_melee_damage"
    assert selection.damage_score == 8.5


def test_enemy_multiattack_text_preserves_authored_action_sequence():
    enemy = {
        "multiattack_text": "The drake makes three attacks: one with its Bite and two with its Claws.",
        "actions": [
            {
                "name": "Tail",
                "type": "melee_attack",
                "damage_dice": "2d10+4",
                "reach": 5,
            },
            {
                "name": "Bite",
                "type": "melee_attack",
                "damage_dice": "1d8+3",
                "reach": 5,
            },
            {
                "name": "Claws",
                "type": "melee_attack",
                "damage_dice": "1d6+3",
                "reach": 5,
            },
        ],
    }

    selections = select_enemy_multiattack_actions(
        enemy,
        preferred_is_ranged=False,
        target_distance_tiles=1,
        attack_count=3,
    )

    assert [selection.action["name"] for selection in selections] == ["Bite", "Claws", "Claws"]
    assert [selection.selection_reason for selection in selections] == [
        "multiattack_sequence",
        "multiattack_sequence",
        "multiattack_sequence",
    ]


def test_enemy_multiattack_explicit_sequence_supports_counted_actions():
    enemy = {
        "multiattack_actions": [
            {"name": "Bite", "count": 1},
            {"name": "Claw", "count": 2},
        ],
        "actions": [
            {
                "name": "Bite",
                "type": "melee_attack",
                "damage_dice": "1d8+3",
                "reach": 5,
            },
            {
                "name": "Claws",
                "type": "melee_attack",
                "damage_dice": "1d6+3",
                "reach": 5,
            },
        ],
    }

    selections = select_enemy_multiattack_actions(
        enemy,
        preferred_is_ranged=False,
        target_distance_tiles=1,
        attack_count=3,
    )

    assert [selection.action["name"] for selection in selections] == ["Bite", "Claws", "Claws"]


def test_enemy_multiattack_explicit_string_supports_counted_actions():
    enemy = {
        "multiattack_sequence": "Bite and two Claws",
        "actions": [
            {
                "name": "Bite",
                "type": "melee_attack",
                "damage_dice": "1d8+3",
                "reach": 5,
            },
            {
                "name": "Claws",
                "type": "melee_attack",
                "damage_dice": "1d6+3",
                "reach": 5,
            },
        ],
    }

    selections = select_enemy_multiattack_actions(
        enemy,
        preferred_is_ranged=False,
        target_distance_tiles=1,
        attack_count=3,
    )

    assert [selection.action["name"] for selection in selections] == ["Bite", "Claws", "Claws"]


def test_enemy_reach_action_can_be_selected_when_target_is_two_tiles_away():
    enemy = {
        "actions": [
            {
                "name": "Bite",
                "type": "melee_attack",
                "reach": 5,
            },
            {
                "name": "Tentacle",
                "type": "melee_attack",
                "properties": ["reach"],
            },
        ]
    }

    selection = select_enemy_attack_action(
        enemy,
        preferred_is_ranged=False,
        target_distance_tiles=2,
    )

    assert selection.action["name"] == "Tentacle"
    assert selection.is_ranged is False


def test_enemy_distance_selection_keeps_ranged_action_for_far_target():
    enemy = {
        "actions": [
            {
                "name": "Claws",
                "type": "melee_attack",
                "reach": 5,
            },
            {
                "name": "Shortbow",
                "type": "ranged_attack",
                "properties": ["ammunition", "range(80/320)"],
                "ammo": 1,
            },
        ]
    }

    selection = select_enemy_attack_action(
        enemy,
        preferred_is_ranged=True,
        target_distance_tiles=6,
    )

    assert selection.action["name"] == "Shortbow"
    assert selection.is_ranged is True
