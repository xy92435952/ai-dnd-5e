from services.combat_grapple_drag_service import (
    apply_grapple_drag_positions,
    build_grapple_drag_result,
)


def test_build_grapple_drag_result_moves_grappled_target_with_actor():
    positions = {
        "hero-1": {"x": 5, "y": 5},
        "enemy-1": {"x": 6, "y": 5},
    }

    result = build_grapple_drag_result(
        actor_id="hero-1",
        actor_from={"x": 5, "y": 5},
        actor_to={"x": 7, "y": 5},
        positions=positions,
        targets=[{
            "id": "enemy-1",
            "name": "Training Duelist",
            "conditions": ["grappled"],
            "condition_durations": {"grappled": {"source_id": "hero-1"}},
        }],
    )

    assert result == {
        "type": "grapple_drag",
        "actor_id": "hero-1",
        "distance_ft": 10,
        "steps": 2,
        "movement_cost": 4,
        "targets": [{
            "target_id": "enemy-1",
            "target_name": "Training Duelist",
            "from": {"x": 6, "y": 5},
            "to": {"x": 8, "y": 5},
            "distance_ft": 10,
            "steps": 2,
            "applied": True,
        }],
        "applied": True,
    }
    assert apply_grapple_drag_positions(positions, result)["enemy-1"] == {"x": 8, "y": 5}


def test_build_grapple_drag_result_blocks_occupied_destination():
    result = build_grapple_drag_result(
        actor_id="hero-1",
        actor_from={"x": 5, "y": 5},
        actor_to={"x": 7, "y": 5},
        positions={
            "hero-1": {"x": 5, "y": 5},
            "enemy-1": {"x": 6, "y": 5},
            "enemy-2": {"x": 8, "y": 5},
        },
        targets=[{
            "id": "enemy-1",
            "name": "Training Duelist",
            "conditions": ["grappled"],
            "condition_durations": {"grappled": {"source_id": "hero-1"}},
        }],
    )

    assert result["applied"] is False
    assert result["blocked_reason"] == "occupied"
    assert result["targets"][0]["blocked_reason"] == "occupied"


def test_build_grapple_drag_result_ignores_other_grapple_sources():
    result = build_grapple_drag_result(
        actor_id="hero-1",
        actor_from={"x": 5, "y": 5},
        actor_to={"x": 6, "y": 5},
        positions={
            "hero-1": {"x": 5, "y": 5},
            "enemy-1": {"x": 6, "y": 5},
        },
        targets=[{
            "id": "enemy-1",
            "name": "Training Duelist",
            "conditions": ["grappled"],
            "condition_durations": {"grappled": {"source_id": "other-hero"}},
        }],
    )

    assert result is None
