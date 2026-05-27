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
        hp_current=8,
        death_saves=None,
        conditions=[],
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
        hp_current=8,
        death_saves=None,
        conditions=[],
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


@pytest.mark.asyncio
async def test_concentration_check_passes_exhaustion_state_to_rule_service(monkeypatch):
    captured = {}
    char = SimpleNamespace(
        name="Hero",
        concentration="Bless",
        hp_current=8,
        death_saves=None,
        conditions=["exhaustion"],
        condition_durations={"exhaustion_level": 3},
        derived={"ability_modifiers": {"con": 2}},
        proficient_saves=[],
    )

    def fake_check_concentration(**kwargs):
        captured["character_dict"] = kwargs["character_dict"]
        return {
            "spell_name": "Bless",
            "dc": 10,
            "broke": False,
            "roll_result": {
                "d20": 12,
                "modifier": 2,
                "total": 14,
                "disadvantage": True,
                "exhaustion_disadvantage": True,
            },
        }

    monkeypatch.setattr(
        "services.combat_concentration_service.svc.check_concentration",
        fake_check_concentration,
    )

    log = await do_concentration_check(char, damage=12, session_id="sess")

    assert captured["character_dict"]["condition_durations"] == {"exhaustion_level": 3}
    assert captured["character_dict"]["conditions"] == ["exhaustion"]
    assert log.dice_result["disadvantage"] is True
    assert log.dice_result["exhaustion_disadvantage"] is True


@pytest.mark.asyncio
async def test_concentration_breaks_automatically_at_zero_hp():
    char = SimpleNamespace(
        name="Hero",
        concentration="Bless",
        hp_current=0,
        death_saves={"successes": 0, "failures": 0, "stable": False},
        conditions=["unconscious"],
        derived={},
        proficient_saves=[],
    )

    log = await do_concentration_check(char, damage=1, session_id="sess")

    assert char.concentration is None
    assert log.session_id == "sess"
    assert log.dice_result["broke"] is True
    assert log.dice_result["automatic"] is True
    assert log.dice_result["reason"] == "incapacitated"
    assert "dying" in log.dice_result["reasons"]
    assert "unconscious" in log.dice_result["reasons"]


@pytest.mark.asyncio
async def test_concentration_breaks_automatically_when_stunned():
    char = SimpleNamespace(
        name="Hero",
        concentration="Bless",
        hp_current=8,
        death_saves=None,
        conditions=["stunned"],
        derived={},
        proficient_saves=[],
    )

    log = await do_concentration_check(char, damage=0, session_id="sess")

    assert char.concentration is None
    assert log.dice_result["automatic"] is True
    assert log.dice_result["reasons"] == ["stunned"]
