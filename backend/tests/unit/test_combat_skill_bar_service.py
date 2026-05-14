from types import SimpleNamespace

from services.combat_skill_bar_service import build_skill_bar


def _character(char_class, level=1, slots=None, resources=None):
    return SimpleNamespace(
        char_class=char_class,
        level=level,
        spell_slots=slots or {},
        derived={"class_resources": resources or {}},
    )


def test_build_skill_bar_returns_ten_slots_with_attack_first():
    bar = build_skill_bar(_character("Fighter", level=1))

    assert len(bar) == 10
    assert bar[0]["k"] == "atk"
    assert bar[-1]["key"] == "0"


def test_paladin_smite_reflects_first_level_slot_availability():
    bar = build_skill_bar(_character("Paladin", level=3, slots={"1st": 0}))

    smite = bar[1]
    assert smite["k"] == "smite"
    assert smite["available"] is False
    assert smite["reason"] == "需要 1 环法术位"


def test_rogue_skill_bar_keeps_sneak_attack_hint_scaling():
    bar = build_skill_bar(_character("Rogue", level=5))

    assert bar[1]["k"] == "sneak"
    assert "+3d6" in bar[1]["dmg_hint"]
