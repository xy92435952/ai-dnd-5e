from services.combat_spell_damage_component_service import (
    apply_save_to_damage_components,
    resolve_spell_damage_components,
)


def test_resolve_ice_storm_damage_components_from_mixed_roll_parts():
    components = resolve_spell_damage_components(
        "Ice Storm",
        {"name_en": "Ice Storm"},
        dice_detail={
            "base_roll": {
                "total": 20,
                "parts": [
                    {"notation": "2d8", "rolls": [4, 4], "total": 8},
                    {"notation": "4d6", "rolls": [3, 3, 3, 3], "total": 12},
                ],
            },
            "total": 20,
        },
        total_damage=20,
    )

    assert [
        (component["damage"], component["damage_type"], component["notation"])
        for component in components
    ] == [
        (8, "bludgeoning", "2d8"),
        (12, "cold", "4d6"),
    ]


def test_resolve_flame_strike_damage_components_from_name_mapping():
    components = resolve_spell_damage_components(
        "Flame Strike",
        {"name_en": "Flame Strike"},
        dice_detail={
            "base_roll": {
                "total": 18,
                "parts": [
                    {"notation": "4d6", "rolls": [2, 2, 2, 2], "total": 8},
                    {"notation": "4d6", "rolls": [3, 3, 2, 2], "total": 10},
                ],
            },
            "total": 18,
        },
        total_damage=18,
    )

    assert [component["damage_type"] for component in components] == ["fire", "radiant"]
    assert [component["damage"] for component in components] == [8, 10]


def test_apply_save_to_damage_components_halves_each_component():
    components = [
        {"damage": 9, "damage_type": "bludgeoning"},
        {"damage": 13, "damage_type": "cold"},
    ]

    scaled = apply_save_to_damage_components(
        components,
        save_result={"success": True},
        save_ability="dex",
        half_on_save=True,
        target={},
    )

    assert [component["damage"] for component in scaled] == [4, 6]
    assert [component["damage_before_save"] for component in scaled] == [9, 13]


def test_apply_save_to_damage_components_zeroes_on_success_without_half_damage():
    scaled = apply_save_to_damage_components(
        [{"damage": 7, "damage_type": "radiant"}],
        save_result={"success": True},
        save_ability="dex",
        half_on_save=False,
        target={},
    )

    assert scaled == []
