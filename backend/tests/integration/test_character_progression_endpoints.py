import uuid

import pytest

from models import Character
from services.dnd_rules import calc_derived

pytestmark = pytest.mark.integration


async def _auth_headers(client, sample_user):
    response = await client.post("/auth/login", json={
        "username": sample_user.username,
        "password": "password",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def test_level_up_adds_new_spell_slots_without_refilling_spent_slots(client, db_session, sample_user):
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 16, "wis": 12, "cha": 10}
    old_derived = calc_derived("Wizard", 2, ability_scores, None, race="Human")
    wizard = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="测试升阶法师",
        race="Human",
        char_class="Wizard",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={"1st": 0},
        proficient_skills=["奥秘", "调查"],
        proficient_saves=["int", "wis"],
        is_player=True,
    )
    db_session.add(wizard)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/characters/{wizard.id}/level-up",
        headers=headers,
        json={"use_average_hp": True},
    )

    assert response.status_code == 200, response.text
    data = response.json()["character"]
    assert data["level"] == 3
    assert data["spell_slots"]["1st"] == 1
    assert data["spell_slots"]["2nd"] == 2


async def test_exhaustion_level_4_clamps_hp_and_serializes_effective_max(
    client, db_session, sample_character, sample_user,
):
    sample_character.hp_current = 12
    sample_character.conditions = ["exhaustion"]
    sample_character.condition_durations = {"exhaustion_level": 3}
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.patch(
        f"/characters/{sample_character.id}/exhaustion",
        headers=headers,
        json={"change": 1},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["exhaustion_level"] == 4
    assert "hp_max_halved" in data["effects"]
    assert data["is_dead"] is False
    assert data["hp_current"] == 6
    assert data["hp_max"] == 6
    assert data["base_hp_max"] == 12

    await db_session.refresh(sample_character)
    assert sample_character.hp_current == 6
    assert sample_character.derived["hp_max"] == 12


async def test_exhaustion_level_6_sets_death_state(
    client, db_session, sample_character, sample_user,
):
    sample_character.hp_current = 6
    sample_character.conditions = ["exhaustion"]
    sample_character.condition_durations = {"exhaustion_level": 5}
    sample_character.death_saves = {"successes": 2, "failures": 0, "stable": False}
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.patch(
        f"/characters/{sample_character.id}/exhaustion",
        headers=headers,
        json={"change": 1},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["exhaustion_level"] == 6
    assert "death" in data["effects"]
    assert data["is_dead"] is True
    assert data["hp_current"] == 0
    assert data["death_saves"] == {"successes": 0, "failures": 3, "stable": False}

    await db_session.refresh(sample_character)
    assert sample_character.hp_current == 0
    assert sample_character.death_saves == {"successes": 0, "failures": 3, "stable": False}
