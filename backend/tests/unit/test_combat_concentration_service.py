from types import SimpleNamespace

import pytest

from services.combat_concentration_service import do_concentration_check


@pytest.mark.asyncio
async def test_concentration_check_skips_without_concentration():
    char = SimpleNamespace(concentration=None)

    result = await do_concentration_check(char, damage=10, session_id="sess")

    assert result is None


@pytest.mark.asyncio
async def test_concentration_check_breaks_and_returns_log(monkeypatch):
    char = SimpleNamespace(
        name="艾琳",
        concentration="祝福",
        derived={},
        proficient_saves=[],
    )

    monkeypatch.setattr(
        "services.combat_concentration_service.svc.check_concentration",
        lambda **_kwargs: {
            "spell_name": "祝福",
            "dc": 10,
            "broke": True,
            "roll_result": {"d20": 3, "modifier": 1, "total": 4},
        },
    )

    log = await do_concentration_check(char, damage=12, session_id="sess")

    assert char.concentration is None
    assert log.session_id == "sess"
    assert "失去了【祝福】" in log.content
    assert log.dice_result["broke"] is True


@pytest.mark.asyncio
async def test_concentration_check_keeps_spell_on_success(monkeypatch):
    char = SimpleNamespace(
        name="艾琳",
        concentration="祝福",
        derived={},
        proficient_saves=[],
    )

    monkeypatch.setattr(
        "services.combat_concentration_service.svc.check_concentration",
        lambda **_kwargs: {
            "spell_name": "祝福",
            "dc": 10,
            "broke": False,
            "roll_result": {"d20": 15, "modifier": 1, "total": 16},
        },
    )

    log = await do_concentration_check(char, damage=12, session_id="sess")

    assert char.concentration == "祝福"
    assert "维持了【祝福】" in log.content
    assert log.dice_result["broke"] is False
