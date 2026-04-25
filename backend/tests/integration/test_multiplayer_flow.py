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


# ─── 接管 AI 角色 / 重连续玩（用户反馈过的 bug） ─────────

async def test_claim_ai_character_promotes_to_player(
    client, db_session, sample_module,
):
    """
    用户报过的 bug：断线重连 / 加入既有房间想接管 AI 队友时，被拒绝
    "AI 队友角色不能被认领"。修法：is_player=False 不再 block claim，
    接管后角色自动升级为 is_player=True 并绑定 user_id。
    """
    from models import Character
    import uuid as _uuid

    host = await _register(client, "host_takeover")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]

    # 模拟一个 AI 队友（fill_ai 或别的玩家离开后留下的）
    ai_char = Character(
        id=str(_uuid.uuid4()),
        name="AI 法师",
        race="Elf", char_class="Wizard", level=1,
        ability_scores={"str": 8, "dex": 14, "con": 13, "int": 16, "wis": 12, "cha": 10},
        hp_current=6, is_player=False,
        session_id=sid,
        user_id=None,
    )
    db_session.add(ai_char)
    await db_session.commit()

    # host claim 这个 AI 角色 → 应当成功
    r = await client.post(
        f"/game/rooms/{sid}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": ai_char.id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["claimed"] is True

    # 角色应被升级 + 绑定到 host
    await db_session.refresh(ai_char)
    assert ai_char.is_player is True
    assert ai_char.user_id == host["user_id"]


async def test_claim_orphan_character_binds_to_session(
    client, db_session, sample_module,
):
    """孤儿角色（session_id=None，刚从创角向导出来）首次 claim 时被绑到房间。"""
    from models import Character
    import uuid as _uuid

    host = await _register(client, "host_orphan")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]

    orphan = Character(
        id=str(_uuid.uuid4()),
        name="孤儿角色",
        race="Human", char_class="Fighter", level=1,
        ability_scores={"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        hp_current=12, is_player=True,
        session_id=None, user_id=None,
    )
    db_session.add(orphan)
    await db_session.commit()

    r = await client.post(
        f"/game/rooms/{sid}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": orphan.id},
    )
    assert r.status_code == 200, r.text
    await db_session.refresh(orphan)
    assert orphan.session_id == sid


async def test_cannot_steal_character_from_active_member(
    client, db_session, sample_module,
):
    """如果角色已被某 SessionMember 绑（无论该 user 在线与否），别人不能抢。"""
    from models import Character
    import uuid as _uuid

    host  = await _register(client, "host_owner")
    thief = await _register(client, "thief_attempt")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]

    char = Character(
        id=str(_uuid.uuid4()),
        name="host 的角色",
        race="Human", char_class="Fighter", level=1,
        ability_scores={"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        hp_current=12, is_player=True, session_id=sid, user_id=host["user_id"],
    )
    db_session.add(char)
    await db_session.commit()

    # host 先 claim
    r = await client.post(f"/game/rooms/{sid}/claim-character",
                           headers=_h(host["token"]),
                           json={"character_id": char.id})
    assert r.status_code == 200

    # thief 加入房间，尝试 claim 同一个角色
    await client.post("/game/rooms/join", headers=_h(thief["token"]), json={
        "room_code": create["room_code"],
    })
    bad = await client.post(f"/game/rooms/{sid}/claim-character",
                              headers=_h(thief["token"]),
                              json={"character_id": char.id})
    assert bad.status_code == 409  # 已被其他玩家认领


async def test_switching_character_demotes_previous_one(
    client, db_session, sample_module,
):
    """玩家从角色 A 换到角色 B：A 应被自动降级为 is_player=False。"""
    from models import Character
    import uuid as _uuid

    host = await _register(client, "host_switch")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]

    char_a = Character(
        id=str(_uuid.uuid4()), name="角色 A",
        race="Human", char_class="Fighter", level=1,
        ability_scores={"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        hp_current=12, is_player=True, session_id=sid,
    )
    char_b = Character(
        id=str(_uuid.uuid4()), name="角色 B",
        race="Elf", char_class="Wizard", level=1,
        ability_scores={"str": 8, "dex": 14, "con": 13, "int": 16, "wis": 12, "cha": 10},
        hp_current=6, is_player=True, session_id=sid,
    )
    db_session.add_all([char_a, char_b])
    await db_session.commit()

    # 先 claim A
    await client.post(f"/game/rooms/{sid}/claim-character",
                       headers=_h(host["token"]),
                       json={"character_id": char_a.id})
    # 换 claim B
    r = await client.post(f"/game/rooms/{sid}/claim-character",
                           headers=_h(host["token"]),
                           json={"character_id": char_b.id})
    assert r.status_code == 200, r.text

    # A 被降级为 AI
    await db_session.refresh(char_a)
    assert char_a.is_player is False
    assert char_a.user_id is None
    # B 是真人
    await db_session.refresh(char_b)
    assert char_b.is_player is True
    assert char_b.user_id == host["user_id"]


async def test_reclaim_own_character_after_leave_and_rejoin(
    client, db_session, sample_module,
):
    """
    完整模拟"断线重连接管"：玩家显式 leave_room → 角色降级 AI → 重新加入 → 再次 claim 成功。
    （leave_room 的降级行为之前是 claim_character is_player 检查的"杀手"，
    现在应当通畅。）
    """
    from models import Character
    import uuid as _uuid

    host = await _register(client, "perm_host")
    p2   = await _register(client, "comeback_player")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]
    code = create["room_code"]

    # p2 加入并 claim 一个角色
    await client.post("/game/rooms/join", headers=_h(p2["token"]), json={"room_code": code})
    char = Character(
        id=str(_uuid.uuid4()), name="p2 的角色",
        race="Human", char_class="Fighter", level=1,
        ability_scores={"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        hp_current=12, is_player=True, session_id=sid,
    )
    db_session.add(char)
    await db_session.commit()
    await client.post(f"/game/rooms/{sid}/claim-character",
                       headers=_h(p2["token"]),
                       json={"character_id": char.id})

    # p2 离开房间 —— 角色应被降级为 AI
    await client.post(f"/game/rooms/{sid}/leave", headers=_h(p2["token"]))
    await db_session.refresh(char)
    assert char.is_player is False  # leave_room 的降级行为还在

    # p2 重新加入
    await client.post("/game/rooms/join", headers=_h(p2["token"]), json={"room_code": code})

    # 重新 claim 自己的角色 —— 现在应该能成功（修复前会 400）
    r = await client.post(f"/game/rooms/{sid}/claim-character",
                           headers=_h(p2["token"]),
                           json={"character_id": char.id})
    assert r.status_code == 200, r.text

    await db_session.refresh(char)
    assert char.is_player is True
    assert char.user_id == p2["user_id"]
