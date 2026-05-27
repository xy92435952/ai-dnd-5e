from types import SimpleNamespace

from services.exploration_rules_service import (
    group_stealth_result,
    party_best_passive,
    passive_detects,
    passive_investigation,
    passive_perception,
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
