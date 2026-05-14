from models import Character
from services.dnd_rules import (
    ALL_SKILLS,
    CLASS_SAVE_PROFICIENCIES,
    CLASS_SKILL_CHOICES,
    _normalize_class,
    apply_racial_bonuses,
    calc_derived,
)


def build_companion_character(payload: dict, *, fallback_level: int) -> Character:
    base_scores = payload.get("ability_scores", {
        "str": 10,
        "dex": 10,
        "con": 10,
        "int": 10,
        "wis": 10,
        "cha": 10,
    })
    companion_race = payload.get("race", "人类")
    companion_class = payload.get("class", "Fighter")
    companion_level = payload.get("level", fallback_level)

    final_scores = apply_racial_bonuses(base_scores, companion_race)
    cls_key = _normalize_class(companion_class)
    save_proficiencies = CLASS_SAVE_PROFICIENCIES.get(cls_key, [])
    proficient_skills = _build_companion_skills(payload, cls_key)

    derived = calc_derived(
        companion_class,
        companion_level,
        final_scores,
        payload.get("subclass"),
        race=companion_race,
        proficient_skills=proficient_skills,
    )

    return Character(
        is_player=False,
        name=payload.get("name", "未知冒险者"),
        race=companion_race,
        char_class=companion_class,
        subclass=payload.get("subclass"),
        level=companion_level,
        background=payload.get("background"),
        alignment=payload.get("alignment", "中立善良"),
        ability_scores=final_scores,
        derived=derived,
        hp_current=derived["hp_max"],
        spell_slots=dict(derived.get("spell_slots_max", {})),
        known_spells=payload.get("known_spells", []),
        cantrips=payload.get("cantrips", []),
        proficient_skills=proficient_skills,
        proficient_saves=save_proficiencies,
        personality=payload.get("personality_traits", ""),
        speech_style=payload.get("speech_style", ""),
        combat_preference=payload.get("combat_preference", ""),
        backstory=payload.get("backstory", ""),
        catchphrase=payload.get("catchphrase", ""),
    )


def _build_companion_skills(payload: dict, cls_key: str) -> list[str]:
    ai_skills = payload.get("proficient_skills", [])
    if ai_skills:
        return list(ai_skills)

    skill_config = CLASS_SKILL_CHOICES.get(cls_key, {"count": 2, "options": ALL_SKILLS})
    return list(skill_config["options"][:skill_config["count"]])
