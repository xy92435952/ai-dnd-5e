import pytest

from services.lucky_feat_service import (
    LuckyFeatError,
    apply_lucky_to_attack_roll,
    apply_lucky_to_skill_check,
    spend_lucky_point,
)


class FakeCharacter:
    def __init__(self, *, feats=None, derived=None, class_resources=None):
        self.feats = feats or []
        self.derived = derived or {}
        self.class_resources = class_resources or {}


def test_spend_lucky_point_decrements_resource_and_returns_metadata():
    character = FakeCharacter(
        feats=[{"name": "Lucky"}],
        class_resources={"lucky_points_remaining": 2},
    )

    lucky = spend_lucky_point(
        character,
        d20_before=3,
        lucky_d20_value=17,
        context="skill_check",
    )

    assert character.class_resources["lucky_points_remaining"] == 1
    assert lucky == {
        "type": "lucky",
        "spent": True,
        "context": "skill_check",
        "d20_before": 3,
        "d20_after": 17,
        "lucky_points_remaining": 1,
    }


def test_spend_lucky_point_rejects_character_without_lucky():
    character = FakeCharacter(class_resources={})

    with pytest.raises(LuckyFeatError) as exc:
        spend_lucky_point(
            character,
            d20_before=3,
            lucky_d20_value=17,
            context="skill_check",
        )

    assert exc.value.status_code == 400
    assert "Lucky feat" in exc.value.detail
    assert character.class_resources == {}


def test_spend_lucky_point_rejects_empty_resource():
    character = FakeCharacter(
        feats=[{"name": "Lucky"}],
        class_resources={"lucky_points_remaining": 0},
    )

    with pytest.raises(LuckyFeatError) as exc:
        spend_lucky_point(
            character,
            d20_before=3,
            lucky_d20_value=17,
            context="attack_roll",
        )

    assert exc.value.status_code == 400
    assert "No Lucky points" in exc.value.detail
    assert character.class_resources["lucky_points_remaining"] == 0


def test_apply_lucky_to_skill_check_recomputes_total():
    result = {
        "d20": 2,
        "modifier": 5,
        "condition_modifier": 1,
        "total": 8,
        "success": False,
    }
    lucky = {
        "type": "lucky",
        "spent": True,
        "context": "skill_check",
        "d20_before": 2,
        "d20_after": 14,
        "lucky_points_remaining": 0,
    }

    updated = apply_lucky_to_skill_check(result, lucky=lucky, dc=20)

    assert updated["d20"] == 14
    assert updated["total"] == 20
    assert updated["success"] is True
    assert updated["lucky"] == lucky


def test_apply_lucky_to_attack_roll_recomputes_hit_and_crit_flags():
    attack = {
        "d20": 2,
        "attack_bonus": 5,
        "condition_modifier": 0,
        "attack_total": 7,
        "target_ac": 12,
        "hit": False,
        "is_crit": False,
        "is_fumble": False,
    }
    lucky = {
        "type": "lucky",
        "spent": True,
        "context": "attack_roll",
        "d20_before": 2,
        "d20_after": 20,
        "lucky_points_remaining": 0,
    }

    updated = apply_lucky_to_attack_roll(attack, lucky=lucky, crit_threshold=20)

    assert updated["d20"] == 20
    assert updated["attack_total"] == 25
    assert updated["hit"] is True
    assert updated["is_crit"] is True
    assert updated["is_fumble"] is False
    assert updated["d20_selection"] == "lucky"
    assert updated["lucky"] == lucky
