from types import SimpleNamespace

from services.combat_wild_magic_service import (
    apply_wild_magic_mechanical_effect,
    resolve_wild_magic_for_spell,
)


def _surge(effect="你恢复 2d10 点生命值", mechanical=None):
    return {
        "index": 9,
        "effect": effect,
        "mechanical": mechanical or {"type": "heal", "dice": "2d10"},
    }


def test_wild_magic_skips_cantrips():
    result = resolve_wild_magic_for_spell(
        caster_name="术士",
        is_cantrip=True,
        derived={"subclass_effects": {"wild_magic": True}},
        class_resources={"tides_of_chaos_used": True},
        roll_dice=lambda *_args: (_ for _ in ()).throw(AssertionError("should not roll")),
        roll_wild_magic_surge=lambda: (_ for _ in ()).throw(AssertionError("should not surge")),
    )

    assert result.surge is None
    assert result.check is None


def test_forced_tides_of_chaos_surge_resets_resource():
    result = resolve_wild_magic_for_spell(
        caster_name="术士",
        is_cantrip=False,
        derived={"subclass_effects": {"wild_magic": True}},
        class_resources={"tides_of_chaos_used": True, "sorcery_points": 2},
        roll_dice=lambda *_args: (_ for _ in ()).throw(AssertionError("should not roll d20")),
        roll_wild_magic_surge=lambda: _surge("你周围30尺内每个生物都变得隐形"),
    )

    assert result.check == {"d20": "自动", "triggered": True, "forced": True, "surge_roll": 10}
    assert result.updated_class_resources == {"tides_of_chaos_used": False, "sorcery_points": 2}
    assert "混沌反噬" in result.log_content


def test_normal_d20_one_triggers_surge():
    result = resolve_wild_magic_for_spell(
        caster_name="伊芙",
        is_cantrip=False,
        derived={"subclass_effects": {"wild_magic": True}},
        class_resources={"tides_of_chaos_used": False},
        roll_dice=lambda notation: {"rolls": [1], "total": 1},
        roll_wild_magic_surge=lambda: _surge("你恢复 2d10 点生命值"),
    )

    assert result.check["triggered"] is True
    assert result.check["forced"] is False
    assert result.log_dice_result["type"] == "wild_magic_surge"
    assert "伊芙" in result.narration_append


def test_normal_d20_other_than_one_records_non_trigger_check():
    result = resolve_wild_magic_for_spell(
        caster_name="伊芙",
        is_cantrip=False,
        derived={"subclass_effects": {"wild_magic": True}},
        class_resources={},
        roll_dice=lambda notation: {"rolls": [7], "total": 7},
        roll_wild_magic_surge=lambda: (_ for _ in ()).throw(AssertionError("should not surge")),
    )

    assert result.surge is None
    assert result.check == {"d20": 7, "triggered": False, "forced": False}
    assert "未触发涌动" in result.log_content


def test_apply_wild_magic_mechanical_heal_caps_at_max_hp():
    caster = SimpleNamespace(hp_current=5, derived={"hp_max": 12}, conditions=[])

    apply_wild_magic_mechanical_effect(
        caster=caster,
        surge=_surge(mechanical={"type": "heal", "dice": "2d10"}),
        roll_dice=lambda notation: {"rolls": [8, 8], "total": 16},
    )

    assert caster.hp_current == 12


def test_apply_wild_magic_mechanical_condition_appends_condition():
    caster = SimpleNamespace(hp_current=5, derived={"hp_max": 12}, conditions=["prone"])

    apply_wild_magic_mechanical_effect(
        caster=caster,
        surge=_surge(
            effect="你变成一盆盆栽",
            mechanical={"type": "condition", "condition": "失能", "duration": "1round"},
        ),
        roll_dice=lambda *_args: (_ for _ in ()).throw(AssertionError("should not roll heal")),
    )

    assert caster.conditions == ["prone", "失能"]
