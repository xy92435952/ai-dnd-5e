import pytest
from sqlalchemy import select

from models import Character, GameLog, Session
from services.smoke_scenario_seed import seed_smoke_scenario


pytestmark = pytest.mark.integration


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_seeded_feather_fall_variant_restores_prompt_and_resolves_via_http(
    client,
    db_session,
):
    """The deployment smoke seed should make exploration Feather Fall QA reachable without LLMs."""
    result = await seed_smoke_scenario(
        db_session,
        slug="feather fall http qa",
        variant="feather-fall",
    )

    login = await client.post("/auth/login", json={
        "username": result.username,
        "password": result.password,
    })
    assert login.status_code == 200, login.text
    headers = _h(login.json()["token"])

    restored = await client.get(f"/game/sessions/{result.session_id}", headers=headers)
    assert restored.status_code == 200, restored.text
    data = restored.json()
    assert data["combat_active"] is False

    prompt = data["game_state"]["pending_exploration_reaction"]
    assert prompt["type"] == "feather_fall"
    assert prompt["reactor_character_id"] == result.companion_ids[0]
    assert prompt["target_character_id"] == result.character_id
    assert prompt["damage_prevented"] == 6

    accepted = await client.post(
        f"/game/sessions/{result.session_id}/exploration-reaction",
        headers=headers,
        json={
            "reaction_type": "feather_fall",
            "character_id": prompt["reactor_character_id"],
        },
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["type"] == "exploration_reaction"
    assert body["reaction_effect"]["damage_prevented"] == 6
    assert body["target_state"]["hp_current"] == data["player"]["hp_max"]
    assert body["caster_state"]["spell_slots"]["1st"] == 0
    assert any(row.get("kind") == "reaction" for row in body["dice_display"])

    session = await db_session.get(Session, result.session_id)
    hero = await db_session.get(Character, result.character_id)
    companion = await db_session.get(Character, result.companion_ids[0])
    await db_session.refresh(session)
    await db_session.refresh(hero)
    await db_session.refresh(companion)

    assert "pending_exploration_reaction" not in session.game_state
    assert hero.hp_current == data["player"]["hp_max"]
    assert companion.spell_slots["1st"] == 0

    after = await client.get(f"/game/sessions/{result.session_id}", headers=headers)
    assert after.status_code == 200, after.text
    assert "pending_exploration_reaction" not in after.json()["game_state"]

    logs = (
        await db_session.execute(
            select(GameLog).where(GameLog.session_id == result.session_id)
        )
    ).scalars().all()
    assert any("preventing 6 fall damage" in log.content for log in logs)
