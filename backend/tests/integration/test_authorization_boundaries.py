import uuid

import pytest

from models import Character, CombatState, GameLog, Module, Session, SessionMember

pytestmark = pytest.mark.integration


async def _register(client, username):
    response = await client.post("/auth/register", json={
        "username": username,
        "password": "password",
        "display_name": username,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _character(owner_id, **overrides):
    data = {
        "id": str(uuid.uuid4()),
        "user_id": owner_id,
        "is_player": True,
        "name": "Boundary Fighter",
        "race": "Human",
        "char_class": "Fighter",
        "level": 1,
        "ability_scores": {"str": 14, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        "derived": {
            "hp_max": 12,
            "ac": 16,
            "initiative": 1,
            "ability_modifiers": {"str": 2, "dex": 1, "con": 2, "int": 0, "wis": 0, "cha": 0},
        },
        "hp_current": 12,
        "equipment": {"gold": 100, "gear": []},
        "proficient_skills": [],
        "proficient_saves": [],
    }
    data.update(overrides)
    return Character(**data)


async def test_private_module_rejects_cross_user_read_delete_session_and_room(
    client,
    db_session,
):
    owner = await _register(client, f"mod_owner_{uuid.uuid4().hex[:8]}")
    outsider = await _register(client, f"mod_outsider_{uuid.uuid4().hex[:8]}")

    module = Module(
        id=str(uuid.uuid4()),
        user_id=owner["user_id"],
        name="Private Module",
        file_path="",
        file_type="md",
        parsed_content={"scenes": [{"description": "Private opening"}]},
        parse_status="done",
    )
    char = _character(owner["user_id"])
    db_session.add_all([module, char])
    await db_session.commit()

    read = await client.get(f"/modules/{module.id}", headers=_h(outsider["token"]))
    assert read.status_code == 403

    delete = await client.delete(f"/modules/{module.id}", headers=_h(outsider["token"]))
    assert delete.status_code == 403

    create_session = await client.post(
        "/game/sessions",
        headers=_h(outsider["token"]),
        json={
            "module_id": module.id,
            "player_character_id": char.id,
            "companion_ids": [],
        },
    )
    assert create_session.status_code == 403

    create_room = await client.post(
        "/game/rooms/create",
        headers=_h(outsider["token"]),
        json={"module_id": module.id, "save_name": "bad", "max_players": 4},
    )
    assert create_room.status_code == 403


async def test_shared_module_can_be_read_and_used_but_not_deleted(client, db_session):
    user = await _register(client, f"shared_user_{uuid.uuid4().hex[:8]}")
    module = Module(
        id=str(uuid.uuid4()),
        user_id=None,
        name="Shared Module",
        file_path="",
        file_type="md",
        parsed_content={"scenes": [{"description": "Shared opening"}]},
        parse_status="done",
    )
    char = _character(user["user_id"])
    db_session.add_all([module, char])
    await db_session.commit()

    read = await client.get(f"/modules/{module.id}", headers=_h(user["token"]))
    assert read.status_code == 200

    session = await client.post(
        "/game/sessions",
        headers=_h(user["token"]),
        json={
            "module_id": module.id,
            "player_character_id": char.id,
            "companion_ids": [],
        },
    )
    assert session.status_code == 200, session.text

    delete = await client.delete(f"/modules/{module.id}", headers=_h(user["token"]))
    assert delete.status_code == 403


async def test_character_and_inventory_reject_cross_user_access(client, db_session):
    owner = await _register(client, f"char_owner_{uuid.uuid4().hex[:8]}")
    outsider = await _register(client, f"char_outsider_{uuid.uuid4().hex[:8]}")
    char = _character(owner["user_id"])
    db_session.add(char)
    await db_session.commit()

    read = await client.get(f"/characters/{char.id}", headers=_h(outsider["token"]))
    assert read.status_code == 403

    level = await client.post(
        f"/characters/{char.id}/level-up",
        headers=_h(outsider["token"]),
        json={"use_average_hp": True},
    )
    assert level.status_code == 403

    buy = await client.post(
        f"/characters/{char.id}/shop/buy",
        headers=_h(outsider["token"]),
        json={"item_name": "Healing Potion", "item_category": "gear", "quantity": 1},
    )
    assert buy.status_code == 403


async def test_skill_check_rejects_cross_session_log_write(
    client,
    db_session,
    sample_module,
):
    owner = await _register(client, f"check_owner_{uuid.uuid4().hex[:8]}")
    outsider = await _register(client, f"check_outsider_{uuid.uuid4().hex[:8]}")
    char = _character(owner["user_id"], proficient_skills=["Athletics"])
    session = Session(
        id=str(uuid.uuid4()),
        user_id=owner["user_id"],
        module_id=sample_module.id,
        player_character_id=char.id,
        current_scene="Scene",
        game_state={"companion_ids": [], "scene_index": 0, "flags": {}},
    )
    char.session_id = session.id
    db_session.add_all([char, session])
    await db_session.commit()

    denied = await client.post(
        "/game/skill-check",
        headers=_h(outsider["token"]),
        json={
            "session_id": session.id,
            "character_id": char.id,
            "skill": "Athletics",
            "dc": 10,
            "d20_value": 10,
        },
    )
    assert denied.status_code == 403

    result = await db_session.execute(
        GameLog.__table__.select().where(GameLog.session_id == session.id)
    )
    assert result.fetchall() == []


async def test_combat_condition_rejects_non_member_in_multiplayer(
    client,
    db_session,
    sample_module,
):
    host = await _register(client, f"cond_host_{uuid.uuid4().hex[:8]}")
    outsider = await _register(client, f"cond_outsider_{uuid.uuid4().hex[:8]}")
    session = Session(
        id=str(uuid.uuid4()),
        user_id=host["user_id"],
        module_id=sample_module.id,
        is_multiplayer=True,
        room_code="123456",
        host_user_id=host["user_id"],
        max_players=4,
        combat_active=True,
        game_state={"enemies": [{"id": "enemy-1", "conditions": []}]},
    )
    db_session.add(session)
    db_session.add(SessionMember(session_id=session.id, user_id=host["user_id"], role="host"))
    db_session.add(CombatState(session_id=session.id, turn_order=[], entity_positions={}))
    await db_session.commit()

    denied = await client.post(
        f"/game/combat/{session.id}/condition/add",
        headers=_h(outsider["token"]),
        json={"entity_id": "enemy-1", "condition": "poisoned", "is_enemy": True},
    )
    assert denied.status_code == 403


async def test_single_player_combat_action_rejects_other_user(
    client,
    db_session,
    sample_module,
):
    owner = await _register(client, f"sp_owner_{uuid.uuid4().hex[:8]}")
    outsider = await _register(client, f"sp_outsider_{uuid.uuid4().hex[:8]}")
    char = _character(owner["user_id"])
    session = Session(
        id=str(uuid.uuid4()),
        user_id=owner["user_id"],
        module_id=sample_module.id,
        player_character_id=char.id,
        combat_active=True,
        game_state={"enemies": []},
    )
    char.session_id = session.id
    combat = CombatState(
        session_id=session.id,
        turn_order=[{"character_id": char.id, "name": char.name, "is_player": True}],
        current_turn_index=0,
        entity_positions={char.id: {"x": 1, "y": 1}},
    )
    db_session.add_all([char, session, combat])
    await db_session.commit()

    denied = await client.post(
        f"/game/combat/{session.id}/move",
        headers=_h(outsider["token"]),
        json={"entity_id": char.id, "to_x": 2, "to_y": 1},
    )
    assert denied.status_code == 403
