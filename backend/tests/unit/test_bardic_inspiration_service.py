import pytest

from services.bardic_inspiration_service import (
    BardicInspirationError,
    apply_bardic_inspiration_to_attack_roll,
    apply_bardic_inspiration_to_skill_check,
    spend_bardic_inspiration,
)


class FakeCharacter:
    def __init__(self, *, class_resources=None):
        self.class_resources = class_resources or {}


def test_spend_bardic_inspiration_decrements_resource_and_returns_metadata():
    character = FakeCharacter(class_resources={
        "bardic_inspiration": {
            "die": "d8",
            "uses_remaining": 1,
            "source_character_id": "bard-1",
            "source_character_name": "Lyra",
        },
    })

    bardic = spend_bardic_inspiration(
        character,
        bardic_roll=6,
        context="skill_check",
    )

    assert character.class_resources["bardic_inspiration"]["uses_remaining"] == 0
    assert bardic == {
        "type": "bardic_inspiration",
        "spent": True,
        "context": "skill_check",
        "die": "d8",
        "roll": 6,
        "uses_remaining": 0,
        "source_character_id": "bard-1",
        "source_character_name": "Lyra",
    }


def test_spend_bardic_inspiration_rejects_empty_resource():
    character = FakeCharacter(class_resources={
        "bardic_inspiration": {"die": "d6", "uses_remaining": 0},
    })

    with pytest.raises(BardicInspirationError) as exc:
        spend_bardic_inspiration(character, bardic_roll=3, context="attack_roll")

    assert exc.value.status_code == 400
    assert "No Bardic Inspiration" in exc.value.detail


def test_spend_bardic_inspiration_rejects_roll_above_die_faces():
    character = FakeCharacter(class_resources={
        "bardic_inspiration": {"die": "d6", "uses_remaining": 1},
    })

    with pytest.raises(BardicInspirationError) as exc:
        spend_bardic_inspiration(character, bardic_roll=7, context="skill_check")

    assert exc.value.status_code == 400
    assert "between 1 and 6" in exc.value.detail
    assert character.class_resources["bardic_inspiration"]["uses_remaining"] == 1


def test_apply_bardic_inspiration_to_skill_check_recomputes_success():
    result = {
        "d20": 10,
        "modifier": 2,
        "condition_modifier": 0,
        "total": 12,
        "success": False,
    }
    bardic = {
        "type": "bardic_inspiration",
        "spent": True,
        "context": "skill_check",
        "die": "d8",
        "roll": 4,
        "uses_remaining": 0,
    }

    updated = apply_bardic_inspiration_to_skill_check(result, bardic_inspiration=bardic, dc=15)

    assert updated["total"] == 16
    assert updated["success"] is True
    assert updated["bardic_inspiration"]["total_before"] == 12
    assert updated["bardic_inspiration"]["total_after"] == 16


def test_apply_bardic_inspiration_to_attack_roll_recomputes_hit_without_changing_crit_flags():
    attack = {
        "d20": 10,
        "attack_bonus": 2,
        "condition_modifier": 0,
        "attack_total": 12,
        "target_ac": 15,
        "hit": False,
        "is_crit": False,
        "is_fumble": False,
    }
    bardic = {
        "type": "bardic_inspiration",
        "spent": True,
        "context": "attack_roll",
        "die": "d8",
        "roll": 4,
        "uses_remaining": 0,
    }

    updated = apply_bardic_inspiration_to_attack_roll(attack, bardic_inspiration=bardic)

    assert updated["attack_total"] == 16
    assert updated["hit"] is True
    assert updated["is_crit"] is False
    assert updated["is_fumble"] is False
    assert updated["roll_modifiers"] == [{"source": "bardic_inspiration", "value": 4, "die": "d8"}]
