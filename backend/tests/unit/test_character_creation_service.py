import pytest

from services import character_creation_service


def test_build_starting_equipment_equips_fighter_heavy_armor_loadout():
    equipment = character_creation_service.build_starting_equipment("Fighter", 0)

    assert equipment["gold"] == 10
    assert equipment["armor"] == [
        {
            "name": "Chain Mail",
            "zh": "锁甲",
            "ac": 16,
            "type": "heavy",
            "dex_bonus": "none",
            "stealth_disadvantage": True,
            "weight": 55,
            "cost": 75,
            "equipped": True,
        }
    ]
    assert equipment["shield"] == {
        "name": "Shield",
        "zh": "盾牌",
        "ac": 2,
        "equipped": True,
    }
    assert [weapon["name"] for weapon in equipment["weapons"]] == ["Longsword", "Light Crossbow"]
    assert equipment["weapons"][0]["equipped"] is True
    assert equipment["weapons"][1]["equipped"] is False
    assert equipment["weapons"][1]["ammo"] == 20
    assert equipment["gear"] == [{"name": "Explorer's Pack", "zh": "探险者背包"}]


def test_build_starting_equipment_keeps_unknown_weapon_choice_as_gear():
    equipment = character_creation_service.build_starting_equipment("Fighter", 1)

    assert [weapon["name"] for weapon in equipment["weapons"]] == ["Longbow"]
    assert equipment["weapons"][0]["ammo"] == 20
    assert equipment["armor"][0]["name"] == "Leather"
    assert {"name": "Two Handaxes", "zh": "两把手斧"} in equipment["gear"]


def test_build_starting_equipment_returns_empty_for_invalid_choice():
    assert character_creation_service.build_starting_equipment("Fighter", None) == {}
    assert character_creation_service.build_starting_equipment("Fighter", 99) == {}
    assert character_creation_service.build_starting_equipment("Unknown", 0) == {}


def test_build_character_languages_caps_bonus_choices_and_deduplicates():
    languages = character_creation_service.build_character_languages(
        race="Human",
        background_features={"languages": 2},
        bonus_languages=["Elvish", "Elvish", "Orc", "Abyssal"],
    )

    assert languages == ["Common", "Elvish", "Orc"]


def test_build_character_languages_ignores_invalid_and_fixed_duplicates():
    languages = character_creation_service.build_character_languages(
        race="Elf",
        background_features={"languages": 2},
        bonus_languages=["Elvish", "Made Up", "Draconic"],
    )

    assert languages == ["Common", "Elvish"]


def test_normalize_fighting_style_accepts_valid_style_at_required_level():
    style = character_creation_service.normalize_fighting_style(
        cls_key="Fighter",
        class_label="Fighter",
        level=1,
        fighting_style="Defense",
    )

    assert style == "Defense"


def test_normalize_fighting_style_ignores_unavailable_class_or_level():
    assert character_creation_service.normalize_fighting_style(
        cls_key="Wizard",
        class_label="Wizard",
        level=1,
        fighting_style="Defense",
    ) is None
    assert character_creation_service.normalize_fighting_style(
        cls_key="Paladin",
        class_label="Paladin",
        level=1,
        fighting_style="Defense",
    ) is None


def test_normalize_fighting_style_rejects_invalid_style_for_eligible_class():
    with pytest.raises(character_creation_service.CharacterCreationError, match="战斗风格【Fake Style】不在Fighter可选范围内"):
        character_creation_service.normalize_fighting_style(
            cls_key="Fighter",
            class_label="Fighter",
            level=1,
            fighting_style="Fake Style",
        )


def test_build_proficient_skills_merges_background_skills_without_duplicates():
    skills = character_creation_service.build_proficient_skills(
        cls_key="Fighter",
        class_label="Fighter",
        selected_skills=["运动", "感知"],
        background_skills=["运动", "威吓"],
    )

    assert skills == ["运动", "感知", "威吓"]


def test_build_proficient_skills_rejects_too_many_selected_skills():
    with pytest.raises(character_creation_service.CharacterCreationError, match="Fighter 只能选 2 个技能熟练，您选了 3 个"):
        character_creation_service.build_proficient_skills(
            cls_key="Fighter",
            class_label="Fighter",
            selected_skills=["运动", "感知", "求生"],
            background_skills=[],
        )


def test_build_proficient_skills_rejects_skill_outside_class_options():
    with pytest.raises(character_creation_service.CharacterCreationError, match="技能【奥秘】不在该职业可选范围内"):
        character_creation_service.build_proficient_skills(
            cls_key="Fighter",
            class_label="Fighter",
            selected_skills=["奥秘"],
            background_skills=[],
        )
