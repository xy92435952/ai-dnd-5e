import json

import pytest
from sqlalchemy import select

from models import Character, CombatState, Module, Session
from services.combat_service import AttackResult
from services.smoke_scenario_seed import build_smoke_module_content

pytestmark = pytest.mark.integration


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, username: str, display_name: str) -> dict:
    response = await client.post("/auth/register", json={
        "username": username,
        "password": "password",
        "display_name": display_name,
    })
    assert response.status_code == 200, response.text
    return response.json()


async def _create_ready_module(db_session) -> Module:
    module = Module(
        id="mp-happy-module-1",
        user_id=None,
        name="Multiplayer Happy Path Crossing",
        file_path="seeded://multiplayer-happy-path",
        file_type="seed",
        parsed_content=build_smoke_module_content(),
        parse_status="done",
        parse_error=None,
        level_min=2,
        level_max=3,
        recommended_party_size=4,
    )
    db_session.add(module)
    await db_session.commit()
    return module


async def _create_character(client, user: dict, module_id: str, *, name: str, class_name: str) -> dict:
    response = await client.post("/characters/create", headers=_h(user["token"]), json={
        "module_id": module_id,
        "name": name,
        "race": "Human",
        "char_class": class_name,
        "level": 3,
        "background": "Soldier" if class_name == "Fighter" else "Sage",
        "alignment": "Neutral Good",
        "ability_scores": {"str": 15, "dex": 13, "con": 14, "int": 13, "wis": 12, "cha": 10},
        "proficient_skills": ["运动", "感知"] if class_name == "Fighter" else ["奥秘", "调查"],
        "fighting_style": "Defense" if class_name == "Fighter" else None,
        "equipment_choice": 0,
        "known_spells": ["Shield"] if class_name == "Wizard" else [],
    })
    assert response.status_code == 200, response.text
    return response.json()


async def _ready_all(client, session_id: str, users: list[dict]) -> None:
    for user in users:
        response = await client.post(
            f"/game/rooms/{session_id}/start-ready",
            headers=_h(user["token"]),
            json={"ready": True},
        )
        assert response.status_code == 200, response.text


