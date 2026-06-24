import pytest
from sqlalchemy import select

from models import CombatState, GameLog, Session
from services.smoke_scenario_seed import (
    STAGE7_5_COMBAT_CHOICE_TEXT,
    STAGE7_5_TOKEN_LOOT_ID,
    seed_smoke_scenario,
)


pytestmark = pytest.mark.integration


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _turn_token(combat_data: dict) -> str:
    index = int(combat_data.get("current_turn_index") or 0)
    current = list(combat_data.get("turn_order") or [])[index]
    return f"{combat_data.get('round_number') or 1}:{index}:{current['character_id']}"


def _first_live_enemy(combat_data: dict) -> tuple[str, dict]:
    enemies = [
        (entity_id, entity)
        for entity_id, entity in (combat_data.get("entities") or {}).items()
        if entity.get("is_enemy") and int(entity.get("hp_current") or 0) > 0
    ]
    enemies.sort(key=lambda item: int(item[1].get("hp_current") or 0))
    assert enemies
    return enemies[0]


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

    async def skip_combat_narration(*args, **kwargs):
        return ""

    monkeypatch.setattr(
        "services.game_exploration_service.langgraph_client.call_dm_agent",
        fail_if_llm_called,
    )
    monkeypatch.setattr("api.combat.attack_rolls.narrate_action", skip_combat_narration)

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

    target_id, target = _first_live_enemy(combat_data)
    before_hp = int(target["hp_current"])
    attack = await client.post(
        f"/game/combat/{result.session_id}/attack-roll",
        headers=headers,
        json={
            "entity_id": result.character_id,
            "target_id": target_id,
            "action_type": "ranged",
            "d20_value": 19,
            "expected_turn_token": _turn_token(combat_data),
        },
    )
    assert attack.status_code == 200, attack.text
    attack_data = attack.json()
    assert attack_data["hit"] is True
    assert attack_data["pending_attack_id"]

    damage = await client.post(
        f"/game/combat/{result.session_id}/damage-roll",
        headers=headers,
        json={
            "pending_attack_id": attack_data["pending_attack_id"],
            "damage_values": [4],
        },
    )
    assert damage.status_code == 200, damage.text

    after_damage = await client.get(f"/game/combat/{result.session_id}", headers=headers)
    assert after_damage.status_code == 200, after_damage.text
    after_damage_data = after_damage.json()
    after_hp = int(after_damage_data["entities"][target_id]["hp_current"])
    assert after_hp < before_hp

    end_turn_token = _turn_token(after_damage_data)
    end_turn = await client.post(
        f"/game/combat/{result.session_id}/end-turn",
        headers=headers,
        json={"expected_turn_token": end_turn_token},
    )
    assert end_turn.status_code == 200, end_turn.text

    after_end_turn = await client.get(f"/game/combat/{result.session_id}", headers=headers)
    assert after_end_turn.status_code == 200, after_end_turn.text
    assert _turn_token(after_end_turn.json()) != end_turn_token

    claim = await client.post(
        f"/game/sessions/{result.session_id}/loot/claim",
        headers=headers,
        json={
            "character_id": result.character_id,
            "loot_id": STAGE7_5_TOKEN_LOOT_ID,
            "claim_mode": "party_stash",
        },
    )
    assert claim.status_code == 200, claim.text
    claimed_items = claim.json()["loot_pool"]["items"]
    gate_token = next(item for item in claimed_items if item["id"] == STAGE7_5_TOKEN_LOOT_ID)
    assert gate_token["status"] == "claimed"
    assert gate_token["shared_with_party"] is True
