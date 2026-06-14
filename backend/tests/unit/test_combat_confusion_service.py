from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _disable_sqlalchemy_flags(monkeypatch):
    monkeypatch.setattr("services.combat_turn_state_service.flag_modified", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("services.combat_confusion_service.flag_modified", lambda *_args, **_kwargs: None)


def test_confused_blocks_reactions_without_full_incapacitation():
    from services.combat_action_rules_service import (
        can_take_reaction,
        validate_can_take_action,
        validate_can_take_reaction,
    )

    actor = {"hp_current": 10, "conditions": ["confused"]}

    validate_can_take_action(actor)
    assert can_take_reaction(actor) is False
    with pytest.raises(Exception) as exc:
        validate_can_take_reaction(actor)
    assert "confused" in str(exc.value)


def test_confusion_turn_roll_one_spends_control_and_moves_random_direction():
    from services.combat_confusion_service import apply_confusion_turn_start

    combat = SimpleNamespace(
        round_number=2,
        current_turn_index=1,
        turn_states={
            "hero": {
                "action_used": False,
                "bonus_action_used": False,
                "reaction_used": False,
                "movement_used": 0,
                "movement_max": 3,
            }
        },
        entity_positions={
            "hero": {"x": 1, "y": 1},
            "blocker": {"x": 5, "y": 1},
        },
    )

    result = apply_confusion_turn_start(
        combat,
        "hero",
        {"conditions": ["confused"]},
        d10_value=1,
        direction_index=2,
    )

    assert result["outcome"] == "random_move"
    assert result["movement"]["direction_label"] == "east"
    assert result["movement"]["steps"] == 3
    assert combat.entity_positions["hero"] == {"x": 4, "y": 1}
    turn_state = combat.turn_states["hero"]
    assert turn_state["action_used"] is True
    assert turn_state["bonus_action_used"] is True
    assert turn_state["movement_used"] == 3
    assert turn_state["reaction_blocked"] is True
    assert turn_state["confusion_turn"]["roll"] == 1


def test_confusion_turn_roll_two_to_six_blocks_actions_and_movement():
    from services.combat_confusion_service import apply_confusion_turn_start

    combat = SimpleNamespace(
        round_number=1,
        current_turn_index=0,
        turn_states={
            "enemy": {
                "action_used": False,
                "bonus_action_used": False,
                "reaction_used": False,
                "movement_used": 1,
                "movement_max": 6,
            }
        },
        entity_positions={"enemy": {"x": 8, "y": 8}},
    )

    result = apply_confusion_turn_start(
        combat,
        "enemy",
        {"conditions": ["confused"]},
        d10_value=4,
    )

    assert result["outcome"] == "no_action"
    assert result["action_blocked"] is True
    assert result["movement_blocked"] is True
    assert combat.turn_states["enemy"]["action_used"] is True
    assert combat.turn_states["enemy"]["bonus_action_used"] is True
    assert combat.turn_states["enemy"]["movement_used"] == 6


def test_confusion_turn_roll_nine_to_ten_keeps_action_available():
    from services.combat_confusion_service import apply_confusion_turn_start

    combat = SimpleNamespace(
        round_number=1,
        current_turn_index=0,
        turn_states={
            "enemy": {
                "action_used": False,
                "bonus_action_used": False,
                "reaction_used": False,
                "movement_used": 0,
                "movement_max": 6,
            }
        },
        entity_positions={"enemy": {"x": 8, "y": 8}},
    )

    result = apply_confusion_turn_start(
        combat,
        "enemy",
        {"conditions": ["confused"]},
        d10_value=10,
    )

    assert result["outcome"] == "act_normally"
    assert result["action_blocked"] is False
    assert result["movement_blocked"] is False
    assert combat.turn_states["enemy"]["action_used"] is False
    assert combat.turn_states["enemy"]["movement_used"] == 0
    assert combat.turn_states["enemy"]["reaction_blocked"] is True


def test_confusion_end_of_turn_save_success_removes_condition_and_metadata():
    from services.combat_confusion_service import resolve_confusion_end_of_turn_save

    actor = {
        "id": "enemy-1",
        "name": "Confused Guard",
        "conditions": ["confused", "poisoned"],
        "condition_durations": {
            "confused": {"duration": 5, "save_dc": 12, "save_ability": "wis"},
            "confusion_target_id": "hero-1",
            "confusion_end_save_d20": 20,
            "poisoned": 3,
        },
        "derived": {"saving_throws": {"wis": 1}},
    }

    result = resolve_confusion_end_of_turn_save(actor)

    assert result["ended"] is True
    assert result["save"]["total"] == 21
    assert actor["conditions"] == ["poisoned"]
    assert actor["condition_durations"] == {"poisoned": 3}
    assert result["removed_conditions"] == ["confused"]
    assert result["target_state"]["conditions"] == ["poisoned"]


def test_confusion_end_of_turn_save_failure_keeps_condition():
    from services.combat_confusion_service import resolve_confusion_end_of_turn_save

    actor = {
        "id": "enemy-1",
        "name": "Confused Guard",
        "conditions": ["confused"],
        "condition_durations": {
            "confused": {"duration": 5, "save_dc": 20, "save_ability": "wis"},
        },
        "derived": {"saving_throws": {"wis": 0}},
    }

    result = resolve_confusion_end_of_turn_save(actor, d20_value=1)

    assert result["ended"] is False
    assert result["save"]["success"] is False
    assert actor["conditions"] == ["confused"]
    assert actor["condition_durations"]["confused"]["duration"] == 5


def test_confusion_duration_tick_handles_metadata_and_cleans_on_expiry():
    from services.combat_condition_duration_service import tick_enemy_conditions

    enemy = {
        "conditions": ["confused"],
        "condition_durations": {
            "confused": {"duration": 2, "save_dc": 15, "save_ability": "wis"},
            "confusion_target_id": "hero-1",
        },
    }

    assert tick_enemy_conditions(enemy) == []
    assert enemy["conditions"] == ["confused"]
    assert enemy["condition_durations"]["confused"]["duration"] == 1
    assert enemy["condition_durations"]["confusion_target_id"] == "hero-1"

    assert tick_enemy_conditions(enemy) == ["confused"]
    assert enemy["conditions"] == []
    assert enemy["condition_durations"] == {}


async def test_confusion_roll_seven_to_eight_resolves_random_melee_damage():
    from services.combat_confusion_service import (
        apply_confusion_turn_start,
        resolve_confusion_random_melee_attack,
    )

    class FakeDb:
        def add(self, _log):
            pass

        async def get(self, _model, _entity_id):
            return None

    class FakeCombatService:
        def resolve_melee_attack(self, **_kwargs):
            return SimpleNamespace(
                attack_roll={
                    "d20": 12,
                    "attack_bonus": 99,
                    "attack_total": 111,
                    "target_ac": 10,
                    "hit": True,
                    "is_crit": False,
                    "is_fumble": False,
                },
                damage=7,
                damage_roll={"total": 7, "rolls": [4], "modifier": 3},
            )

    enemies = [{
        "id": "enemy-1",
        "name": "Confused Target",
        "hp_current": 40,
        "derived": {"hp_max": 40, "ac": 10},
        "conditions": [],
    }]
    session = SimpleNamespace(id="session-1", game_state={"enemies": enemies})
    combat = SimpleNamespace(
        round_number=1,
        current_turn_index=0,
        turn_states={
            "hero": {
                "action_used": False,
                "bonus_action_used": False,
                "reaction_used": False,
                "movement_used": 0,
                "movement_max": 6,
            }
        },
        entity_positions={
            "hero": {"x": 1, "y": 1},
            "enemy-1": {"x": 2, "y": 1},
        },
    )
    actor = SimpleNamespace(
        id="hero",
        name="Hero",
        hp_current=20,
        derived={"attack_bonus": 99, "hit_die": 8, "ability_modifiers": {"str": 3}},
        conditions=["confused"],
        condition_durations={"confusion_target_id": "enemy-1"},
    )

    confusion_turn = apply_confusion_turn_start(combat, "hero", actor, d10_value=8)
    attack = await resolve_confusion_random_melee_attack(
        FakeDb(),
        session=session,
        combat=combat,
        entity_id="hero",
        actor=actor,
        enemies=enemies,
        confusion_turn=confusion_turn,
        combat_service=FakeCombatService(),
    )

    assert attack["applied"] is True
    assert attack["target_id"] == "enemy-1"
    assert attack["hit"] is True
    assert attack["damage"] == 7
    assert enemies[0]["hp_current"] == 33
    stored = combat.turn_states["hero"]["confusion_turn"]["attack"]
    assert stored["target_new_hp"] == 33
