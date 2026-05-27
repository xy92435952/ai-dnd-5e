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
        "condition_durations": {},
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


def test_second_wind_caps_at_exhaustion_hp_max():
    player = _character(
        hp_current=4,
        conditions=["exhaustion"],
        condition_durations={"exhaustion_level": 4},
    )

    result = resolve_combat_class_feature(
        feature="second_wind",
        player=player,
        player_id="hero",
        combat=_combat(),
        turn_state=_turn_state(),
        combat_service=CombatService(),
        roll_dice_fn=lambda notation: {"rolls": [10], "total": 12},
    )

    assert player.hp_current == 10
    assert result.hp_max == 10


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


def test_cunning_action_dash_adds_base_movement_not_current_total_again():
    player = _character(char_class="Rogue", level=2)

    result = resolve_combat_class_feature(
        feature="cunning_action_dash",
        player=player,
        player_id="hero",
        combat=_combat(),
        turn_state=_turn_state(movement_max=12, base_movement_max=6),
        combat_service=CombatService(),
        roll_dice_fn=lambda *_args: (_ for _ in ()).throw(AssertionError("should not roll")),
    )

    assert result.turn_state["bonus_action_used"] is True
    assert result.turn_state["movement_max"] == 18


def test_class_feature_rejects_incapacitated_actor():
    player = _character(conditions=["paralyzed"])

    with pytest.raises(CombatClassFeatureError) as exc:
        resolve_combat_class_feature(
            feature="action_surge",
            player=player,
            player_id="hero",
            combat=_combat(),
            turn_state=_turn_state(),
            combat_service=CombatService(),
            roll_dice_fn=lambda *_args: (_ for _ in ()).throw(AssertionError("should not roll")),
        )

    assert exc.value.status_code == 400
    assert "paralyzed" in exc.value.detail


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


def test_fighting_spirit_grants_real_temporary_hp():
    player = _character(
        char_class="Fighter",
        level=5,
        derived={"hp_max": 20, "ability_modifiers": {"wis": 2}, "subclass_effects": {"fighting_spirit": True}},
        class_resources={"fighting_spirit_remaining": 1},
    )

    result = resolve_combat_class_feature(
        feature="fighting_spirit",
        player=player,
        player_id="hero",
        combat=_combat(),
        turn_state=_turn_state(),
        combat_service=CombatService(),
        roll_dice_fn=lambda *_args: (_ for _ in ()).throw(AssertionError("should not roll")),
    )

    assert result.class_resources["fighting_spirit_remaining"] == 0
    assert result.class_resources["temporary_hp"] == 5
    assert result.class_resources["temporary_hp_source"] == "fighting_spirit"
    assert result.temporary_hp == 5


def test_symbiotic_entity_grants_real_temporary_hp_and_preserves_higher_existing_pool():
    player = _character(
        char_class="Druid",
        level=3,
        derived={
            "hp_max": 20,
            "ability_modifiers": {"wis": 2},
            "subclass_effects": {"symbiotic_entity": True, "symbiotic_temp_hp": 12},
        },
        class_resources={
            "wild_shape_remaining": 1,
            "temporary_hp": 15,
            "temporary_hp_source": "armor_of_agathys",
            "armor_of_agathys_damage": 15,
        },
        conditions=["armor_of_agathys"],
        condition_durations={"armor_of_agathys": 600},
    )

    result = resolve_combat_class_feature(
        feature="symbiotic_entity",
        player=player,
        player_id="hero",
        combat=_combat(),
        turn_state=_turn_state(),
        combat_service=CombatService(),
        roll_dice_fn=lambda *_args: (_ for _ in ()).throw(AssertionError("should not roll")),
    )

    assert result.class_resources["wild_shape_remaining"] == 0
    assert result.class_resources["symbiotic_entity_active"] is True
    assert result.class_resources["temporary_hp"] == 15
    assert result.class_resources["temporary_hp_source"] == "armor_of_agathys"
    assert result.temporary_hp == 15


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
