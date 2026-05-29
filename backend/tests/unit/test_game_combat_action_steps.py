from types import SimpleNamespace

from services.combat_service import AttackResult


class FakeCombatService:
    def resolve_melee_attack(self, **kwargs):
        self.last_attack_kwargs = kwargs
        return AttackResult(
            attack_roll={
                "d20": 15,
                "attack_total": 20,
                "target_ac": 12,
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
            },
            damage=4,
            damage_roll={"formula": "1d6", "rolls": [4], "total": 4},
            narration="hit",
        )

    def apply_damage(self, current_hp, damage, _max_hp):
        return max(0, current_hp - damage)

    def apply_damage_with_resistance(self, damage, *_args):
        return damage


def test_execute_move_action_blocks_speed_zero_condition():
    from services.game_combat_action_steps import execute_move_action

    positions = {
        "hero-1": {"x": 0, "y": 0},
        "goblin-1": {"x": 5, "y": 0},
    }
    combat_state = SimpleNamespace(entity_positions=positions)
    turn_state = {"movement_used": 0, "movement_max": 6}
    action_results = []
    executed_action_types = []

    move_remaining = execute_move_action(
        combat_state=combat_state,
        positions=positions,
        player_id="hero-1",
        turn_state=turn_state,
        move_remaining=6,
        action={"type": "move", "target_id": "goblin-1"},
        actor_conditions=["被擒抱"],
        action_results=action_results,
        executed_action_types=executed_action_types,
        move_toward=lambda *_args: {"x": 1, "y": 0, "steps": 1},
        save_turn_state=lambda *_args: None,
    )

    assert move_remaining == 6
    assert positions["hero-1"] == {"x": 0, "y": 0}
    assert turn_state["movement_used"] == 0
    assert action_results == ["速度为 0，无法移动"]
    assert executed_action_types == ["move_blocked"]


def test_execute_attack_action_consumes_guiding_bolt_and_applies_hex(monkeypatch):
    from services import combat_damage_bonus_service
    from services.game_combat_action_steps import execute_attack_action

    monkeypatch.setattr(combat_damage_bonus_service, "roll_dice", lambda expr: {"formula": expr, "rolls": [3], "total": 3})
    enemies = [{
        "id": "goblin-1",
        "name": "Goblin",
        "hp_current": 12,
        "derived": {"hp_max": 12, "ac": 12},
        "conditions": ["guiding_bolt", "hexed"],
        "condition_durations": {"guiding_bolt": 1, "hexed": 600},
    }]
    state = {"enemies": enemies}
    service = FakeCombatService()
    action_results = []
    dice_display = []
    executed_action_types = []

    total_damage = execute_attack_action(
        session=SimpleNamespace(game_state=state),
        combat_state=SimpleNamespace(),
        positions={"hero-1": {"x": 0, "y": 0}, "goblin-1": {"x": 1, "y": 0}},
        state=state,
        enemies=enemies,
        player_id="hero-1",
        player_derived={"attack_bonus": 5, "hit_die": 6},
        player_conditions=[],
        player_concentration="Hex",
        action={"type": "attack", "target_id": "goblin-1"},
        action_results=action_results,
        dice_display=dice_display,
        executed_action_types=executed_action_types,
        combat_service=service,
        check_attack_range=lambda *_args: (True, 1, None),
        distance=lambda *_args: 1,
    )

    assert total_damage == 7
    assert enemies[0]["hp_current"] == 5
    assert enemies[0]["conditions"] == ["hexed"]
    assert enemies[0]["condition_durations"] == {"hexed": 600}
    assert service.last_attack_kwargs["advantage"] is True
    assert service.last_attack_kwargs["target_conditions"] == ["hexed"]
    assert dice_display[-1]["total"] == 7
    assert any("Hex+3" in item for item in action_results)
    assert executed_action_types == ["attack"]


def test_execute_parsed_actions_allows_movement_but_blocks_spent_standard_action():
    from services.game_combat_action_executor import (
        ACTION_ALREADY_USED_MESSAGE,
        execute_parsed_combat_actions,
    )

    actor = SimpleNamespace(conditions=[])
    positions = {
        "hero-1": {"x": 0, "y": 0},
        "goblin-1": {"x": 4, "y": 0},
    }
    combat_state = SimpleNamespace(entity_positions=positions, turn_states={})
    turn_state = {
        "action_used": True,
        "movement_used": 4,
        "movement_max": 6,
        "base_movement_max": 6,
    }
    saved_states = []

    def save_turn_state(_combat, _entity_id, state):
        saved_states.append(dict(state))

    result = execute_parsed_combat_actions(
        parsed_actions=[
            {"type": "move", "target_id": "goblin-1"},
            {"type": "attack", "target_id": "goblin-1"},
        ],
        session=SimpleNamespace(game_state={"enemies": [{"id": "goblin-1", "hp_current": 8}]}),
        combat_state=combat_state,
        positions=positions,
        state={"enemies": [{"id": "goblin-1", "hp_current": 8}]},
        enemies=[{"id": "goblin-1", "hp_current": 8}],
        player=actor,
        player_id="hero-1",
        player_derived={},
        turn_state=turn_state,
        move_remaining=2,
        combat_service=FakeCombatService(),
        move_toward=lambda *_args: {"x": 2, "y": 0, "steps": 2},
        save_turn_state=save_turn_state,
        check_attack_range=lambda *_args: (True, 1, None),
        distance=lambda *_args: 1,
    )

    assert positions["hero-1"] == {"x": 2, "y": 0}
    assert turn_state["movement_used"] == 6
    assert turn_state["action_used"] is True
    assert result.total_damage == 0
    assert result.dice_display == []
    assert result.errors == [ACTION_ALREADY_USED_MESSAGE]
    assert result.executed_action_types == ["move", "action_blocked"]
    assert saved_states == [turn_state]
