from types import SimpleNamespace

from services.combat_turn_state_service import (
    DEFAULT_TURN_STATE,
    get_turn_state,
    mobile_blocks_opportunity_from,
    record_mobile_dash_difficult_terrain_ignore,
    record_mobile_opportunity_safe_target,
    reset_turn_state,
    save_turn_state,
)


def test_get_turn_state_returns_default_copy():
    combat = SimpleNamespace(turn_states=None)

    state = get_turn_state(combat, "hero")
    state["action_used"] = True

    assert DEFAULT_TURN_STATE["action_used"] is False


def test_save_and_reset_turn_state_updates_combat_state(monkeypatch):
    monkeypatch.setattr(
        "services.combat_turn_state_service.flag_modified",
        lambda *_args: None,
    )
    combat = SimpleNamespace(turn_states={})

    save_turn_state(combat, "hero", {"action_used": True})
    assert combat.turn_states["hero"] == {"action_used": True}

    reset_turn_state(combat, "hero", attacks_max=2, movement_max=8)
    assert combat.turn_states["hero"]["action_used"] is False
    assert combat.turn_states["hero"]["attacks_max"] == 2
    assert combat.turn_states["hero"]["movement_max"] == 8


def test_record_mobile_opportunity_safe_target_tracks_mobile_melee_only():
    mobile_derived = {"feat_effects": {"Mobile": {"mobile": True}}}
    turn_state = {}

    updated = record_mobile_opportunity_safe_target(
        turn_state,
        "goblin-1",
        attacker_derived=mobile_derived,
        is_ranged=False,
    )
    updated = record_mobile_opportunity_safe_target(
        updated,
        "goblin-1",
        attacker_derived=mobile_derived,
        is_ranged=False,
    )

    assert updated["mobile_opportunity_safe_targets"] == ["goblin-1"]
    assert mobile_blocks_opportunity_from(updated, "goblin-1") is True
    assert mobile_blocks_opportunity_from(updated, "goblin-2") is False

    ranged_state = record_mobile_opportunity_safe_target(
        {},
        "goblin-1",
        attacker_derived=mobile_derived,
        is_ranged=True,
    )
    assert "mobile_opportunity_safe_targets" not in ranged_state

    no_feat_state = record_mobile_opportunity_safe_target(
        {},
        "goblin-1",
        attacker_derived={"feat_effects": {}},
        is_ranged=False,
    )
    assert "mobile_opportunity_safe_targets" not in no_feat_state


def test_reset_turn_state_clears_mobile_opportunity_safe_targets(monkeypatch):
    monkeypatch.setattr(
        "services.combat_turn_state_service.flag_modified",
        lambda *_args: None,
    )
    combat = SimpleNamespace(turn_states={
        "hero": {
            "mobile_opportunity_safe_targets": ["goblin-1"],
            "mobile_ignores_difficult_terrain": True,
        },
    })

    reset_turn_state(combat, "hero", attacks_max=1, movement_max=6)

    assert "mobile_opportunity_safe_targets" not in combat.turn_states["hero"]
    assert "mobile_ignores_difficult_terrain" not in combat.turn_states["hero"]


def test_record_mobile_dash_marks_difficult_terrain_ignore_for_mobile_only():
    mobile_derived = {"feat_effects": {"Mobile": {"mobile": True}}}

    mobile_state = record_mobile_dash_difficult_terrain_ignore(
        {},
        actor_derived=mobile_derived,
    )
    assert mobile_state["mobile_ignores_difficult_terrain"] is True

    normal_state = record_mobile_dash_difficult_terrain_ignore(
        {},
        actor_derived={"feat_effects": {}},
    )
    assert "mobile_ignores_difficult_terrain" not in normal_state
