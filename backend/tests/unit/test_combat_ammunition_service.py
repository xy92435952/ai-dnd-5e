import pytest

from services.combat_ammunition_service import (
    choose_attack_weapon,
    consume_attack_weapon_resource,
)
from services.combat_attack_roll_service import CombatAttackRollError


class FakeCharacter:
    def __init__(self, equipment):
        self.equipment = equipment


def make_weapons():
    return [
        {
            "name": "Longsword",
            "damage": "1d8",
            "type": "martial_melee",
            "properties": ["versatile(1d10)"],
            "equipped": True,
        },
        {
            "name": "Javelin",
            "damage": "1d6",
            "type": "simple_melee",
            "properties": ["thrown(30/120)"],
            "equipped": False,
        },
        {
            "name": "Longbow",
            "damage": "1d8",
            "type": "martial_ranged",
            "properties": ["ammunition", "range(150/600)", "two-handed"],
            "equipped": False,
            "ammo": 3,
        },
    ]


def test_choose_attack_weapon_prefers_named_melee_weapon():
    equipment = {"weapons": make_weapons()}

    selected = choose_attack_weapon(equipment, is_ranged=False, weapon_name="Javelin")

    assert selected["name"] == "Javelin"


def test_consume_attack_weapon_resource_uses_named_ranged_weapon_and_ammo():
    character = FakeCharacter({"weapons": make_weapons()})

    result = consume_attack_weapon_resource(
        character,
        is_ranged=True,
        weapon_name="Longbow",
    )

    assert result.weapon_name == "Longbow"
    assert result.resource_type == "ammunition"
    assert result.consumed is True
    assert result.ammo_remaining == 2
    assert character.equipment["weapons"][2]["ammo"] == 2


def test_consume_attack_weapon_resource_rejects_named_weapon_for_wrong_mode():
    character = FakeCharacter({"weapons": make_weapons()})

    with pytest.raises(CombatAttackRollError) as exc:
        consume_attack_weapon_resource(
            character,
            is_ranged=True,
            weapon_name="Longsword",
        )

    assert exc.value.status_code == 400
    assert "Selected weapon is not available: Longsword" in exc.value.detail
