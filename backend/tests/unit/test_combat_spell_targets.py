import pytest
from fastapi import HTTPException


def test_collect_spell_target_ids_defaults_aoe_to_living_enemies():
    from api.combat.spell_targets import collect_spell_target_ids

    enemies = [
        {"id": "goblin-1", "hp_current": 7},
        {"id": "goblin-2", "hp_current": 0},
        {"id": "goblin-3", "hp_current": 2},
    ]

    assert collect_spell_target_ids(None, None, enemies, is_aoe=True) == ["goblin-1", "goblin-3"]


def test_parse_spell_range_ft_accepts_strings_and_numbers():
    from api.combat.spell_targets import parse_spell_range_ft

    assert parse_spell_range_ft("60 ft.") == 60
    assert parse_spell_range_ft(30) == 30
    assert parse_spell_range_ft("Self") == 0


def test_validate_spell_range_raises_for_out_of_range_target():
    from api.combat.spell_targets import validate_spell_range

    with pytest.raises(HTTPException) as exc:
        validate_spell_range(
            target_ids=["goblin-1"],
            positions={
                "caster-1": {"x": 0, "y": 0},
                "goblin-1": {"x": 4, "y": 0},
            },
            caster_id="caster-1",
            spell_range_ft=15,
        )

    assert exc.value.status_code == 400
    assert "目标超出法术射程" in exc.value.detail
