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


def test_parse_spell_range_tiles_treats_numbers_as_grid_tiles_and_strings_as_feet():
    from api.combat.spell_targets import parse_spell_range_tiles

    assert parse_spell_range_tiles(12) == 12
    assert parse_spell_range_tiles("60 ft.") == 12
    assert parse_spell_range_tiles("Self") == 0


def test_validate_spell_range_raises_for_out_of_range_string_feet():
    from api.combat.spell_targets import validate_spell_range

    with pytest.raises(HTTPException) as exc:
        validate_spell_range(
            target_ids=["goblin-1"],
            positions={
                "caster-1": {"x": 0, "y": 0},
                "goblin-1": {"x": 4, "y": 0},
            },
            caster_id="caster-1",
            spell_range_ft="15 ft.",
        )

    assert exc.value.status_code == 400
    assert "目标超出法术射程" in exc.value.detail


def test_validate_spell_range_treats_numeric_spell_data_as_tiles():
    from api.combat.spell_targets import validate_spell_range

    validate_spell_range(
        target_ids=["goblin-1"],
        positions={
            "caster-1": {"x": 0, "y": 0},
            "goblin-1": {"x": 12, "y": 0},
        },
        caster_id="caster-1",
        spell_range_ft=12,
    )

    with pytest.raises(HTTPException) as exc:
        validate_spell_range(
            target_ids=["goblin-1"],
            positions={
                "caster-1": {"x": 0, "y": 0},
                "goblin-1": {"x": 13, "y": 0},
            },
            caster_id="caster-1",
            spell_range_ft=12,
        )

    assert "射程60ft" in exc.value.detail
