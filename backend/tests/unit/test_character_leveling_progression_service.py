import pytest

from services import character_leveling_service
from services.dnd_rules import CASTER_TYPE, HIT_DICE, calc_derived, get_class_resource_defaults, get_spell_slots
from services.dnd_subclass_progression import subclass_options_for_class, subclass_unlock_level


BASE_ABILITY_SCORES = {"str": 14, "dex": 14, "con": 14, "int": 14, "wis": 14, "cha": 14}
ALL_SUPPORTED_CLASSES = sorted(HIT_DICE)


def _starting_state(char_class: str) -> dict:
    derived = calc_derived(char_class, 1, BASE_ABILITY_SCORES, None, race="Human", proficient_skills=[])
    return {
        "char_class": char_class,
        "level": 1,
        "ability_scores": dict(BASE_ABILITY_SCORES),
        "derived": derived,
        "hp_current": derived["hp_max"],
        "spell_slots": dict(derived.get("spell_slots_max", {})),
        "class_resources": get_class_resource_defaults(char_class, 1),
        "known_spells": [],
        "cantrips": [],
    }


def _asi_payload_for_next_level(char_class: str, next_level: int) -> dict | None:
    if next_level in {4, 8, 12, 16, 19}:
        return {"str": 1, "con": 1}
    if char_class == "Fighter" and next_level in {6, 14}:
        return {"str": 1, "con": 1}
    if char_class == "Rogue" and next_level == 10:
        return {"str": 1, "con": 1}
    return None


def _subclass_choice_for_next_level(char_class: str, current_subclass: str | None, next_level: int) -> str | None:
    if current_subclass or next_level < subclass_unlock_level(char_class):
        return None
    options = subclass_options_for_class(char_class)
    return options[0] if options else None


def _fighting_style_choice_for_next_level(char_class: str, current_style: str | None, next_level: int) -> str | None:
    if current_style:
        return None
    if char_class == "Fighter" and next_level >= 1:
        return "Defense"
    if char_class == "Paladin" and next_level >= 2:
        return "Defense"
    if char_class == "Ranger" and next_level >= 2:
        return "Archery"
    return None


def _maneuver_choices_for_next_level(
    char_class: str,
    current_subclass: str | None,
    current_resources: dict | None,
    next_level: int,
    subclass_choice: str | None = None,
) -> list[str]:
    subclass = current_subclass or subclass_choice or ""
    if char_class != "Fighter" or "Battle Master" not in subclass or next_level < 3:
        return []
    current = list((current_resources or {}).get("maneuvers_known") or [])
    required = 3 if next_level < 7 else (5 if next_level < 10 else (7 if next_level < 15 else 9))
    options = [
        "precision",
        "trip",
        "disarm",
        "riposte",
        "menacing",
        "pushing",
        "goading",
        "distracting",
        "lunging",
    ]
    return [maneuver for maneuver in options if maneuver not in current][:max(0, required - len(current))]


