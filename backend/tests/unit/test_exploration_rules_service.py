from types import SimpleNamespace

from services.exploration_rules_service import (
    build_exploration_context,
    character_passive_summary,
    group_stealth_result,
    party_best_passive,
    passive_detects,
    passive_investigation,
    passive_perception,
    resolve_passive_discoveries,
    resolve_trap_trigger,
    passive_score,
)


def _character(
    *,
    char_id: str = "c1",
    name: str = "Scout",
    mods: dict | None = None,
    proficiency_bonus: int = 2,
    proficient_skills: list[str] | None = None,
    feats: list | None = None,
) -> dict:
    return {
        "id": char_id,
        "name": name,
        "derived": {
            "ability_modifiers": mods or {},
            "proficiency_bonus": proficiency_bonus,
        },
        "proficient_skills": proficient_skills or [],
        "feats": feats or [],
    }


def test_passive_perception_uses_wisdom_and_proficiency():
    character = _character(
        mods={"wis": 3},
        proficiency_bonus=3,
        proficient_skills=["perception"],
    )

    assert passive_perception(character) == 16


def test_passive_score_normalizes_chinese_skill_aliases():
    character = _character(
        mods={"wis": 2, "dex": 4},
        proficiency_bonus=2,
        proficient_skills=["\u611f\u77e5", "\u9690\u533f"],
    )

    assert passive_score(character, "\u5bdf\u89c9") == 14
    assert passive_score(character, "\u6f5c\u884c") == 16


def test_passive_score_accepts_flat_character_snapshots():
    snapshot = {
        "id": "flat",
        "name": "Flat Snapshot",
        "ability_modifiers": {"wis": 2},
        "proficiency_bonus": 3,
        "proficient_skills": ["perception"],
    }

    assert passive_perception(snapshot) == 15


def test_passive_investigation_uses_intelligence_and_observant_bonus():
    character = _character(
        mods={"int": 1, "wis": 4},
        proficiency_bonus=2,
        proficient_skills=["investigation"],
        feats=[{"name": "Observant"}],
    )

    assert passive_investigation(character) == 18


def test_passive_detects_compares_passive_score_to_dc():
    character = _character(mods={"wis": 2}, proficient_skills=["perception"])

    assert passive_detects(character, 14)
    assert not passive_detects(character, 15)


def test_party_best_passive_returns_highest_score_and_character_identity():
    characters = [
        _character(char_id="low", name="Low", mods={"wis": 0}),
        _character(char_id="high", name="High", mods={"wis": 3}, proficient_skills=["perception"]),
    ]

    result = party_best_passive(characters)

    assert result == {
        "character_id": "high",
        "name": "High",
        "score": 15,
        "skill": "perception",
    }


def test_party_best_passive_accepts_object_like_characters():
    character = SimpleNamespace(
        id="obj-1",
        name="Object Scout",
        derived={"ability_modifiers": {"wis": 1}, "proficiency_bonus": 3},
        proficient_skills=["perception"],
        feats=[],
    )

    assert party_best_passive([character])["score"] == 14


def test_character_passive_summary_contains_core_exploration_scores():
    character = _character(
        char_id="scout",
        name="Scout",
        mods={"wis": 2, "int": 1, "dex": 4},
        proficiency_bonus=2,
        proficient_skills=["perception", "stealth"],
    )

    assert character_passive_summary(character) == {
        "character_id": "scout",
        "name": "Scout",
        "passive_perception": 14,
        "passive_investigation": 11,
        "passive_stealth": 16,
    }


def test_build_exploration_context_summarizes_party_passives():
    characters = [
        _character(char_id="wizard", name="Wizard", mods={"int": 4, "wis": 0, "dex": 1}),
        _character(
            char_id="rogue",
            name="Rogue",
            mods={"int": 0, "wis": 2, "dex": 4},
            proficient_skills=["perception", "stealth"],
        ),
    ]

    context = build_exploration_context(characters)

    assert context["character_passives"][0]["passive_investigation"] == 14
    assert context["party_best_passive"]["perception"]["character_id"] == "rogue"
    assert context["party_best_passive"]["perception"]["score"] == 14
    assert context["party_best_passive"]["investigation"]["character_id"] == "wizard"
    assert context["party_best_passive"]["investigation"]["score"] == 14
    assert context["party_best_passive"]["stealth"]["character_id"] == "rogue"
    assert context["party_best_passive"]["stealth"]["score"] == 16
    assert context["group_stealth"]["success_rule"] == "at_least_half_members_meet_or_exceed_dc"
    assert context["passive_discovery"]["features"] == []


def test_resolve_passive_discoveries_detects_hidden_features_by_best_passive_score():
    characters = [
        _character(char_id="fighter", name="Fighter", mods={"wis": 0, "int": 0}),
        _character(char_id="scout", name="Scout", mods={"wis": 3, "int": 1}, proficient_skills=["perception"]),
    ]

    result = resolve_passive_discoveries(
        characters,
        [
            {"id": "wire", "name": "Tripwire", "kind": "trap", "dc": 15},
            {"id": "door", "name": "False Wall", "kind": "secret_door", "dc": 16},
        ],
    )

    assert result["rule"] == "party_best_passive_for_feature_skill_meets_dc"
    assert result["detected_feature_ids"] == ["wire"]
    assert result["hidden_feature_ids"] == ["door"]
    assert result["features"][0]["skill"] == "perception"
    assert result["features"][0]["detected_by"]["character_id"] == "scout"
    assert result["features"][0]["best_score"] == 15
    assert result["features"][1]["detected_by"] is None


