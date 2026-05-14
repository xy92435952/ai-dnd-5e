from services.character_companion_service import build_companion_character


def test_build_companion_character_applies_defaults_and_class_skill_fallback():
    companion = build_companion_character({}, fallback_level=4)

    assert companion.is_player is False
    assert companion.name == "未知冒险者"
    assert companion.char_class == "Fighter"
    assert companion.level == 4
    assert companion.hp_current == companion.derived["hp_max"]
    assert companion.spell_slots == companion.derived.get("spell_slots_max", {})
    assert len(companion.proficient_skills) == 2
    assert companion.proficient_saves == ["str", "con"]


def test_build_companion_character_keeps_ai_skills_and_narrative_fields():
    companion = build_companion_character(
        {
            "name": "艾拉",
            "race": "Elf",
            "class": "Wizard",
            "level": 2,
            "ability_scores": {"str": 8, "dex": 13, "con": 14, "int": 15, "wis": 12, "cha": 10},
            "proficient_skills": ["奥秘", "调查"],
            "personality_traits": "好奇",
            "speech_style": "轻快",
            "combat_preference": "控制",
            "backstory": "来自学院",
            "catchphrase": "让我看看。",
        },
        fallback_level=1,
    )

    assert companion.name == "艾拉"
    assert companion.char_class == "Wizard"
    assert companion.level == 2
    assert companion.ability_scores["dex"] == 15
    assert companion.ability_scores["int"] == 16
    assert companion.proficient_skills == ["奥秘", "调查"]
    assert companion.personality == "好奇"
    assert companion.catchphrase == "让我看看。"
