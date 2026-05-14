import pytest

from services.character_spell_service import CharacterSpellError, build_prepared_spells_update


def test_build_prepared_spells_update_accepts_known_spells_under_limit():
    result = build_prepared_spells_update(
        known_spells=["magic-missile", "shield"],
        requested_spells=["magic-missile"],
        level=1,
        derived={
            "spell_ability": "int",
            "ability_modifiers": {"int": 3},
        },
    )

    assert result == {
        "prepared_spells": ["magic-missile"],
        "max_prepared": 4,
    }


def test_build_prepared_spells_update_rejects_unknown_spell():
    with pytest.raises(CharacterSpellError) as exc:
        build_prepared_spells_update(
            known_spells=["magic-missile"],
            requested_spells=["shield"],
            level=1,
            derived={},
        )

    assert exc.value.status_code == 400
    assert "不在已知法术列表" in exc.value.detail


def test_build_prepared_spells_update_rejects_too_many_spells():
    with pytest.raises(CharacterSpellError) as exc:
        build_prepared_spells_update(
            known_spells=["a", "b", "c"],
            requested_spells=["a", "b", "c"],
            level=1,
            derived={
                "spell_ability": "wis",
                "ability_modifiers": {"wis": 1},
            },
        )

    assert exc.value.status_code == 400
    assert "已备法术上限为 2" in exc.value.detail