def test_resolve_passive_discoveries_uses_investigation_for_clues_and_mechanisms():
    characters = [
        _character(char_id="sage", name="Sage", mods={"int": 4, "wis": 0}, proficient_skills=["investigation"]),
    ]

    result = resolve_passive_discoveries(
        characters,
        [
            {"name": "Ledger clue", "kind": "clue", "dc": 15},
            {"name": "Poison needle", "kind": "trap", "detection_skill": "investigation", "dc": 17},
        ],
    )

    assert result["detected_feature_ids"] == ["Ledger clue"]
    assert result["hidden_feature_ids"] == ["Poison needle"]
    assert result["features"][0]["feature_id"] == "Ledger clue"
    assert result["features"][0]["skill"] == "investigation"
    assert result["features"][0]["best_score"] == 16
    assert result["features"][1]["skill"] == "investigation"


def test_resolve_trap_trigger_halves_damage_on_successful_save():
    target = _character(
        char_id="rogue",
        name="Rogue",
        mods={"dex": 3},
    )
    target["derived"]["saving_throws"] = {"dex": 5}

    result = resolve_trap_trigger(
        {
            "id": "dart",
            "name": "Poison Dart",
            "save_ability": "dex",
            "save_dc": 14,
            "damage_dice": "2d10",
            "damage_type": "poison",
        },
        target,
        d20_roller=lambda _expr: {"rolls": [12], "total": 12},
        damage_roller=lambda expr: {"notation": expr, "rolls": [8, 6], "total": 14},
    )

    assert result["trap_id"] == "dart"
    assert result["target_id"] == "rogue"
    assert result["saved"] is True
    assert result["save"]["total"] == 17
    assert result["rolled_damage"] == 14
    assert result["final_damage"] == 7
    assert result["conditions_applied"] == []
    assert result["mutates_hp"] is False


def test_resolve_trap_trigger_applies_full_damage_and_failed_conditions():
    target = _character(char_id="fighter", name="Fighter", mods={"dex": 0})
    target["derived"]["saving_throws"] = {"dex": 0}

    result = resolve_trap_trigger(
        {
            "name": "Net Snare",
            "dc": 13,
            "damage": "1d6",
            "condition_on_fail": "restrained",
            "half_on_save": False,
        },
        target,
        d20_roller=lambda _expr: {"rolls": [7], "total": 7},
        damage_roller=lambda expr: {"notation": expr, "rolls": [5], "total": 5},
    )

    assert result["trap_id"] == "Net Snare"
    assert result["save_ability"] == "dex"
    assert result["save_dc"] == 13
    assert result["saved"] is False
    assert result["damage_dice"] == "1d6"
    assert result["half_on_save"] is False
    assert result["final_damage"] == 5
    assert result["conditions_applied"] == ["restrained"]


def test_resolve_trap_trigger_accepts_object_like_targets_and_ability_aliases():
    target = SimpleNamespace(
        id="wizard",
        name="Wizard",
        ability_scores={"wis": 14},
        derived={"saving_throws": {"wis": 4}, "ability_modifiers": {"wis": 2}},
        conditions=[],
        condition_durations={},
    )

    result = resolve_trap_trigger(
        {
            "id": "glyph",
            "saving_throw": "wisdom",
            "save_dc": 15,
            "damage_dice": "3d8",
            "conditions_on_fail": ["frightened"],
        },
        target,
        d20_roller=lambda _expr: {"rolls": [10], "total": 10},
        damage_roller=lambda expr: {"notation": expr, "rolls": [4, 4, 4], "total": 12},
    )

    assert result["target_id"] == "wizard"
    assert result["save_ability"] == "wis"
    assert result["saved"] is False
    assert result["final_damage"] == 12
    assert result["conditions_applied"] == ["frightened"]


def test_group_stealth_succeeds_when_at_least_half_succeed():
    result = group_stealth_result(
        [
            {"character_id": "a", "total": 18},
            {"character_id": "b", "total": 11},
            {"character_id": "c", "success": True},
            {"character_id": "d", "success": False},
        ],
        dc=14,
    )

    assert result == {
        "dc": 14,
        "members": 4,
        "successes": 2,
        "needed": 2,
        "success": True,
        "failed_member_ids": ["b", "d"],
    }


def test_group_stealth_fails_empty_or_less_than_half_successes():
    assert group_stealth_result([], 12)["success"] is False

    result = group_stealth_result(
        [
            {"id": "a", "total": 8},
            {"id": "b", "total": 12},
            {"id": "c", "total": 9},
        ],
        dc=12,
    )

    assert result["needed"] == 2
    assert result["successes"] == 1
    assert result["success"] is False
    assert result["failed_member_ids"] == ["a", "c"]
