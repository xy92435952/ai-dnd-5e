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
