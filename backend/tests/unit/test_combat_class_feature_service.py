from types import SimpleNamespace

import pytest

from services.combat_class_feature_service import (
    CombatClassFeatureError,
    resolve_combat_class_feature,
)
from services.combat_service import CombatService


def _character(**overrides):
    defaults = {
        "name": "阿尔文",
        "char_class": "Fighter",
        "level": 2,
        "hp_current": 5,
        "derived": {"hp_max": 20, "ability_modifiers": {"wis": 2}},
        "class_resources": {},
        "conditions": [],
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _combat():
    return SimpleNamespace(turn_states={})


def _turn_state(**overrides):
    state = {
        "action_used": True,
        "bonus_action_used": False,
        "reaction_used": False,
        "movement_used": 0,
        "movement_max": 6,
        "attacks_made": 1,
    }
    state.update(overrides)
    return state


@pytest.fixture(autouse=True)
def _patch_flag_modified(monkeypatch):
    monkeypatch.setattr(
        "services.combat_turn_state_service.flag_modified",
        lambda *_args: None,
    )


def test_second_wind_heals_and_spends_bonus_action():
    player = _character()

    result = resolve_combat_class_feature(
        feature="second_wind",
        player=player,
        player_id="hero",
        combat=_combat(),
        turn_state=_turn_state(),
        combat_service=CombatService(),
        roll_dice_fn=lambda notation: {"rolls": [4], "total": 6},
    )

    assert player.hp_current == 11
    assert result.class_resources["second_wind_used"] is True
    assert result.turn_state["bonus_action_used"] is True
    assert result.dice_roll["faces"] == 10


def test_action_surge_resets_action_and_attack_count():
    player = _character(class_resources={})

    result = resolve_combat_class_feature(
        feature="action_surge",
        player=player,
        player_id="hero",
        combat=_combat(),
        turn_state=_turn_state(action_used=True, attacks_made=1),
        combat_service=CombatService(),
        roll_dice_fn=lambda *_args: (_ for _ in ()).throw(AssertionError("should not roll")),
    )

    assert result.class_resources["action_surge_used"] is True
    assert result.turn_state["action_used"] is False
    assert result.turn_state["attacks_made"] == 0


def test_tides_of_chaos_marks_next_d20_advantage():
    player = _character(char_class="Sorcerer", class_resources={})

    result = resolve_combat_class_feature(
        feature="tides_of_chaos",
        player=player,
        player_id="hero",
        combat=_combat(),
        turn_state=_turn_state(),
        combat_service=CombatService(),
        roll_dice_fn=lambda *_args: (_ for _ in ()).throw(AssertionError("should not roll")),
    )

    assert result.class_resources["tides_of_chaos_used"] is True
    assert result.turn_state["tides_of_chaos_active"] is True
    assert "获得优势" in result.narration


def test_rejects_wrong_class_feature():
    player = _character(char_class="Wizard")

    with pytest.raises(CombatClassFeatureError) as exc:
        resolve_combat_class_feature(
            feature="second_wind",
            player=player,
            player_id="hero",
            combat=_combat(),
            turn_state=_turn_state(),
            combat_service=CombatService(),
            roll_dice_fn=lambda *_args: {"rolls": [1], "total": 1},
        )

    assert exc.value.status_code == 400
    assert "只有战士" in exc.value.detail
