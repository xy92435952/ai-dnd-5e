import uuid

import pytest

from models import Character
from services.dnd_rules import CASTER_TYPE, HIT_DICE, calc_derived, get_class_resource_defaults, get_spell_slots
from services.dnd_subclass_progression import subclass_options_for_class, subclass_unlock_level


pytestmark = pytest.mark.integration

BASE_ABILITY_SCORES = {"str": 14, "dex": 14, "con": 14, "int": 14, "wis": 14, "cha": 14}
ALL_SUPPORTED_CLASSES = sorted(HIT_DICE)


async def _auth_headers(client, sample_user):
    response = await client.post("/auth/login", json={
        "username": sample_user.username,
        "password": "password",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _level_up_payload(char_class: str, next_level: int) -> dict:
    payload = {"use_average_hp": True}
    if next_level in {4, 8, 12, 16, 19}:
        payload["ability_score_increases"] = {"str": 1, "con": 1}
    if char_class == "Fighter" and next_level in {6, 14}:
        payload["ability_score_increases"] = {"str": 1, "con": 1}
    if char_class == "Rogue" and next_level == 10:
        payload["ability_score_increases"] = {"str": 1, "con": 1}
    return payload


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


def _stored_derived_from_response(derived: dict) -> dict:
    stored = dict(derived or {})
    stored.pop("base_hp_max", None)
    return stored


@pytest.mark.parametrize("char_class", ALL_SUPPORTED_CLASSES)
async def test_level_up_endpoint_supports_level_one_to_twenty_for_all_classes(
    char_class,
    client,
    db_session,
    sample_user,
):
    old_derived = calc_derived(char_class, 1, BASE_ABILITY_SCORES, None, race="Human", proficient_skills=[])
    character = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name=f"Progression {char_class}",
        race="Human",
        char_class=char_class,
        level=1,
        ability_scores=dict(BASE_ABILITY_SCORES),
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots=dict(old_derived.get("spell_slots_max", {})),
        class_resources=get_class_resource_defaults(char_class, 1),
        known_spells=[],
        cantrips=[],
        proficient_skills=[],
        proficient_saves=[],
        is_player=True,
    )
    db_session.add(character)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    for expected_level in range(2, 21):
        payload = _level_up_payload(char_class, expected_level)
        subclass_choice = _subclass_choice_for_next_level(
            char_class,
            character.subclass,
            expected_level,
        )
        if subclass_choice:
            payload["subclass_choice"] = subclass_choice
        fighting_style_choice = _fighting_style_choice_for_next_level(
            char_class,
            character.fighting_style,
            expected_level,
        )
        if fighting_style_choice:
            payload["fighting_style_choice"] = fighting_style_choice
        maneuver_choices = _maneuver_choices_for_next_level(
            char_class,
            character.subclass,
            character.class_resources,
            expected_level,
            subclass_choice,
        )
        if maneuver_choices:
            payload["maneuver_choices"] = maneuver_choices

        response = await client.post(
            f"/characters/{character.id}/level-up",
            headers=headers,
            json=payload,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        data = payload["character"]
        details = payload["level_up_details"]
        assert data["level"] == expected_level
        assert data["subclass"] == (character.subclass or subclass_choice)
        assert data["fighting_style"] == (character.fighting_style or fighting_style_choice)
        assert details["old_level"] == expected_level - 1
        assert details["new_level"] == expected_level
        assert details["subclass"] == data["subclass"]
        assert details["fighting_style"] == data["fighting_style"]
        assert details["new_spell_slots"] == get_spell_slots(char_class, expected_level)
        assert data["spell_slots"] == get_spell_slots(char_class, expected_level)
        assert data["derived"]["hit_die"] == HIT_DICE[char_class]
        assert data["derived"]["proficiency_bonus"] == calc_derived(
            char_class,
            expected_level,
            data["ability_scores"],
            None,
            fighting_style=data["fighting_style"],
            race="Human",
            proficient_skills=[],
        )["proficiency_bonus"]
        assert data["hp_current"] <= data["derived"]["hp_max"]
        assert data["known_spells"] == []
        assert data["cantrips"] == []

        await db_session.refresh(character)
        assert character.level == expected_level
        assert character.subclass == data["subclass"]
        assert character.fighting_style == data["fighting_style"]
        assert character.class_resources == data["class_resources"]
        assert character.ability_scores == data["ability_scores"]
        assert character.derived == _stored_derived_from_response(data["derived"])
        assert character.hp_current == data["hp_current"]
        assert character.spell_slots == data["spell_slots"]
        assert character.class_resources == data["class_resources"]

    assert character.level == 20
    if char_class == "Barbarian":
        expected_score = 23
    elif char_class in {"Fighter", "Rogue"}:
        expected_score = 20
    else:
        expected_score = 19
    assert character.ability_scores["str"] == expected_score
    assert character.ability_scores["con"] == expected_score
    assert character.derived["proficiency_bonus"] == 6
    if CASTER_TYPE.get(char_class) == "full":
        assert character.spell_slots["6th"] == 2
        assert character.spell_slots["7th"] == 2
        assert character.spell_slots["9th"] == 1
    elif CASTER_TYPE.get(char_class) == "half":
        assert character.spell_slots["5th"] == 2
    elif CASTER_TYPE.get(char_class) == "pact":
        assert character.spell_slots == {"5th": 4}
    if char_class == "Barbarian":
        assert character.class_resources["rage_remaining"] == 999
        assert character.derived["ability_modifiers"]["str"] == 6
        assert character.derived["ability_modifiers"]["con"] == 6
        assert character.derived["attack_bonus"] == 12
    if char_class == "Druid":
        assert character.class_resources["wild_shape_remaining"] == 999
    if char_class == "Fighter" and character.subclass == "Battle Master":
        assert character.class_resources["action_surge_remaining"] == 2
        assert character.class_resources["maneuvers_known"] == [
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
