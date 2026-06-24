import pytest
from sqlalchemy import select

from models import CombatState, GameLog, Session
from services.smoke_scenario_seed import (
    STAGE7_5_COMBAT_CHOICE_TEXT,
    seed_smoke_scenario,
)


pytestmark = pytest.mark.integration


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_stage7_5_seed_action_starts_combat_without_llm(client, db_session, monkeypatch):
    result = await seed_smoke_scenario(
        db_session,
        slug="stage7_5_launch",
        variant="stage7-5",
        username="test_stage7_5",
        password="123456",
    )

    async def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("Stage 7.5 seed action should not call the DM agent")

    monkeypatch.setattr(
        "services.game_exploration_service.langgraph_client.call_dm_agent",
        fail_if_llm_called,
    )

    login = await client.post("/auth/login", json={
        "username": result.username,
        "password": result.password,
    })
    assert login.status_code == 200, login.text
    headers = _h(login.json()["token"])

    restored = await client.get(f"/game/sessions/{result.session_id}", headers=headers)
    assert restored.status_code == 200, restored.text
    restored_data = restored.json()
    assert restored_data["combat_active"] is False
    assert restored_data["game_state"]["last_turn"]["player_choices"][0]["text"] == STAGE7_5_COMBAT_CHOICE_TEXT

    loot = await client.get(f"/game/sessions/{result.session_id}/loot", headers=headers)
    assert loot.status_code == 200, loot.text
    loot_items = loot.json()["items"]
    assert {item["name"] for item in loot_items} >= {"25 gp", "Gate Token"}

    action = await client.post(
        "/game/action",
        headers=headers,
        json={
            "session_id": result.session_id,
            "action_text": STAGE7_5_COMBAT_CHOICE_TEXT,
            "action_source": "ai_generated_choice",
        },
    )
    assert action.status_code == 200, action.text
    body = action.json()
    assert body["type"] == "stage7_5_combat_trigger"
    assert body["combat_triggered"] is True
    assert body["retryable"] is False

    session = await db_session.get(Session, result.session_id)
    await db_session.refresh(session)
    assert session.combat_active is True
    assert session.game_state["stage7_5_progress"] == "combat_started"
    assert session.game_state["enemies"][0]["hp_current"] == 4

    combat = (
        await db_session.execute(
            select(CombatState).where(CombatState.session_id == result.session_id)
        )
    ).scalars().first()
    assert combat is not None
    assert combat.turn_order[combat.current_turn_index]["character_id"] == result.character_id
    assert result.character_id in combat.turn_states
    assert "enemy_" in next(entry["character_id"] for entry in combat.turn_order if entry.get("is_enemy"))

    logs = (
        await db_session.execute(
            select(GameLog).where(GameLog.session_id == result.session_id)
        )
    ).scalars().all()
    assert any("Stage 7.5 smoke" in log.content for log in logs)

    combat_api = await client.get(f"/game/combat/{result.session_id}", headers=headers)
    assert combat_api.status_code == 200, combat_api.text
    combat_data = combat_api.json()
    assert combat_data["entities"][result.character_id]["is_player"] is True
    assert len(combat_data["entities"]) >= 3