async def test_four_player_multiplayer_happy_path_room_to_combat_reaction_and_end(
    client,
    db_session,
    sample_module,
    monkeypatch,
):
    """Repeatable 4-player smoke for room, ownership, exploration, combat, reaction, and combat end."""
    import services.ai_combat_agent as ai_agent
    import services.combat_narrator as narrator
    import services.dnd_dice as dice
    import services.langgraph_client as lc
    import api.combat.ai_turn_attack as ai_turn_attack
    import api.combat.reactions as reaction_api

    users = [
        await _register(client, "mp_happy_host", "Host Player"),
        await _register(client, "mp_happy_guest_1", "Guest One"),
        await _register(client, "mp_happy_guest_2", "Guest Two"),
        await _register(client, "mp_happy_guest_3", "Guest Three"),
    ]
    module = await _create_ready_module(db_session)
    module_id = module.id

    created = await client.post("/game/rooms/create", headers=_h(users[0]["token"]), json={
        "module_id": module_id,
        "save_name": "4P Happy Path",
        "max_players": 4,
        "dm_style": "classic",
    })
    assert created.status_code == 200, created.text
    room_seed = created.json()
    session_id = room_seed["session_id"]

    for user in users[1:]:
        joined = await client.post("/game/rooms/join", headers=_h(user["token"]), json={
            "room_code": room_seed["room_code"],
        })
        assert joined.status_code == 200, joined.text
        assert len(joined.json()["members"]) <= 4

    characters = [
        await _create_character(client, users[0], module_id, name="Host Sentinel", class_name="Fighter"),
        await _create_character(client, users[1], module_id, name="Guest Shieldmage", class_name="Wizard"),
        await _create_character(client, users[2], module_id, name="Guest Scout", class_name="Fighter"),
        await _create_character(client, users[3], module_id, name="Guest Guard", class_name="Fighter"),
    ]
    for user, character in zip(users, characters):
        claimed = await client.post(
            f"/game/rooms/{session_id}/claim-character",
            headers=_h(user["token"]),
            json={"character_id": character["id"]},
        )
        assert claimed.status_code == 200, claimed.text
        assert claimed.json()["character_id"] == character["id"]

    await _ready_all(client, session_id, users)

    started = await client.post(f"/game/rooms/{session_id}/start", headers=_h(users[0]["token"]))
    assert started.status_code == 200, started.text
    assert started.json()["started"] is True

    room = (await client.get(f"/game/rooms/{session_id}", headers=_h(users[0]["token"]))).json()
    assert room["game_started"] is True
    assert room["current_speaker_user_id"] == users[0]["user_id"]
    assert {member["character_id"] for member in room["members"]} == {character["id"] for character in characters}

    session_restore = await client.get(f"/game/sessions/{session_id}", headers=_h(users[1]["token"]))
    assert session_restore.status_code == 200, session_restore.text
    assert session_restore.json()["player"]["id"] == characters[1]["id"]
    assert session_restore.json()["game_state"]["dm_style"] == "classic"

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "combat_start",
                "narrative": "The whole table pushes into the training yard as a clockwork sentry attacks.",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {
                    "combat_trigger": True,
                    "combat_trigger_reason": "The party enters the live training yard.",
                    "initial_enemies": [{
                        "name": "Clockwork Sentry",
                        "hp": 16,
                        "ac": 13,
                        "attack_bonus": 4,
                        "damage_dice": "1d6+2",
                    }],
                },
                "needs_check": {"required": False},
                "combat_triggered": True,
                "combat_ended": False,
                "dice_display": [],
            }, ensure_ascii=False),
            "success": True,
        }

    async def fake_ai_decision(**kwargs):
        return {"action_type": "attack", "target_id": characters[1]["id"], "reason": "test reaction target"}

    def fake_resolve_melee_attack(*_args, **_kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 16,
                "target_ac": 12,
            },
            damage=4,
            damage_roll={"formula": "1d6+2", "rolls": [2], "total": 4},
            narration="hit",
        )

    async def fake_narrate_action(**_kwargs):
        return ""

    async def fake_narrate_batch(actions):
        return ["" for _ in actions]

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(dice.random, "randint", lambda low, high: high)
    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(narrator, "narrate_action", fake_narrate_action)
    monkeypatch.setattr(reaction_api, "narrate_action", fake_narrate_action)

    action = await client.post("/game/action", headers=_h(users[0]["token"]), json={
        "session_id": session_id,
        "action_text": "We enter the training yard together.",
        "idempotency_key": "mp-happy-trigger-combat",
    })
    assert action.status_code == 200, action.text
    assert action.json()["combat_triggered"] is True

    combat_payload = (await client.get(f"/game/combat/{session_id}", headers=_h(users[0]["token"]))).json()
    assert all(character["id"] in combat_payload["entities"] for character in characters)
    enemy = next(entity for entity in combat_payload["entities"].values() if entity["is_enemy"])

    current_turn = combat_payload["turn_order"][combat_payload["current_turn_index"]]
    assert current_turn["character_id"] == characters[0]["id"]

    bad_attack = await client.post(f"/game/combat/{session_id}/attack-roll", headers=_h(users[2]["token"]), json={
        "entity_id": characters[2]["id"],
        "target_id": enemy["id"],
        "action_type": "ranged",
        "d20_value": 18,
    })
    assert bad_attack.status_code == 403
    assert "不是你的回合" in bad_attack.text

    attack = await client.post(f"/game/combat/{session_id}/attack-roll", headers=_h(users[0]["token"]), json={
        "entity_id": characters[0]["id"],
        "target_id": enemy["id"],
        "action_type": "ranged",
        "d20_value": 18,
    })
    assert attack.status_code == 200, attack.text
    assert attack.json()["hit"] is True

    damage = await client.post(f"/game/combat/{session_id}/damage-roll", headers=_h(users[0]["token"]), json={
        "pending_attack_id": attack.json()["pending_attack_id"],
        "damage_values": [4],
    })
    assert damage.status_code == 200, damage.text
    assert damage.json()["target_new_hp"] < enemy["hp_current"]

    combat_row = (
        await db_session.execute(select(CombatState).where(CombatState.session_id == session_id))
    ).scalars().first()
    enemy_turn_index = next(
        index
        for index, turn in enumerate(combat_row.turn_order or [])
        if turn["character_id"] == enemy["id"]
    )
    combat_row.current_turn_index = enemy_turn_index
    positions = dict(combat_row.entity_positions or {})
    positions[enemy["id"]] = {"x": 5, "y": 5}
    positions[characters[1]["id"]] = {"x": 6, "y": 5}
    combat_row.entity_positions = positions

    wizard = await db_session.get(Character, characters[1]["id"])
    wizard.known_spells = ["Shield"]
    wizard.spell_slots = {"1st": 1}
    await db_session.commit()

    ai_turn = await client.post(f"/game/combat/{session_id}/ai-turn", headers=_h(users[0]["token"]))
    assert ai_turn.status_code == 200, ai_turn.text
    ai_body = ai_turn.json()
    assert ai_body["target_id"] == characters[1]["id"]
    assert ai_body["player_can_react"] is True
    assert ai_body["reaction_prompt"]["reactor_character_id"] == characters[1]["id"]
    assert ai_body["reaction_prompt"]["available_reactions"][0]["type"] == "shield"

    reaction = await client.post(f"/game/combat/{session_id}/reaction", headers=_h(users[1]["token"]), json={
        "reaction_type": "shield",
        "target_id": enemy["id"],
        "character_id": characters[1]["id"],
    })
    assert reaction.status_code == 200, reaction.text
    assert reaction.json()["reaction_effect"]["damage_prevented"] == 4
    assert reaction.json()["turn_state"]["reaction_used"] is True

    await db_session.refresh(wizard)
    assert wizard.spell_slots["1st"] == 0
    assert wizard.hp_current == wizard.derived["hp_max"]

    end_combat = await client.post(f"/game/combat/{session_id}/end", headers=_h(users[0]["token"]))
    assert end_combat.status_code == 200, end_combat.text
    assert end_combat.json()["ok"] is True

    final_session = await client.get(f"/game/sessions/{session_id}", headers=_h(users[3]["token"]))
    assert final_session.status_code == 200, final_session.text
    assert final_session.json()["combat_active"] is False

    session_row = (await db_session.execute(select(Session).where(Session.id == session_id))).scalar_one()
    assert session_row.combat_active is False
    assert session_row.is_multiplayer is True