@pytest.mark.parametrize("char_class", ALL_SUPPORTED_CLASSES)
def test_build_level_up_update_supports_level_one_to_twenty_for_all_classes(char_class):
    state = _starting_state(char_class)

    for expected_level in range(2, 21):
        subclass_choice = _subclass_choice_for_next_level(
            char_class,
            state.get("subclass"),
            expected_level,
        )
        update = character_leveling_service.build_level_up_update(
            char_class=state["char_class"],
            level=state["level"],
            ability_scores=state["ability_scores"],
            derived=state["derived"],
            hp_current=state["hp_current"],
            spell_slots=state["spell_slots"],
            use_average_hp=True,
            class_resources=state["class_resources"],
            race="Human",
            proficient_skills=[],
            known_spells=state["known_spells"],
            cantrips=state["cantrips"],
            subclass=state.get("subclass"),
            subclass_choice=subclass_choice,
            fighting_style=state.get("fighting_style"),
            fighting_style_choice=_fighting_style_choice_for_next_level(
                char_class,
                state.get("fighting_style"),
                expected_level,
            ),
            maneuver_choices=_maneuver_choices_for_next_level(
                char_class,
                state.get("subclass"),
                state["class_resources"],
                expected_level,
                subclass_choice,
            ),
            ability_score_increases=_asi_payload_for_next_level(char_class, expected_level),
        )

        assert update["old_level"] == expected_level - 1
        assert update["new_level"] == expected_level
        assert update["derived"]["hit_die"] == HIT_DICE[char_class]
        assert update["derived"]["caster_type"] == CASTER_TYPE.get(char_class)
        assert update["new_spell_slots"] == get_spell_slots(char_class, expected_level)
        assert update["spell_slots"] == get_spell_slots(char_class, expected_level)
        assert update["subclass"] == (
            state.get("subclass")
            or _subclass_choice_for_next_level(char_class, state.get("subclass"), expected_level)
        )
        assert update["fighting_style"] == (
            state.get("fighting_style")
            or _fighting_style_choice_for_next_level(char_class, state.get("fighting_style"), expected_level)
        )
        assert update["known_spells"] == state["known_spells"]
        assert update["cantrips"] == state["cantrips"]
        assert update["learned_spells"] == []
        assert update["learned_cantrips"] == []

        expected_derived = calc_derived(
            char_class,
            expected_level,
            update["ability_scores"],
            update["subclass"],
            fighting_style=update["fighting_style"],
            race="Human",
            proficient_skills=[],
        )
        assert update["derived"]["hp_max"] == expected_derived["hp_max"]
        assert update["derived"]["proficiency_bonus"] == expected_derived["proficiency_bonus"]
        assert update["hp_current"] <= update["derived"]["hp_max"]
        assert update["hp_current"] > state["hp_current"]

        for key, value in get_class_resource_defaults(char_class, expected_level).items():
            assert key in update["class_resources"]
            if isinstance(value, bool):
                assert isinstance(update["class_resources"][key], bool)
            elif isinstance(value, int):
                assert 0 <= update["class_resources"][key] <= value

        state.update(
            level=update["new_level"],
            subclass=update["subclass"],
            fighting_style=update["fighting_style"],
            ability_scores=update["ability_scores"],
            derived=update["derived"],
            hp_current=update["hp_current"],
            spell_slots=update["spell_slots"],
            class_resources=update["class_resources"],
            known_spells=update["known_spells"],
            cantrips=update["cantrips"],
        )

    assert state["level"] == 20
    if char_class == "Barbarian":
        expected_score = 23
    elif char_class in {"Fighter", "Rogue"}:
        expected_score = 20
    else:
        expected_score = 19
    assert state["ability_scores"]["str"] == expected_score
    assert state["ability_scores"]["con"] == expected_score
    assert state["derived"]["proficiency_bonus"] == 6
    if CASTER_TYPE.get(char_class) == "full":
        assert state["spell_slots"]["6th"] == 2
        assert state["spell_slots"]["7th"] == 2
        assert state["spell_slots"]["9th"] == 1
    elif CASTER_TYPE.get(char_class) == "half":
        assert state["spell_slots"]["5th"] == 2
    elif CASTER_TYPE.get(char_class) == "pact":
        assert state["spell_slots"] == {"5th": 4}
    if char_class == "Barbarian":
        assert state["class_resources"]["rage_remaining"] == 999
        assert state["derived"]["ability_modifiers"]["str"] == 6
        assert state["derived"]["ability_modifiers"]["con"] == 6
        assert state["derived"]["attack_bonus"] == 12
    if char_class == "Druid":
        assert state["class_resources"]["wild_shape_remaining"] == 999
    if char_class == "Fighter" and state["subclass"] == "Battle Master":
        assert state["class_resources"]["action_surge_remaining"] == 2
        assert state["class_resources"]["maneuvers_known"] == [
            "precision",
            "trip",
            "disarm",
            "riposte",
            "menacing",
            "pushing",
            "goading",
            "distracting",
            "lunging",
        ]
