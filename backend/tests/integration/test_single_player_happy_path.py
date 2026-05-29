import json

import pytest
from sqlalchemy import select

from models import Character, Module, Session
from services.smoke_scenario_seed import build_smoke_module_content

pytestmark = pytest.mark.integration


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_ready_module(db_session, *, user_id: str, module_id: str = "happy-module-1"):
    module = Module(
        id=module_id,
        user_id=user_id,
        name="Happy Path Clockwork Crossing",
        file_path="seeded://happy-path",
        file_type="seed",
        parsed_content=build_smoke_module_content(),
        parse_status="done",
        parse_error=None,
        level_min=2,
        level_max=3,
        recommended_party_size=3,
    )
    db_session.add(module)
    await db_session.commit()
    return module


async def test_single_player_happy_path_login_module_character_adventure_combat_rest_checkpoint(
    client,
    db_session,
    monkeypatch,
):
    """Repeatable single-player smoke for the full playable loop without parser/LLM network calls."""
    import services.dnd_dice as dice
    import services.langgraph_client as lc

    register = await client.post("/auth/register", json={
        "username": "happy_path_player",
        "password": "password",
        "display_name": "Happy Path Player",
    })
    assert register.status_code == 200, register.text

    login = await client.post("/auth/login", json={
        "username": "happy_path_player",
        "password": "password",
    })
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    user_id = login.json()["user_id"]
    headers = _h(token)

    await _create_ready_module(db_session, user_id=user_id)

    modules = await client.get("/modules/", headers=headers)
    assert modules.status_code == 200, modules.text
    module_item = next(item for item in modules.json() if item["name"] == "Happy Path Clockwork Crossing")
    assert module_item["parse_status"] == "done"

    module_detail = await client.get(f"/modules/{module_item['id']}", headers=headers)
    assert module_detail.status_code == 200, module_detail.text
    assert module_detail.json()["parsed_content"]["scenes"][0]["choices"][0]["skill_check"] is True

    character_resp = await client.post("/characters/create", headers=headers, json={
        "module_id": module_item["id"],
        "name": "Loop Sentinel",
        "race": "Human",
        "char_class": "Fighter",
        "subclass": "Champion",
        "level": 3,
        "background": "Soldier",
        "alignment": "Neutral Good",
        "ability_scores": {"str": 15, "dex": 13, "con": 14, "int": 10, "wis": 12, "cha": 10},
        "proficient_skills": ["运动", "感知"],
        "fighting_style": "Defense",
        "equipment_choice": 0,
        "personality": "Patient and protective.",
        "backstory": "A veteran hired to stabilize the crossing.",
    })
    assert character_resp.status_code == 200, character_resp.text
    character = character_resp.json()
    assert character["name"] == "Loop Sentinel"
    assert character["hp_current"] == character["hp_max"]
    assert character["equipment"]["weapons"]

    session_resp = await client.post("/game/sessions", headers=headers, json={
        "module_id": module_item["id"],
        "player_character_id": character["id"],
        "companion_ids": [],
        "save_name": "Single Player Happy Path",
        "dm_style": "classic",
    })
    assert session_resp.status_code == 200, session_resp.text
    session_id = session_resp.json()["session_id"]
    assert session_resp.json()["opening_scene"]

    restored = await client.get(f"/game/sessions/{session_id}", headers=headers)
    assert restored.status_code == 200, restored.text
    restored_data = restored.json()
    assert restored_data["save_name"] == "Single Player Happy Path"
    assert restored_data["player"]["id"] == character["id"]
    assert restored_data["game_state"]["dm_style"] == "classic"
    assert any(log["content"].startswith("[开场]") for log in restored_data["logs"])

    skill_check = await client.post("/game/skill-check", headers=headers, json={
        "session_id": session_id,
        "character_id": character["id"],
        "skill": "运动",
        "dc": 13,
        "d20_value": 12,
    })
    assert skill_check.status_code == 200, skill_check.text
    assert skill_check.json()["success"] is True
    assert skill_check.json()["proficient"] is True

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "The repaired sentry sparks, then a training construct attacks.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "combat_trigger_reason": "The construct attacks after the tripwire is disarmed.",
                    "initial_enemies": [{
                        "name": "Clockwork Training Construct",
                        "hp": 12,
                        "ac": 14,
                        "attack_bonus": 4,
                        "damage_dice": "1d8+2",
                    }],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }, ensure_ascii=False),
            "success": True,
        }

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(dice.random, "randint", lambda low, high: high)

    action_resp = await client.post("/game/action", headers=headers, json={
        "session_id": session_id,
        "action_text": "I cross the yard after disarming the tripwire.",
        "idempotency_key": "single-happy-trigger-combat",
    })
    assert action_resp.status_code == 200, action_resp.text
    assert action_resp.json()["combat_triggered"] is True

    combat_resp = await client.get(f"/game/combat/{session_id}", headers=headers)
    assert combat_resp.status_code == 200, combat_resp.text
    combat = combat_resp.json()
    assert combat["session_id"] == session_id
    assert combat["turn_order"][0]["character_id"] == character["id"]
    enemy_id = next(entity_id for entity_id, entity in combat["entities"].items() if entity["is_enemy"])
    assert combat["entities"][enemy_id]["name"] == "Clockwork Training Construct"

    move_resp = await client.post(f"/game/combat/{session_id}/move", headers=headers, json={
        "entity_id": character["id"],
        "to_x": 3,
        "to_y": 3,
    })
    assert move_resp.status_code == 200, move_resp.text
    assert move_resp.json()["positions"][character["id"]] == {"x": 3, "y": 3}

    attack_resp = await client.post(f"/game/combat/{session_id}/attack-roll", headers=headers, json={
        "entity_id": character["id"],
        "target_id": enemy_id,
        "action_type": "ranged",
        "d20_value": 18,
    })
    assert attack_resp.status_code == 200, attack_resp.text
    attack = attack_resp.json()
    assert attack["hit"] is True
    assert attack["pending_attack_id"]

    damage_resp = await client.post(f"/game/combat/{session_id}/damage-roll", headers=headers, json={
        "pending_attack_id": attack["pending_attack_id"],
        "damage_values": [4],
    })
    assert damage_resp.status_code == 200, damage_resp.text
    damage = damage_resp.json()
    assert damage["target_id"] == enemy_id
    assert damage["target_new_hp"] < combat["entities"][enemy_id]["hp_current"]
    assert damage["combat_over"] is False

    end_turn_resp = await client.post(f"/game/combat/{session_id}/end-turn", headers=headers, json={})
    assert end_turn_resp.status_code == 200, end_turn_resp.text
    assert end_turn_resp.json()["next_turn_index"] == 1

    end_combat_resp = await client.post(f"/game/combat/{session_id}/end", headers=headers)
    assert end_combat_resp.status_code == 200, end_combat_resp.text
    assert end_combat_resp.json()["ok"] is True

    post_combat_session = await client.get(f"/game/sessions/{session_id}", headers=headers)
    assert post_combat_session.status_code == 200, post_combat_session.text
    assert post_combat_session.json()["combat_active"] is False

    character_row = await db_session.get(Character, character["id"])
    character_row.hp_current = 3
    character_row.hit_dice_remaining = 0
    await db_session.commit()

    rest_resp = await client.post(
        f"/game/sessions/{session_id}/rest",
        headers=headers,
        params={"rest_type": "long"},
    )
    assert rest_resp.status_code == 200, rest_resp.text
    rest_data = rest_resp.json()
    assert rest_data["rest_type"] == "long"
    hero_rest = next(item for item in rest_data["characters"] if item["name"] == "Loop Sentinel")
    assert hero_rest["hp_current"] == hero_rest["hp_max"]
    assert hero_rest["hit_dice_restored"] >= 1

    checkpoint_resp = await client.post(f"/game/sessions/{session_id}/checkpoint", headers=headers)
    assert checkpoint_resp.status_code == 200, checkpoint_resp.text
    assert checkpoint_resp.json()["ok"] is True
    assert "quest_log" in checkpoint_resp.json()["campaign_state"]

    checkpoint_restore = await client.get(f"/game/sessions/{session_id}/checkpoint", headers=headers)
    assert checkpoint_restore.status_code == 200, checkpoint_restore.text
    assert checkpoint_restore.json()["has_checkpoint"] is True
    assert checkpoint_restore.json()["campaign_state"] == checkpoint_resp.json()["campaign_state"]

    session_row = (await db_session.execute(select(Session).where(Session.id == session_id))).scalar_one()
    assert session_row.combat_active is False
