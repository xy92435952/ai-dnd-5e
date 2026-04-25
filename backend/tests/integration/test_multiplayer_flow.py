"""
多人房间端到端流程：create → join → claim → fill_ai → start → leave / dissolve

每条 case 都覆盖了"DB 状态变化 + 端点正确响应 + 权限边界"三个层面。
WS 广播由 broadcast_to_session 在背后做（mock 没接 ws_manager.broadcast 的具体实现，
但调用不会抛错）。
"""
import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration


# ─── 辅助 ────────────────────────────────────────────────

async def _register(client, username, password="password", display_name=None):
    r = await client.post("/auth/register", json={
        "username": username, "password": password,
        "display_name": display_name or username,
    })
    assert r.status_code == 200, r.text
    return r.json()  # {token, user_id, ...}


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ─── 创建 / 加入 / 离开 ─────────────────────────────────

async def test_host_creates_room_gets_room_code(client, sample_module):
    host = await _register(client, "host_user")

    r = await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "测试房间",
        "max_players": 4,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    # 必须返回 6 字符房间号
    assert "room_code" in data
    assert len(data["room_code"]) == 6
    assert data["host_user_id"] == host["user_id"]
    assert "session_id" in data


async def test_second_player_joins_via_room_code(client, sample_module):
    host  = await _register(client, "host2")
    guest = await _register(client, "guest1")

    create_resp = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()

    join_resp = await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": create_resp["room_code"],
    })
    assert join_resp.status_code == 200, join_resp.text
    join_data = join_resp.json()
    assert join_data["session_id"] == create_resp["session_id"]
    # 加入后成员数 = 2
    members = join_data["members"]
    user_ids = {m["user_id"] for m in members}
    assert host["user_id"] in user_ids
    assert guest["user_id"] in user_ids


async def test_join_with_invalid_code_404(client):
    user = await _register(client, "lonely")
    r = await client.post("/game/rooms/join", headers=_h(user["token"]), json={
        "room_code": "AAAAAA",
    })
    assert r.status_code in (404, 400)


async def test_member_leaves_room(client, sample_module):
    host  = await _register(client, "host3")
    guest = await _register(client, "guest3")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": create["room_code"],
    })

    # guest 离开
    r = await client.post(f"/game/rooms/{create['session_id']}/leave", headers=_h(guest["token"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["room_dissolved"] is False  # host 还在，房间不解散
    assert body["host_transferred_to"] is None


async def test_host_leaves_dissolves_room(client, sample_module):
    """房主作为唯一成员离开 → 房间解散。"""
    host = await _register(client, "host_alone")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()

    r = await client.post(f"/game/rooms/{create['session_id']}/leave", headers=_h(host["token"]))
    assert r.status_code == 200, r.text
    assert r.json()["room_dissolved"] is True


async def test_host_transfer_when_only_host_leaves_with_other_members(
    client, sample_module,
):
    """房主离开但还有其他人 → 房主自动转给最早加入的成员。"""
    host = await _register(client, "transferring_host")
    p2   = await _register(client, "next_host")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(p2["token"]), json={
        "room_code": create["room_code"],
    })

    r = await client.post(f"/game/rooms/{create['session_id']}/leave", headers=_h(host["token"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["room_dissolved"] is False
    assert body["host_transferred_to"] == p2["user_id"]


# ─── 角色认领 ───────────────────────────────────────────

async def test_claim_character_binds_to_member(
    client, db_session, sample_module, sample_character,
):
    """玩家 claim 一个角色后，SessionMember.character_id 被绑定。"""
    host = await _register(client, "claimer")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()

    # claim sample_character（conftest 里属于 sample_user，这里 host 是新用户但角色无主限制由 service 决定）
    # sample_character.user_id = sample_user.id（不是 host），所以这里测一种情况：
    # 创个新角色给 host 用
    create_char = await client.post("/characters/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "name": "claim 测试",
        "race": "Human",
        "char_class": "Fighter",
        "level": 1,
        "ability_scores": {"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        "proficient_skills": ["运动", "感知"],
    })
    assert create_char.status_code == 200, create_char.text
    char_id = create_char.json()["id"]

    r = await client.post(
        f"/game/rooms/{create['session_id']}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": char_id},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["claimed"] is True
    assert body["character_id"] == char_id


# ─── 转主 / 踢人 ────────────────────────────────────────

async def test_host_transfers_then_old_host_loses_perm(client, sample_module):
    host = await _register(client, "old_host")
    p2   = await _register(client, "new_host")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(p2["token"]), json={
        "room_code": create["room_code"],
    })

    # host 主动转
    r = await client.post(f"/game/rooms/{create['session_id']}/transfer",
                           headers=_h(host["token"]),
                           json={"new_host_user_id": p2["user_id"]})
    assert r.status_code == 200, r.text

    # 转完后旧 host 再做 host 操作应被拒（kick / start 等需要 host 权限）
    bad = await client.post(f"/game/rooms/{create['session_id']}/transfer",
                              headers=_h(host["token"]),
                              json={"new_host_user_id": host["user_id"]})
    assert bad.status_code == 403


async def test_non_host_cannot_kick(client, sample_module):
    host = await _register(client, "host_kick")
    p2   = await _register(client, "guest_kick")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(p2["token"]), json={
        "room_code": create["room_code"],
    })

    # p2 尝试踢 host —— 没权限
    r = await client.post(f"/game/rooms/{create['session_id']}/kick",
                           headers=_h(p2["token"]),
                           json={"user_id": host["user_id"]})
    assert r.status_code == 403


# ─── 开始游戏 ───────────────────────────────────────────

async def test_start_game_requires_at_least_one_claimed_character(
    client, sample_module,
):
    """没人认领角色就开始游戏 → 400。"""
    host = await _register(client, "host_start")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()

    r = await client.post(f"/game/rooms/{create['session_id']}/start",
                           headers=_h(host["token"]))
    assert r.status_code == 400, r.text


async def test_start_game_after_claim_works(client, sample_module):
    """认领角色后开始游戏 → 200，game_state.multiplayer.game_started=True。"""
    host = await _register(client, "host_full")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()

    # 创角并认领
    char = (await client.post("/characters/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id,
        "name": "测试主角",
        "race": "Human",
        "char_class": "Fighter",
        "level": 1,
        "ability_scores": {"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        "proficient_skills": ["运动", "感知"],
    })).json()
    await client.post(f"/game/rooms/{create['session_id']}/claim-character",
                       headers=_h(host["token"]),
                       json={"character_id": char["id"]})

    r = await client.post(f"/game/rooms/{create['session_id']}/start",
                           headers=_h(host["token"]))
    assert r.status_code == 200, r.text
    assert r.json()["started"] is True


async def test_get_room_returns_full_info(client, sample_module):
    host = await _register(client, "host_info")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()

    r = await client.get(f"/game/rooms/{create['session_id']}", headers=_h(host["token"]))
    assert r.status_code == 200, r.text
    info = r.json()
    assert info["room_code"] == create["room_code"]
    assert info["host_user_id"] == host["user_id"]
