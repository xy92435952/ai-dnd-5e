from services.combat_movement_cost_service import (
    build_movement_cost_breakdown,
    build_movement_path_cells,
)


def test_build_movement_path_cells_includes_destination_and_intermediate_cells():
    assert build_movement_path_cells({"x": 5, "y": 5}, {"x": 7, "y": 5}) == [
        {"cell": "6_5", "x": 6, "y": 5},
        {"cell": "7_5", "x": 7, "y": 5},
    ]


def test_difficult_terrain_adds_one_extra_cost_per_entered_cell():
    breakdown = build_movement_cost_breakdown(
        {
            "6_5": {"terrain": "difficult", "label": "Mud slick"},
            "7_5": "difficult_terrain",
        },
        {"x": 5, "y": 5},
        {"x": 7, "y": 5},
    )

    assert breakdown["steps"] == 2
    assert breakdown["base_cost"] == 2
    assert breakdown["difficult_terrain_extra"] == 2
    assert breakdown["movement_cost"] == 4
    assert breakdown["difficult_terrain_cells"] == [
        {"cell": "6_5", "terrain": "difficult", "label": "Mud slick", "extra_cost": 1},
        {"cell": "7_5", "terrain": "difficult_terrain", "label": "Difficult terrain", "extra_cost": 1},
    ]


def test_difficult_terrain_extra_stacks_on_custom_base_cost():
    breakdown = build_movement_cost_breakdown(
        {"6_5": "difficult"},
        {"x": 5, "y": 5},
        {"x": 6, "y": 5},
        base_cost=2,
    )

    assert breakdown["base_cost"] == 2
    assert breakdown["difficult_terrain_extra"] == 1
    assert breakdown["movement_cost"] == 3


def test_ignored_difficult_terrain_preserves_cells_without_extra_cost():
    breakdown = build_movement_cost_breakdown(
        {"6_5": {"terrain": "difficult", "label": "Mud slick"}},
        {"x": 5, "y": 5},
        {"x": 6, "y": 5},
        ignore_difficult_terrain=True,
    )

    assert breakdown["base_cost"] == 1
    assert breakdown["difficult_terrain_extra"] == 0
    assert breakdown["movement_cost"] == 1
    assert breakdown["ignores_difficult_terrain"] is True
    assert breakdown["difficult_terrain_cells"] == [{
        "cell": "6_5",
        "terrain": "difficult",
        "label": "Mud slick",
        "extra_cost": 0,
    }]
