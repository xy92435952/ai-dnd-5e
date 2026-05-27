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


async def _create_character(client, token, module_id, name="测试角色"):
    r = await client.post("/characters/create", headers=_h(token), json={
        "module_id": module_id,
        "name": name,
        "race": "Human",
        "char_class": "Fighter",
        "level": 1,
        "ability_scores": {"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        "proficient_skills": ["运动", "感知"],
    })
    assert r.status_code == 200, r.text
    return r.json()


async def _ready_for_start(client, session_id, *users):
    for user in users:
        r = await client.post(
            f"/game/rooms/{session_id}/start-ready",
            headers=_h(user["token"]),
            json={"ready": True},
        )
        assert r.status_code == 200, r.text


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


async def test_non_member_cannot_restore_multiplayer_room_or_session(client, sample_module):
    host = await _register(client, "mp_boundary_host")
    stranger = await _register(client, "mp_boundary_stranger")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]

    room = await client.get(f"/game/rooms/{sid}", headers=_h(stranger["token"]))
    assert room.status_code == 403

    members = await client.get(f"/game/rooms/{sid}/members", headers=_h(stranger["token"]))
    assert members.status_code == 403

    session = await client.get(f"/game/sessions/{sid}", headers=_h(stranger["token"]))
    assert session.status_code == 403


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


async def test_two_player_room_cannot_start_kick_vote(client, sample_module):
    host = await _register(client, "host_kick")
    p2   = await _register(client, "guest_kick")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(p2["token"]), json={
        "room_code": create["room_code"],
    })

    # 两人房只有 1 个非目标投票人，不允许单人决定移出另一个玩家。
    r = await client.post(f"/game/rooms/{create['session_id']}/kick",
                           headers=_h(p2["token"]),
                           json={"user_id": host["user_id"]})
    assert r.status_code == 409
    assert "至少需要 3 名成员" in r.text


async def test_kick_member_requires_room_vote_majority(client, sample_module):
    host = await _register(client, "vote_host")
    p2 = await _register(client, "vote_p2")
    p3 = await _register(client, "vote_p3")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    for user in (p2, p3):
        joined = await client.post("/game/rooms/join", headers=_h(user["token"]), json={
            "room_code": create["room_code"],
        })
        assert joined.status_code == 200, joined.text

    first_vote = await client.post(
        f"/game/rooms/{create['session_id']}/kick",
        headers=_h(p2["token"]),
        json={"user_id": p3["user_id"]},
    )
    assert first_vote.status_code == 200, first_vote.text
    first_body = first_vote.json()
    assert first_body["kicked"] is None
    assert first_body["vote_pending"] is True
    assert first_body["vote"]["target_user_id"] == p3["user_id"]
    assert first_body["vote"]["yes_user_ids"] == [p2["user_id"]]
    assert first_body["vote"]["threshold"] == 2

    room_after_first = (await client.get(
        f"/game/rooms/{create['session_id']}",
        headers=_h(host["token"]),
    )).json()
    assert room_after_first["room_votes"][0]["target_user_id"] == p3["user_id"]

    second_vote = await client.post(
        f"/game/rooms/{create['session_id']}/kick",
        headers=_h(host["token"]),
        json={"user_id": p3["user_id"]},
    )
    assert second_vote.status_code == 200, second_vote.text
    second_body = second_vote.json()
    assert second_body["kicked"] == p3["user_id"]
    assert second_body["vote_pending"] is False

    room_after_pass = (await client.get(
        f"/game/rooms/{create['session_id']}",
        headers=_h(host["token"]),
    )).json()
    assert {member["user_id"] for member in room_after_pass["members"]} == {
        host["user_id"],
        p2["user_id"],
    }
    assert room_after_pass["room_votes"] == []


async def test_four_player_kick_vote_passes_with_two_of_three_eligible_voters(client, sample_module):
    host = await _register(client, "vote4_host")
    p2 = await _register(client, "vote4_p2")
    p3 = await _register(client, "vote4_p3")
    target = await _register(client, "vote4_target")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    for user in (p2, p3, target):
        joined = await client.post("/game/rooms/join", headers=_h(user["token"]), json={
            "room_code": create["room_code"],
        })
        assert joined.status_code == 200, joined.text

    first_vote = await client.post(
        f"/game/rooms/{create['session_id']}/kick",
        headers=_h(p2["token"]),
        json={"user_id": target["user_id"]},
    )
    assert first_vote.status_code == 200, first_vote.text
    first_body = first_vote.json()
    assert first_body["kicked"] is None
    assert first_body["vote_pending"] is True
    assert first_body["vote"]["threshold"] == 2
    assert first_body["vote"]["eligible_voter_user_ids"] == [
        host["user_id"],
        p2["user_id"],
        p3["user_id"],
    ]
    assert first_body["vote"]["yes_user_ids"] == [p2["user_id"]]

    second_vote = await client.post(
        f"/game/rooms/{create['session_id']}/kick",
        headers=_h(host["token"]),
        json={"user_id": target["user_id"]},
    )
    assert second_vote.status_code == 200, second_vote.text
    second_body = second_vote.json()
    assert second_body["kicked"] == target["user_id"]
    assert second_body["vote_pending"] is False
    assert second_body["vote"]["threshold"] == 2
    assert second_body["vote"]["yes_user_ids"] == [p2["user_id"], host["user_id"]]

    room_after_pass = (await client.get(
        f"/game/rooms/{create['session_id']}",
        headers=_h(host["token"]),
    )).json()
    assert {member["user_id"] for member in room_after_pass["members"]} == {
        host["user_id"],
        p2["user_id"],
        p3["user_id"],
    }
    assert room_after_pass["room_votes"] == []


async def test_kick_vote_target_cannot_vote_on_their_own_removal(client, sample_module):
    host = await _register(client, "vote_self_host")
    voter = await _register(client, "vote_self_voter")
    target = await _register(client, "vote_self_target")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    for user in (voter, target):
        joined = await client.post("/game/rooms/join", headers=_h(user["token"]), json={
            "room_code": create["room_code"],
        })
        assert joined.status_code == 200, joined.text

    first_vote = await client.post(
        f"/game/rooms/{create['session_id']}/kick",
        headers=_h(voter["token"]),
        json={"user_id": target["user_id"]},
    )
    assert first_vote.status_code == 200, first_vote.text
    assert first_vote.json()["vote_pending"] is True

    target_vote = await client.post(
        f"/game/rooms/{create['session_id']}/kick",
        headers=_h(target["token"]),
        json={"user_id": target["user_id"]},
    )
    assert target_vote.status_code == 400

    room_after_target_attempt = (await client.get(
        f"/game/rooms/{create['session_id']}",
        headers=_h(host["token"]),
    )).json()
    vote = room_after_target_attempt["room_votes"][0]
    assert vote["target_user_id"] == target["user_id"]
    assert vote["yes_user_ids"] == [voter["user_id"]]
    assert target["user_id"] not in vote["eligible_voter_user_ids"]


async def test_kick_vote_transfers_host_when_host_is_removed(client, sample_module, monkeypatch):
    import services.ws_manager as ws_module

    broadcasts = []

    async def fake_broadcast(session_id, event, exclude_user_id=None):
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
        broadcasts.append(payload)
        return 1

    monkeypatch.setattr(ws_module.ws_manager, "broadcast", fake_broadcast)

    host = await _register(client, "vote_host_target")
    p2 = await _register(client, "vote_host_p2")
    p3 = await _register(client, "vote_host_p3")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    for user in (p2, p3):
        joined = await client.post("/game/rooms/join", headers=_h(user["token"]), json={
            "room_code": create["room_code"],
        })
        assert joined.status_code == 200, joined.text

    broadcasts.clear()
    first_vote = await client.post(
        f"/game/rooms/{create['session_id']}/kick",
        headers=_h(p2["token"]),
        json={"user_id": host["user_id"]},
    )
    assert first_vote.status_code == 200, first_vote.text
    assert first_vote.json()["vote_pending"] is True
    assert [event["type"] for event in broadcasts] == ["room_state_updated"]

    broadcasts.clear()
    second_vote = await client.post(
        f"/game/rooms/{create['session_id']}/kick",
        headers=_h(p3["token"]),
        json={"user_id": host["user_id"]},
    )
    assert second_vote.status_code == 200, second_vote.text
    second_body = second_vote.json()
    assert second_body["kicked"] == host["user_id"]
    assert second_body["host_transferred_to"] == p2["user_id"]
    assert [event["type"] for event in broadcasts] == [
        "member_kicked",
        "host_transferred",
        "room_state_updated",
    ]
    assert broadcasts[1]["new_host_user_id"] == p2["user_id"]

    room_after_pass = (await client.get(
        f"/game/rooms/{create['session_id']}",
        headers=_h(p2["token"]),
    )).json()
    assert room_after_pass["host_user_id"] == p2["user_id"]
    assert {member["user_id"] for member in room_after_pass["members"]} == {
        p2["user_id"],
        p3["user_id"],
    }
    roles = {
        member["user_id"]: member["role"]
        for member in room_after_pass["members"]
    }
    assert roles[p2["user_id"]] == "host"
    assert roles[p3["user_id"]] == "player"
    assert room_after_pass["room_votes"] == []


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


async def test_start_game_requires_every_room_member_to_claim_character(
    client, sample_module,
):
    """多人房开局前，当前房间里的每位真人成员都必须已有角色。"""
    host = await _register(client, "host_claim_all")
    guest = await _register(client, "guest_claim_all")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": create["room_code"],
    })

    host_char = await _create_character(client, host["token"], sample_module.id, "房主角色")
    await client.post(
        f"/game/rooms/{create['session_id']}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": host_char["id"]},
    )

    blocked = await client.post(f"/game/rooms/{create['session_id']}/start", headers=_h(host["token"]))
    assert blocked.status_code == 400, blocked.text
    assert "所有玩家都需要认领角色" in blocked.text

    guest_char = await _create_character(client, guest["token"], sample_module.id, "队友角色")
    await client.post(
        f"/game/rooms/{create['session_id']}/claim-character",
        headers=_h(guest["token"]),
        json={"character_id": guest_char["id"]},
    )
    await client.post(
        f"/game/rooms/{create['session_id']}/start-ready",
        headers=_h(host["token"]),
        json={"ready": True},
    )
    await client.post(
        f"/game/rooms/{create['session_id']}/start-ready",
        headers=_h(guest["token"]),
        json={"ready": True},
    )

    started = await client.post(f"/game/rooms/{create['session_id']}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text


async def test_get_session_returns_current_member_character_for_multiplayer(
    client, sample_module,
):
    host = await _register(client, "host_restore_player")
    guest = await _register(client, "guest_restore_player")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": create["room_code"],
    })

    host_char = await _create_character(client, host["token"], sample_module.id, "Host Restore")
    guest_char = await _create_character(client, guest["token"], sample_module.id, "Guest Restore")
    await client.post(
        f"/game/rooms/{create['session_id']}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": host_char["id"]},
    )
    await client.post(
        f"/game/rooms/{create['session_id']}/claim-character",
        headers=_h(guest["token"]),
        json={"character_id": guest_char["id"]},
    )

    host_snapshot = (await client.get(
        f"/game/sessions/{create['session_id']}",
        headers=_h(host["token"]),
    )).json()
    guest_snapshot = (await client.get(
        f"/game/sessions/{create['session_id']}",
        headers=_h(guest["token"]),
    )).json()

    assert host_snapshot["player"]["id"] == host_char["id"]
    assert guest_snapshot["player"]["id"] == guest_char["id"]


async def test_temporary_disconnect_keeps_character_reserved_for_member(
    client, db_session, sample_module,
):
    from models import Character
    from services import room_service

    host = await _register(client, "disconnect_owner_host")
    owner = await _register(client, "disconnect_owner")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_h(owner["token"]), json={
        "room_code": create["room_code"],
    })

    owner_char = await _create_character(
        client,
        owner["token"],
        sample_module.id,
        "Reserved Disconnect Character",
    )
    claimed = await client.post(
        f"/game/rooms/{sid}/claim-character",
        headers=_h(owner["token"]),
        json={"character_id": owner_char["id"]},
    )
    assert claimed.status_code == 200, claimed.text

    await room_service.mark_offline(db_session, sid, owner["user_id"])

    stolen = await client.post(
        f"/game/rooms/{sid}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": owner_char["id"]},
    )
    assert stolen.status_code == 409, stolen.text

    char = await db_session.get(Character, owner_char["id"])
    assert char.user_id == owner["user_id"]
    assert char.is_player is True

    room = (await client.get(f"/game/rooms/{sid}", headers=_h(host["token"]))).json()
    owner_member = next(member for member in room["members"] if member["user_id"] == owner["user_id"])
    assert owner_member["character_id"] == owner_char["id"]
    assert owner_member["is_online"] is False


async def test_started_room_member_can_rejoin_without_reclaiming_character(
    client, db_session, sample_module,
):
    from models import SessionMember
    from services import room_service
    from sqlalchemy import select

    host = await _register(client, "started_reconnect_host")
    guest = await _register(client, "started_reconnect_guest")
    late_user = await _register(client, "started_reconnect_late")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": create["room_code"],
    })

    host_char = await _create_character(client, host["token"], sample_module.id, "Reconnect Host")
    guest_char = await _create_character(client, guest["token"], sample_module.id, "Reconnect Guest")
    for user, char in ((host, host_char), (guest, guest_char)):
        claimed = await client.post(
            f"/game/rooms/{sid}/claim-character",
            headers=_h(user["token"]),
            json={"character_id": char["id"]},
        )
        assert claimed.status_code == 200, claimed.text

    await _ready_for_start(client, sid, host, guest)
    started = await client.post(f"/game/rooms/{sid}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text

    await room_service.mark_offline(db_session, sid, guest["user_id"])

    rejoined = await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": create["room_code"],
    })
    assert rejoined.status_code == 200, rejoined.text

    blocked_late_join = await client.post("/game/rooms/join", headers=_h(late_user["token"]), json={
        "room_code": create["room_code"],
    })
    assert blocked_late_join.status_code == 409

    rows = await db_session.execute(
        select(SessionMember).where(
            SessionMember.session_id == sid,
            SessionMember.user_id == guest["user_id"],
        )
    )
    guest_memberships = rows.scalars().all()
    assert len(guest_memberships) == 1
    assert guest_memberships[0].character_id == guest_char["id"]

    room = (await client.get(f"/game/rooms/{sid}", headers=_h(guest["token"]))).json()
    guest_member = next(member for member in room["members"] if member["user_id"] == guest["user_id"])
    assert guest_member["is_online"] is True
    assert guest_member["character_id"] == guest_char["id"]

    snapshot = (await client.get(f"/game/sessions/{sid}", headers=_h(guest["token"]))).json()
    assert snapshot["player"]["id"] == guest_char["id"]


async def test_get_session_normalizes_multiplayer_group_state_after_join(
    client, sample_module,
):
    host = await _register(client, "session_group_host")
    guest = await _register(client, "session_group_guest")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": create["room_code"],
    })

    snapshot_resp = await client.get(
        f"/game/sessions/{create['session_id']}",
        headers=_h(guest["token"]),
    )
    assert snapshot_resp.status_code == 200, snapshot_resp.text
    snapshot = snapshot_resp.json()

    groups = {
        group["id"]: group
        for group in snapshot["game_state"]["multiplayer"]["party_groups"]
    }
    assert set(groups["main"]["member_user_ids"]) == {
        host["user_id"],
        guest["user_id"],
    }


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
    await client.post(f"/game/rooms/{create['session_id']}/start-ready",
                       headers=_h(host["token"]),
                       json={"ready": True})

    r = await client.post(f"/game/rooms/{create['session_id']}/start",
                           headers=_h(host["token"]))
    assert r.status_code == 200, r.text
    assert r.json()["started"] is True

    room = (await client.get(f"/game/rooms/{create['session_id']}", headers=_h(host["token"]))).json()
    assert room["game_started"] is True
    assert room["current_speaker_user_id"] == host["user_id"]


async def test_multiplayer_action_requires_initialized_current_speaker(client, sample_module):
    """多人探索行动必须有明确当前发言者，不能由未开局房间任意玩家触发。"""
    host = await _register(client, "host_no_speaker")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    char = await _create_character(client, host["token"], sample_module.id, "未开局角色")
    await client.post(
        f"/game/rooms/{create['session_id']}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": char["id"]},
    )

    r = await client.post("/game/action", headers=_h(host["token"]), json={
        "session_id": create["session_id"],
        "action_text": "我先行动。",
    })

    assert r.status_code == 409, r.text
    assert "当前没有发言者" in r.text


async def test_multiplayer_action_rejects_non_current_speaker(client, sample_module):
    """当前发言者之外的玩家不能抢先提交探索行动。"""
    host = await _register(client, "host_speaker_guard")
    guest = await _register(client, "guest_speaker_guard")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": create["room_code"],
    })
    for user, name in [(host, "房主发言者"), (guest, "队友非发言者")]:
        char = await _create_character(client, user["token"], sample_module.id, name)
        await client.post(
            f"/game/rooms/{create['session_id']}/claim-character",
            headers=_h(user["token"]),
            json={"character_id": char["id"]},
        )
    await _ready_for_start(client, create["session_id"], host, guest)
    started = await client.post(f"/game/rooms/{create['session_id']}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text

    r = await client.post("/game/action", headers=_h(guest["token"]), json={
        "session_id": create["session_id"],
        "action_text": "我抢先行动。",
    })

    assert r.status_code == 403, r.text
    assert "现在不是你的发言时机" in r.text


async def test_multiplayer_combat_action_rejects_non_current_turn_player(
    client, db_session, sample_module, monkeypatch,
):
    import uuid as _uuid

    from sqlalchemy.orm.attributes import flag_modified

    from models import CombatState, Session
    from services import action_parser, input_guard

    async def fake_classify_player_input(*_args, **_kwargs):
        return {"verdict": "in_game", "reason": "test", "refusal": ""}

    async def fail_if_parsed(*_args, **_kwargs):
        raise AssertionError("non-current combat player should be rejected before parsing")

    monkeypatch.setattr(input_guard, "classify_player_input", fake_classify_player_input)
    monkeypatch.setattr(action_parser, "parse_combat_action", fail_if_parsed)

    host = await _register(client, "host_combat_turn_guard")
    guest = await _register(client, "guest_combat_turn_guard")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": create["room_code"],
    })

    host_char = await _create_character(client, host["token"], sample_module.id, "Combat Host")
    guest_char = await _create_character(client, guest["token"], sample_module.id, "Combat Guest")
    await client.post(
        f"/game/rooms/{sid}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": host_char["id"]},
    )
    await client.post(
        f"/game/rooms/{sid}/claim-character",
        headers=_h(guest["token"]),
        json={"character_id": guest_char["id"]},
    )
    await _ready_for_start(client, sid, host, guest)
    started = await client.post(f"/game/rooms/{sid}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text

    session = await db_session.get(Session, sid)
    session.combat_active = True
    state = dict(session.game_state or {})
    state["enemies"] = [{
        "id": "guard-1",
        "name": "Guard",
        "hp_current": 9,
        "max_hp": 9,
        "conditions": [],
        "derived": {"hp_max": 9, "ac": 13, "ability_modifiers": {"dex": 1}},
    }]
    session.game_state = state
    flag_modified(session, "game_state")
    db_session.add(CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={
            host_char["id"]: {"x": 5, "y": 5},
            guest_char["id"]: {"x": 4, "y": 5},
            "guard-1": {"x": 6, "y": 5},
        },
        turn_order=[
            {"character_id": host_char["id"], "name": host_char["name"], "initiative": 16, "is_player": True},
            {"character_id": guest_char["id"], "name": guest_char["name"], "initiative": 12, "is_player": True},
            {"character_id": "guard-1", "name": "Guard", "initiative": 8, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={},
    ))
    await db_session.commit()

    response = await client.post("/game/action", headers=_h(guest["token"]), json={
        "session_id": sid,
        "action_text": "I attack the guard.",
    })

    assert response.status_code == 403, response.text


async def test_start_game_requires_ready_votes_after_characters_are_claimed(client, sample_module):
    """所有人认领角色后，还需要每位真人玩家确认准备，房主才能开局。"""
    host = await _register(client, "host_ready_vote")
    guest = await _register(client, "guest_ready_vote")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": create["room_code"],
    })

    for user, name in [(host, "房主已认领"), (guest, "队友已认领")]:
        char = await _create_character(client, user["token"], sample_module.id, name)
        await client.post(
            f"/game/rooms/{create['session_id']}/claim-character",
            headers=_h(user["token"]),
            json={"character_id": char["id"]},
        )

    host_ready = await client.post(
        f"/game/rooms/{create['session_id']}/start-ready",
        headers=_h(host["token"]),
        json={"ready": True},
    )
    assert host_ready.status_code == 200, host_ready.text
    assert host["user_id"] in host_ready.json()["start_ready_user_ids"]

    blocked = await client.post(f"/game/rooms/{create['session_id']}/start", headers=_h(host["token"]))
    assert blocked.status_code == 400, blocked.text
    assert "确认准备" in blocked.text

    guest_ready = await client.post(
        f"/game/rooms/{create['session_id']}/start-ready",
        headers=_h(guest["token"]),
        json={"ready": True},
    )
    assert guest_ready.status_code == 200, guest_ready.text
    assert set(guest_ready.json()["start_ready_user_ids"]) == {host["user_id"], guest["user_id"]}

    started = await client.post(f"/game/rooms/{create['session_id']}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text


async def test_claiming_character_clears_previous_start_ready_vote(client, sample_module):
    """玩家换角色后需要重新确认准备，避免旧准备票误用到新角色。"""
    host = await _register(client, "host_ready_clear")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()

    char_a = await _create_character(client, host["token"], sample_module.id, "旧角色")
    await client.post(
        f"/game/rooms/{create['session_id']}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": char_a["id"]},
    )
    ready = await client.post(
        f"/game/rooms/{create['session_id']}/start-ready",
        headers=_h(host["token"]),
        json={"ready": True},
    )
    assert ready.json()["start_ready_user_ids"] == [host["user_id"]]

    char_b = await _create_character(client, host["token"], sample_module.id, "新角色")
    claimed = await client.post(
        f"/game/rooms/{create['session_id']}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": char_b["id"]},
    )
    assert claimed.status_code == 200, claimed.text
    room = (await client.get(f"/game/rooms/{create['session_id']}", headers=_h(host["token"]))).json()
    assert room["start_ready_user_ids"] == []


async def test_fill_ai_reserves_slots_for_unclaimed_room_members(client, sample_module, monkeypatch):
    """AI 补位按真人成员数预留位置，避免未认领玩家之后再加入队伍导致超过 4 人。"""
    host = await _register(client, "host_fill_reserve")
    guest = await _register(client, "guest_fill_reserve")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": create["room_code"],
    })

    host_char = await _create_character(client, host["token"], sample_module.id, "补位参照角色")
    await client.post(
        f"/game/rooms/{create['session_id']}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": host_char["id"]},
    )

    async def fake_generate_party(**kwargs):
        assert kwargs["party_size"] == 2
        return [
            {
                "name": "补位牧师",
                "race": "Human",
                "class": "Cleric",
                "level": 1,
                "ability_scores": {"str": 10, "dex": 10, "con": 12, "int": 10, "wis": 15, "cha": 10},
                "proficient_skills": ["感知", "医药"],
            },
            {
                "name": "补位游荡者",
                "race": "Human",
                "class": "Rogue",
                "level": 1,
                "ability_scores": {"str": 10, "dex": 15, "con": 12, "int": 12, "wis": 10, "cha": 10},
                "proficient_skills": ["隐匿", "调查"],
            },
        ]

    from services.langgraph_client import langgraph_client
    monkeypatch.setattr(langgraph_client, "generate_party", fake_generate_party)

    filled = await client.post(f"/game/rooms/{create['session_id']}/fill-ai", headers=_h(host["token"]))
    assert filled.status_code == 200, filled.text
    assert filled.json()["generated"] == 2


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
    assert info["active_group_id"] == "main"
    assert info["pending_actions_by_group"] == {"main": []}
    assert info["group_readiness"] == {"main": {}}


async def test_party_group_endpoints_update_room_snapshot(client, sample_module):
    host = await _register(client, "host_groups")
    guest = await _register(client, "guest_groups")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={
        "room_code": create["room_code"],
    })
    sid = create["session_id"]

    joined = await client.post(
        f"/game/rooms/{sid}/groups/join",
        headers=_h(guest["token"]),
        json={"group_id": "alley", "group_name": "后巷组", "location": "酒馆后巷"},
    )
    assert joined.status_code == 200, joined.text
    groups = {group["id"]: group for group in joined.json()["party_groups"]}
    assert groups["alley"]["member_user_ids"] == [guest["user_id"]]

    submitted = await client.post(
        f"/game/rooms/{sid}/groups/actions",
        headers=_h(guest["token"]),
        json={"group_id": "alley", "action_text": "我检查仓库门锁。"},
    )
    assert submitted.status_code == 200, submitted.text
    actions = submitted.json()["pending_actions_by_group"]["alley"]
    assert actions[0]["user_id"] == guest["user_id"]
    assert actions[0]["text"] == "我检查仓库门锁。"
    assert submitted.json()["group_readiness"]["alley"][guest["user_id"]] == "drafting"

    readied = await client.post(
        f"/game/rooms/{sid}/groups/readiness",
        headers=_h(guest["token"]),
        json={"group_id": "alley", "status": "ready"},
    )
    assert readied.status_code == 200, readied.text
    assert readied.json()["group_readiness"]["alley"][guest["user_id"]] == "ready"

    cleared = await client.post(
        f"/game/rooms/{sid}/groups/actions/clear",
        headers=_h(host["token"]),
        json={"group_id": "alley"},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["pending_actions_by_group"]["alley"] == []
    assert cleared.json()["group_readiness"]["alley"] == {}


async def test_focus_group_endpoint_changes_active_group(client, sample_module):
    host = await _register(client, "host_focus")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]

    joined = await client.post(
        f"/game/rooms/{sid}/groups/join",
        headers=_h(host["token"]),
        json={"group_id": "alley", "group_name": "后巷组", "location": "酒馆后巷"},
    )
    assert joined.status_code == 200, joined.text
    assert joined.json()["active_group_id"] == "alley"

    focused = await client.post(
        f"/game/rooms/{sid}/groups/focus",
        headers=_h(host["token"]),
        json={"group_id": "main"},
    )
    assert focused.status_code == 200, focused.text
    assert focused.json()["active_group_id"] == "main"


async def test_multiplayer_player_action_aggregates_group_actions_on_backend(
    client, db_session, sample_module, monkeypatch,
):
    """多人探索行动应由后端聚合同分队 pending actions，并在成功后清空该分队队列。"""
    import json
    import uuid as _uuid
    from models import Character
    import services.langgraph_client as lc

    seen = {}

    async def fake_call_dm_agent(**kwargs):
        seen["player_action"] = kwargs["player_action"]
        return {
            "result": json.dumps({
                "action_type": "exploration",
                "narrative": "后巷的门锁发出轻响。",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {},
                "needs_check": {"required": False},
                "combat_triggered": False,
                "combat_ended": False,
                "dice_display": [],
            }, ensure_ascii=False),
            "success": True,
        }

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)

    host = await _register(client, "mp_actor")
    supporter = await _register(client, "mp_supporter", display_name="艾拉")
    tavern_player = await _register(client, "mp_tavern_ready", display_name="凯伦")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_h(supporter["token"]), json={"room_code": create["room_code"]})
    await client.post("/game/rooms/join", headers=_h(tavern_player["token"]), json={"room_code": create["room_code"]})

    host_char = Character(
        id=str(_uuid.uuid4()), name="洛林",
        race="Human", char_class="Rogue", level=1,
        ability_scores={"str": 10, "dex": 16, "con": 12, "int": 12, "wis": 10, "cha": 10},
        hp_current=8, is_player=True, session_id=sid,
    )
    supporter_char = Character(
        id=str(_uuid.uuid4()), name="艾拉",
        race="Elf", char_class="Wizard", level=1,
        ability_scores={"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 10},
        hp_current=6, is_player=True, session_id=sid,
    )
    tavern_char = Character(
        id=str(_uuid.uuid4()), name="凯伦",
        race="Human", char_class="Bard", level=1,
        ability_scores={"str": 8, "dex": 12, "con": 12, "int": 12, "wis": 10, "cha": 16},
        hp_current=7, is_player=True, session_id=sid,
    )
    db_session.add_all([host_char, supporter_char, tavern_char])
    await db_session.commit()
    await client.post(f"/game/rooms/{sid}/claim-character", headers=_h(host["token"]), json={"character_id": host_char.id})
    await client.post(f"/game/rooms/{sid}/claim-character", headers=_h(supporter["token"]), json={"character_id": supporter_char.id})
    await client.post(f"/game/rooms/{sid}/claim-character", headers=_h(tavern_player["token"]), json={"character_id": tavern_char.id})
    await _ready_for_start(client, sid, host, supporter, tavern_player)
    started = await client.post(f"/game/rooms/{sid}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text
    await client.post(f"/game/rooms/{sid}/groups/join", headers=_h(host["token"]),
                      json={"group_id": "alley", "group_name": "后巷组", "location": "酒馆后巷"})
    await client.post(f"/game/rooms/{sid}/groups/join", headers=_h(supporter["token"]),
                      json={"group_id": "alley", "group_name": "后巷组", "location": "酒馆后巷"})
    await client.post(f"/game/rooms/{sid}/groups/join", headers=_h(tavern_player["token"]),
                      json={"group_id": "tavern", "group_name": "酒馆组", "location": "酒馆大厅"})
    await client.post(f"/game/rooms/{sid}/groups/actions", headers=_h(supporter["token"]),
                      json={"group_id": "alley", "action_text": "我检查仓库门锁。"})
    await client.post(f"/game/rooms/{sid}/groups/actions", headers=_h(tavern_player["token"]),
                      json={"group_id": "tavern", "action_text": "我继续套老板的话。"})
    await client.post(f"/game/rooms/{sid}/groups/readiness", headers=_h(host["token"]),
                      json={"group_id": "alley", "status": "ready"})
    await client.post(f"/game/rooms/{sid}/groups/readiness", headers=_h(supporter["token"]),
                      json={"group_id": "alley", "status": "ready"})
    await client.post(f"/game/rooms/{sid}/groups/readiness", headers=_h(tavern_player["token"]),
                      json={"group_id": "tavern", "status": "ready"})

    response = await client.post("/game/action", headers=_h(host["token"]), json={
        "session_id": sid,
        "action_text": "我撬开后门。",
    })

    assert response.status_code == 200, response.text
    assert "我撬开后门。" in seen["player_action"]
    assert "【多人分队上下文】" in seen["player_action"]
    assert "当前焦点分队：后巷组" in seen["player_action"]
    assert "艾拉：我检查仓库门锁。" in seen["player_action"]

    room = (await client.get(f"/game/rooms/{sid}", headers=_h(host["token"]))).json()
    assert room["pending_actions_by_group"]["alley"] == []
    assert room["group_readiness"]["alley"] == {}
    assert room["pending_actions_by_group"]["tavern"][0]["text"] == "我继续套老板的话。"
    assert room["group_readiness"]["tavern"][tavern_player["user_id"]] == "ready"
    assert room["active_group_id"] == "tavern"


async def test_multiplayer_table_decision_updates_focus_without_base_dm(
    client, db_session, sample_module, monkeypatch,
):
    """v2 桌面裁决如果只切镜头，应返回 table message 并更新房间焦点。"""
    import uuid as _uuid
    from models import Character
    from services.graphs.multiplayer_dm_state import MultiplayerDMDecision
    import services.graphs.multiplayer_dm_agent as mp_agent
    import services.ws_manager as ws_module

    broadcasts = []

    async def fake_multiplayer_dm_agent(*, db, session, actor_user_id, action_text):
        return MultiplayerDMDecision(
            should_call_base_dm=False,
            table_message="镜头转向酒馆组，请酒馆组玩家先行动。",
            table_reason="酒馆组已有待处理行动，玩家明确要求切镜头。",
            table_decision={
                "decision": "switch_focus",
                "reason_code": "switch_focus",
                "target_group_id": "tavern",
                "waiting_group_id": None,
                "actor_group_id": "alley",
                "focus_group_id": "tavern",
                "knowledge_scope": "group",
            },
            actor_group_id="alley",
            focus_group_id="tavern",
            room_updates={"active_group_id": "tavern"},
            visibility={"scope": "group", "group_id": "tavern", "visible_to_user_ids": []},
        )

    async def fake_broadcast(session_id, event, exclude_user_id=None):
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
        broadcasts.append(payload)
        return 1

    monkeypatch.setattr(mp_agent, "run_multiplayer_dm_agent", fake_multiplayer_dm_agent)
    monkeypatch.setattr(ws_module.ws_manager, "broadcast", fake_broadcast)

    host = await _register(client, "mp_table_actor")
    guest = await _register(client, "mp_table_guest")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={"room_code": create["room_code"]})

    host_char = Character(
        id=str(_uuid.uuid4()), name="洛林",
        race="Human", char_class="Rogue", level=1,
        ability_scores={"str": 10, "dex": 16, "con": 12, "int": 12, "wis": 10, "cha": 10},
        hp_current=8, is_player=True, session_id=sid,
    )
    guest_char = Character(
        id=str(_uuid.uuid4()), name="凯伦",
        race="Human", char_class="Bard", level=1,
        ability_scores={"str": 8, "dex": 12, "con": 12, "int": 12, "wis": 10, "cha": 16},
        hp_current=7, is_player=True, session_id=sid,
    )
    db_session.add_all([host_char, guest_char])
    await db_session.commit()
    await client.post(f"/game/rooms/{sid}/claim-character", headers=_h(host["token"]), json={"character_id": host_char.id})
    await client.post(f"/game/rooms/{sid}/claim-character", headers=_h(guest["token"]), json={"character_id": guest_char.id})
    await _ready_for_start(client, sid, host, guest)
    started = await client.post(f"/game/rooms/{sid}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text
    await client.post(f"/game/rooms/{sid}/groups/join", headers=_h(host["token"]),
                      json={"group_id": "alley", "group_name": "后巷组", "location": "酒馆后巷"})
    await client.post(f"/game/rooms/{sid}/groups/join", headers=_h(guest["token"]),
                      json={"group_id": "tavern", "group_name": "酒馆组", "location": "酒馆大厅"})
    focused_before = await client.post(
        f"/game/rooms/{sid}/groups/focus",
        headers=_h(host["token"]),
        json={"group_id": "alley"},
    )
    assert focused_before.status_code == 200, focused_before.text
    assert focused_before.json()["active_group_id"] == "alley"

    response = await client.post("/game/action", headers=_h(host["token"]), json={
        "session_id": sid,
        "action_text": "先切到酒馆看看他们。",
    })

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "multiplayer_table"
    assert body["narrative"] == "镜头转向酒馆组，请酒馆组玩家先行动。"
    assert body["table_reason"] == "酒馆组已有待处理行动，玩家明确要求切镜头。"
    assert body["table_decision"]["decision"] == "switch_focus"
    assert body["table_decision"]["target_group_id"] == "tavern"
    assert body["visibility"]["group_id"] == "tavern"

    room = (await client.get(f"/game/rooms/{sid}", headers=_h(host["token"]))).json()
    assert room["active_group_id"] == "tavern"
    assert any(
        event["type"] == "room_state_updated" and event["room"]["active_group_id"] == "tavern"
        for event in broadcasts
    )
    assert any(
        event["type"] == "dm_responded"
        and event["action_type"] == "multiplayer_table"
        and event["narrative"] == "镜头转向酒馆组，请酒馆组玩家先行动。"
        and event["table_decision"]["target_group_id"] == "tavern"
        for event in broadcasts
    )
    logs = (await client.get(f"/game/sessions/{sid}", headers=_h(host["token"]))).json()["logs"]
    assert any(log["role"] == "dm" and log["content"] == "镜头转向酒馆组，请酒馆组玩家先行动。" for log in logs)
    table_log = next(log for log in logs if log["role"] == "dm" and log["content"] == "镜头转向酒馆组，请酒馆组玩家先行动。")
    assert table_log["table_reason"] == "酒馆组已有待处理行动，玩家明确要求切镜头。"
    assert table_log["table_decision"]["reason_code"] == "switch_focus"


async def test_group_visible_dm_response_is_sent_only_to_visible_users(
    client, db_session, sample_module, monkeypatch,
):
    """基础 DM 叙事带 group visibility 时，只应点对点推给可见分队成员。"""
    import json
    import uuid as _uuid
    from models import Character
    from services.graphs.multiplayer_dm_state import MultiplayerDMDecision
    import services.graphs.multiplayer_dm_agent as mp_agent
    import services.langgraph_client as lc
    import services.ws_manager as ws_module

    sent_to_users = []
    broadcasts = []

    async def fake_multiplayer_dm_agent(*, db, session, actor_user_id, action_text):
        return MultiplayerDMDecision(
            should_call_base_dm=True,
            effective_action_text="我撬开后门。\n\n【多人分队上下文】\n当前焦点分队：后巷组",
            actor_group_id="alley",
            focus_group_id="alley",
            table_reason="后巷组行动已齐，交给基础 DM 处理当前镜头。",
            table_decision={
                "decision": "process_actor_group",
                "reason_code": "process_actor_group",
                "target_group_id": "alley",
                "waiting_group_id": None,
                "actor_group_id": "alley",
                "focus_group_id": "alley",
                "knowledge_scope": "group",
            },
            clear_pending_group_ids=[],
            room_updates={},
            visibility={"scope": "group", "group_id": "alley", "visible_to_user_ids": [host["user_id"], ally["user_id"]]},
        )

    async def fake_call_dm_agent(**kwargs):
        return {
            "result": json.dumps({
                "action_type": "exploration",
                "narrative": "后巷门锁在阴影里轻轻弹开。",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {},
                "needs_check": {"required": False},
                "combat_triggered": False,
                "combat_ended": False,
                "dice_display": [],
            }, ensure_ascii=False),
            "success": True,
        }

    async def fake_broadcast(session_id, event, exclude_user_id=None):
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
        broadcasts.append(payload)
        return 1

    async def fake_send_to_user(session_id, user_id, event):
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
        sent_to_users.append((user_id, payload))
        return True

    monkeypatch.setattr(mp_agent, "run_multiplayer_dm_agent", fake_multiplayer_dm_agent)
    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(ws_module.ws_manager, "broadcast", fake_broadcast)
    monkeypatch.setattr(ws_module.ws_manager, "send_to_user", fake_send_to_user)

    host = await _register(client, "mp_visible_actor")
    ally = await _register(client, "mp_visible_ally")
    outsider = await _register(client, "mp_visible_outsider")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_h(ally["token"]), json={"room_code": create["room_code"]})
    await client.post("/game/rooms/join", headers=_h(outsider["token"]), json={"room_code": create["room_code"]})

    chars = []
    for token_owner, name, char_class in [
        (host, "洛林", "Rogue"),
        (ally, "艾拉", "Wizard"),
        (outsider, "凯伦", "Bard"),
    ]:
        char = Character(
            id=str(_uuid.uuid4()), name=name,
            race="Human", char_class=char_class, level=1,
            ability_scores={"str": 10, "dex": 14, "con": 12, "int": 12, "wis": 10, "cha": 10},
            hp_current=8, is_player=True, session_id=sid,
        )
        chars.append((token_owner, char))
    db_session.add_all([char for _, char in chars])
    await db_session.commit()
    for token_owner, char in chars:
        await client.post(f"/game/rooms/{sid}/claim-character", headers=_h(token_owner["token"]), json={"character_id": char.id})
    await _ready_for_start(client, sid, host, ally, outsider)
    started = await client.post(f"/game/rooms/{sid}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text
    await client.post(f"/game/rooms/{sid}/groups/join", headers=_h(host["token"]),
                      json={"group_id": "alley", "group_name": "后巷组", "location": "酒馆后巷"})
    await client.post(f"/game/rooms/{sid}/groups/join", headers=_h(ally["token"]),
                      json={"group_id": "alley", "group_name": "后巷组", "location": "酒馆后巷"})
    await client.post(f"/game/rooms/{sid}/groups/join", headers=_h(outsider["token"]),
                      json={"group_id": "tavern", "group_name": "酒馆组", "location": "酒馆大厅"})

    response = await client.post("/game/action", headers=_h(host["token"]), json={
        "session_id": sid,
        "action_text": "我撬开后门。",
    })

    assert response.status_code == 200, response.text
    assert response.json()["visibility"]["group_id"] == "alley"
    assert response.json()["table_reason"] == "后巷组行动已齐，交给基础 DM 处理当前镜头。"
    assert response.json()["table_decision"]["reason_code"] == "process_actor_group"
    assert response.json()["table_decision"]["target_group_id"] == "alley"
    visible_user_ids = [user_id for user_id, payload in sent_to_users if payload["type"] == "dm_responded"]
    assert visible_user_ids == [host["user_id"], ally["user_id"]]
    assert outsider["user_id"] not in visible_user_ids
    assert not any(event["type"] == "dm_responded" for event in broadcasts)
    assert sent_to_users[0][1]["visibility"]["group_id"] == "alley"
    assert sent_to_users[0][1]["table_reason"] == "后巷组行动已齐，交给基础 DM 处理当前镜头。"
    assert sent_to_users[0][1]["table_decision"]["reason_code"] == "process_actor_group"
    host_logs = (await client.get(f"/game/sessions/{sid}", headers=_h(host["token"]))).json()["logs"]
    outsider_logs = (await client.get(f"/game/sessions/{sid}", headers=_h(outsider["token"]))).json()["logs"]
    assert any(
        log["content"] == "后巷门锁在阴影里轻轻弹开。"
        and log["visibility"]["group_id"] == "alley"
        and log["table_reason"] == "后巷组行动已齐，交给基础 DM 处理当前镜头。"
        and log["table_decision"]["reason_code"] == "process_actor_group"
        for log in host_logs
    )
    assert not any(log["content"] == "后巷门锁在阴影里轻轻弹开。" for log in outsider_logs)


async def test_simulated_multiplayer_split_party_turn_preserves_other_group_queue(
    client, db_session, sample_module, monkeypatch,
):
    """模拟真人多人局：两个分队都有意图时，只处理当前发言者分队并保留另一组队列。"""
    import json
    import uuid as _uuid
    from models import Character
    import services.langgraph_client as lc
    import services.ws_manager as ws_module

    sent_to_users = []
    broadcasts = []
    seen = {}

    async def fake_call_dm_agent(**kwargs):
        seen["player_action"] = kwargs["player_action"]
        return {
            "result": json.dumps({
                "action_type": "exploration",
                "narrative": "后巷组悄声撬开仓库后门，屋内传出潮湿木板的气味。",
                "player_choices": [],
                "companion_reactions": "",
                "state_delta": {},
                "needs_check": {"required": False},
                "combat_triggered": False,
                "combat_ended": False,
                "dice_display": [],
            }, ensure_ascii=False),
            "success": True,
        }

    async def fake_broadcast(session_id, event, exclude_user_id=None):
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
        broadcasts.append(payload)
        return 1

    async def fake_send_to_user(session_id, user_id, event):
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
        sent_to_users.append((user_id, payload))
        return True

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent)
    monkeypatch.setattr(ws_module.ws_manager, "broadcast", fake_broadcast)
    monkeypatch.setattr(ws_module.ws_manager, "send_to_user", fake_send_to_user)

    host = await _register(client, "mp_sim_host", display_name="洛林玩家")
    ally = await _register(client, "mp_sim_ally", display_name="艾拉玩家")
    tavern = await _register(client, "mp_sim_tavern", display_name="凯伦玩家")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "模拟多人局", "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_h(ally["token"]), json={"room_code": create["room_code"]})
    await client.post("/game/rooms/join", headers=_h(tavern["token"]), json={"room_code": create["room_code"]})

    chars = []
    for token_owner, name, char_class in [
        (host, "洛林", "Rogue"),
        (ally, "艾拉", "Wizard"),
        (tavern, "凯伦", "Bard"),
    ]:
        char = Character(
            id=str(_uuid.uuid4()), name=name,
            race="Human", char_class=char_class, level=1,
            ability_scores={"str": 10, "dex": 14, "con": 12, "int": 12, "wis": 10, "cha": 10},
            hp_current=8, is_player=True, session_id=sid,
        )
        chars.append((token_owner, char))
    db_session.add_all([char for _, char in chars])
    await db_session.commit()
    for token_owner, char in chars:
        await client.post(
            f"/game/rooms/{sid}/claim-character",
            headers=_h(token_owner["token"]),
            json={"character_id": char.id},
        )
    await _ready_for_start(client, sid, host, ally, tavern)
    started = await client.post(f"/game/rooms/{sid}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text
    await client.post(
        f"/game/rooms/{sid}/groups/join",
        headers=_h(host["token"]),
        json={"group_id": "alley", "group_name": "后巷组", "location": "酒馆后巷"},
    )
    await client.post(
        f"/game/rooms/{sid}/groups/join",
        headers=_h(ally["token"]),
        json={"group_id": "alley", "group_name": "后巷组", "location": "酒馆后巷"},
    )
    await client.post(
        f"/game/rooms/{sid}/groups/join",
        headers=_h(tavern["token"]),
        json={"group_id": "tavern", "group_name": "酒馆组", "location": "酒馆大厅"},
    )
    await client.post(
        f"/game/rooms/{sid}/groups/actions",
        headers=_h(ally["token"]),
        json={"group_id": "alley", "action_text": "我在门边准备法术警戒。"},
    )
    await client.post(
        f"/game/rooms/{sid}/groups/actions",
        headers=_h(tavern["token"]),
        json={"group_id": "tavern", "action_text": "我继续和老板套话。"},
    )
    for token_owner, group_id in [(host, "alley"), (ally, "alley"), (tavern, "tavern")]:
        await client.post(
            f"/game/rooms/{sid}/groups/readiness",
            headers=_h(token_owner["token"]),
            json={"group_id": group_id, "status": "ready"},
        )

    response = await client.post("/game/action", headers=_h(host["token"]), json={
        "session_id": sid,
        "action_text": "我轻轻撬开仓库后门。",
    })

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["visibility"]["scope"] == "group"
    assert body["visibility"]["group_id"] == "alley"
    assert body["table_decision"]["target_group_id"] == "alley"
    assert "【同分队队友意图】" in seen["player_action"]
    assert "艾拉玩家：我在门边准备法术警戒。" in seen["player_action"]
    assert "酒馆组 1 条" in seen["player_action"]

    room = (await client.get(f"/game/rooms/{sid}", headers=_h(host["token"]))).json()
    assert room["pending_actions_by_group"]["alley"] == []
    assert room["group_readiness"]["alley"] == {}
    assert room["pending_actions_by_group"]["tavern"][0]["text"] == "我继续和老板套话。"
    assert room["group_readiness"]["tavern"][tavern["user_id"]] == "ready"
    assert room["active_group_id"] == "tavern"

    visible_user_ids = [user_id for user_id, payload in sent_to_users if payload["type"] == "dm_responded"]
    assert visible_user_ids == [host["user_id"], ally["user_id"]]
    assert tavern["user_id"] not in visible_user_ids
    assert any(
        event["type"] == "room_state_updated"
        and event["room"]["pending_actions_by_group"].get("alley") == []
        and (event["room"]["pending_actions_by_group"].get("tavern") or [{}])[0].get("text") == "我继续和老板套话。"
        for event in broadcasts
    )

    host_logs = (await client.get(f"/game/sessions/{sid}", headers=_h(host["token"]))).json()["logs"]
    tavern_logs = (await client.get(f"/game/sessions/{sid}", headers=_h(tavern["token"]))).json()["logs"]
    assert any(log["content"] == body["narrative"] for log in host_logs)
    assert not any(log["content"] == body["narrative"] for log in tavern_logs)


async def test_session_logs_hide_group_private_entries_from_other_groups(
    client, db_session, sample_module,
):
    """刷新会话时，分队私密日志只应出现在可见玩家的 logs 中。"""
    import uuid as _uuid
    from models import Character, GameLog

    host = await _register(client, "mp_log_actor")
    ally = await _register(client, "mp_log_ally")
    outsider = await _register(client, "mp_log_outsider")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_h(ally["token"]), json={"room_code": create["room_code"]})
    await client.post("/game/rooms/join", headers=_h(outsider["token"]), json={"room_code": create["room_code"]})

    chars = []
    for token_owner, name in [(host, "洛林"), (ally, "艾拉"), (outsider, "凯伦")]:
        char = Character(
            id=str(_uuid.uuid4()), name=name,
            race="Human", char_class="Rogue", level=1,
            ability_scores={"str": 10, "dex": 14, "con": 12, "int": 12, "wis": 10, "cha": 10},
            hp_current=8, is_player=True, session_id=sid,
        )
        chars.append((token_owner, char))
    db_session.add_all([char for _, char in chars])
    await db_session.commit()
    for token_owner, char in chars:
        await client.post(f"/game/rooms/{sid}/claim-character", headers=_h(token_owner["token"]), json={"character_id": char.id})
    await _ready_for_start(client, sid, host, ally, outsider)
    started = await client.post(f"/game/rooms/{sid}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text

    db_session.add_all([
        GameLog(
            session_id=sid,
            role="dm",
            content="所有人都听见远处钟声。",
            log_type="narrative",
            visibility={"scope": "party", "visible_to_user_ids": []},
        ),
        GameLog(
            session_id=sid,
            role="dm",
            content="后巷门锁在阴影里轻轻弹开。",
            log_type="narrative",
            visibility={
                "scope": "group",
                "group_id": "alley",
                "visible_to_user_ids": [host["user_id"], ally["user_id"]],
            },
        ),
    ])
    await db_session.commit()

    host_logs = (await client.get(f"/game/sessions/{sid}", headers=_h(host["token"]))).json()["logs"]
    outsider_logs = (await client.get(f"/game/sessions/{sid}", headers=_h(outsider["token"]))).json()["logs"]

    assert any(log["content"] == "后巷门锁在阴影里轻轻弹开。" for log in host_logs)
    assert not any(log["content"] == "后巷门锁在阴影里轻轻弹开。" for log in outsider_logs)
    assert any(log["content"] == "所有人都听见远处钟声。" for log in outsider_logs)


async def test_room_host_cannot_restore_private_logs_unless_visible(
    client, db_session, sample_module,
):
    """房主也是玩家；不在可见名单里时不能恢复其他玩家私密日志。"""
    import uuid as _uuid
    from models import Character, GameLog

    host = await _register(client, "mp_host_private_boundary")
    ally = await _register(client, "mp_private_target")
    outsider = await _register(client, "mp_private_outsider")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_h(ally["token"]), json={"room_code": create["room_code"]})
    await client.post("/game/rooms/join", headers=_h(outsider["token"]), json={"room_code": create["room_code"]})

    chars = []
    for token_owner, name in [(host, "房主角色"), (ally, "艾拉"), (outsider, "凯伦")]:
        char = Character(
            id=str(_uuid.uuid4()), name=name,
            race="Human", char_class="Rogue", level=1,
            ability_scores={"str": 10, "dex": 14, "con": 12, "int": 12, "wis": 10, "cha": 10},
            hp_current=8, is_player=True, session_id=sid,
        )
        chars.append((token_owner, char))
    db_session.add_all([char for _, char in chars])
    await db_session.commit()
    for token_owner, char in chars:
        await client.post(f"/game/rooms/{sid}/claim-character", headers=_h(token_owner["token"]), json={"character_id": char.id})
    await _ready_for_start(client, sid, host, ally, outsider)
    started = await client.post(f"/game/rooms/{sid}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text

    db_session.add(GameLog(
        session_id=sid,
        role="dm",
        content="只有艾拉看见柜台下的暗号。",
        log_type="narrative",
        visibility={
            "scope": "private",
            "visible_to_user_ids": [ally["user_id"]],
        },
    ))
    await db_session.commit()

    host_logs = (await client.get(f"/game/sessions/{sid}", headers=_h(host["token"]))).json()["logs"]
    ally_logs = (await client.get(f"/game/sessions/{sid}", headers=_h(ally["token"]))).json()["logs"]
    outsider_logs = (await client.get(f"/game/sessions/{sid}", headers=_h(outsider["token"]))).json()["logs"]

    assert not any(log["content"] == "只有艾拉看见柜台下的暗号。" for log in host_logs)
    assert any(log["content"] == "只有艾拉看见柜台下的暗号。" for log in ally_logs)
    assert not any(log["content"] == "只有艾拉看见柜台下的暗号。" for log in outsider_logs)


# ─── 接管 AI 角色 / 重连续玩（用户反馈过的 bug） ─────────

async def test_checkpoint_generation_uses_only_visible_multiplayer_logs(
    client, db_session, sample_module, monkeypatch,
):
    import uuid as _uuid
    from models import Character, GameLog
    import services.langgraph_client as lc

    seen = {}

    async def fake_generate_campaign_state(**kwargs):
        seen["log_text"] = kwargs["log_text"]
        return {"quest_log": [], "world_flags": {"visible_only": True}}

    monkeypatch.setattr(lc.langgraph_client, "generate_campaign_state", fake_generate_campaign_state)

    host = await _register(client, "mp_checkpoint_host")
    ally = await _register(client, "mp_checkpoint_private_target")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_h(ally["token"]), json={"room_code": create["room_code"]})

    host_char = Character(
        id=str(_uuid.uuid4()), name="checkpoint-host",
        race="Human", char_class="Rogue", level=1,
        ability_scores={"str": 10, "dex": 14, "con": 12, "int": 12, "wis": 10, "cha": 10},
        hp_current=8, is_player=True, session_id=sid,
    )
    db_session.add(host_char)
    await db_session.commit()
    await client.post(f"/game/rooms/{sid}/claim-character", headers=_h(host["token"]), json={"character_id": host_char.id})

    db_session.add_all([
        GameLog(
            session_id=sid,
            role="dm",
            content="public bell",
            log_type="narrative",
            visibility={"scope": "party", "visible_to_user_ids": []},
        ),
        GameLog(
            session_id=sid,
            role="dm",
            content="ally private mark",
            log_type="narrative",
            visibility={"scope": "private", "visible_to_user_ids": [ally["user_id"]]},
        ),
    ])
    await db_session.commit()

    response = await client.post(f"/game/sessions/{sid}/checkpoint", headers=_h(host["token"]))

    assert response.status_code == 200, response.text
    assert "public bell" in seen["log_text"]
    assert "ally private mark" not in seen["log_text"]


async def test_skill_check_requires_room_membership_and_bound_character(
    client, db_session, sample_module,
):
    import uuid as _uuid
    from models import Character

    host = await _register(client, "mp_skill_host")
    guest = await _register(client, "mp_skill_guest")
    stranger = await _register(client, "mp_skill_stranger")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_h(guest["token"]), json={"room_code": create["room_code"]})

    host_char = Character(
        id=str(_uuid.uuid4()), name="skill-host",
        race="Human", char_class="Rogue", level=1,
        ability_scores={"str": 10, "dex": 14, "con": 12, "int": 12, "wis": 10, "cha": 10},
        hp_current=8, is_player=True, session_id=sid,
    )
    guest_char = Character(
        id=str(_uuid.uuid4()), name="skill-guest",
        race="Human", char_class="Wizard", level=1,
        ability_scores={"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 10},
        hp_current=6, is_player=True, session_id=sid,
    )
    db_session.add_all([host_char, guest_char])
    await db_session.commit()
    await client.post(f"/game/rooms/{sid}/claim-character", headers=_h(host["token"]), json={"character_id": host_char.id})
    await client.post(f"/game/rooms/{sid}/claim-character", headers=_h(guest["token"]), json={"character_id": guest_char.id})

    stranger_roll = await client.post("/game/skill-check", headers=_h(stranger["token"]), json={
        "session_id": sid,
        "character_id": host_char.id,
        "skill": "Athletics",
        "dc": 10,
    })
    assert stranger_roll.status_code == 403

    guest_roll_host_character = await client.post("/game/skill-check", headers=_h(guest["token"]), json={
        "session_id": sid,
        "character_id": host_char.id,
        "skill": "Athletics",
        "dc": 10,
    })
    assert guest_roll_host_character.status_code == 403

    guest_roll_own_character = await client.post("/game/skill-check", headers=_h(guest["token"]), json={
        "session_id": sid,
        "character_id": guest_char.id,
        "skill": "Athletics",
        "dc": 10,
        "d20_value": 12,
    })
    assert guest_roll_own_character.status_code == 200, guest_roll_own_character.text


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


async def test_ai_takeover_speaker_offline_succeeds(
    client, db_session, sample_module, monkeypatch,
):
    """
    场景：speaker 长时间无心跳（离线）→ 另一个在线玩家点"代他出招"→
    AI 据 speaker 的 personality 生成一句行动 → 走 DM 流程 → 推进 speaker。
    """
    from datetime import datetime, timedelta
    from models import Character, SessionMember
    import services.ws_manager as ws_module
    import uuid as _uuid

    broadcasts = []

    async def fake_broadcast(session_id, event, exclude_user_id=None):
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
        broadcasts.append(payload)
        return 1

    monkeypatch.setattr(ws_module.ws_manager, "broadcast", fake_broadcast)

    host    = await _register(client, "host_takeover_off")
    offline = await _register(client, "offline_speaker")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid  = create["session_id"]
    code = create["room_code"]

    # offline 加入并 claim 角色
    await client.post("/game/rooms/join", headers=_h(offline["token"]), json={"room_code": code})

    char = Character(
        id=str(_uuid.uuid4()), name="离线浪人",
        race="Human", char_class="Ranger", level=1,
        ability_scores={"str": 13, "dex": 15, "con": 14, "int": 10, "wis": 13, "cha": 8},
        hp_current=10, is_player=True, session_id=sid,
        personality="沉默寡言", speech_style="短句", catchphrase="天黑前必须到达。",
    )
    db_session.add(char)
    await db_session.commit()
    await client.post(f"/game/rooms/{sid}/claim-character",
                       headers=_h(offline["token"]),
                       json={"character_id": char.id})

    # host 也认领一个角色，方便启动游戏
    host_char = Character(
        id=str(_uuid.uuid4()), name="host 战士",
        race="Human", char_class="Fighter", level=1,
        ability_scores={"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        hp_current=12, is_player=True, session_id=sid,
    )
    db_session.add(host_char)
    await db_session.commit()
    await client.post(f"/game/rooms/{sid}/claim-character",
                       headers=_h(host["token"]),
                       json={"character_id": host_char.id})

    # 启动游戏
    await _ready_for_start(client, sid, host, offline)
    started = await client.post(f"/game/rooms/{sid}/start", headers=_h(host["token"]))
    assert started.status_code == 200, started.text

    # 把 speaker 强行设为 offline 用户
    from sqlalchemy.orm.attributes import flag_modified
    from models import Session
    sess = await db_session.get(Session, sid)
    gs = dict(sess.game_state or {})
    gs.setdefault("multiplayer", {})["current_speaker_user_id"] = offline["user_id"]
    sess.game_state = gs
    flag_modified(sess, "game_state")

    # 把 speaker 和请求者都改成心跳过期；HTTP 代演请求本身应刷新请求者在线状态。
    from sqlalchemy import select as _select
    sm_orm = (await db_session.execute(
        _select(SessionMember).where(
            SessionMember.session_id == sid,
            SessionMember.user_id == offline["user_id"],
        )
    )).scalar_one()
    sm_orm.last_seen_at = datetime.utcnow() - timedelta(seconds=120)
    host_sm = (await db_session.execute(
        _select(SessionMember).where(
            SessionMember.session_id == sid,
            SessionMember.user_id == host["user_id"],
        )
    )).scalar_one()
    host_sm.last_seen_at = datetime.utcnow() - timedelta(seconds=120)
    await db_session.commit()

    # host 触发 AI 代演
    r = await client.post(f"/game/sessions/{sid}/ai-takeover", headers=_h(host["token"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "narrative" in body

    # 验证：写了一条 [AI 代演] log
    from models import GameLog
    logs_q = await db_session.execute(
        _select(GameLog).where(GameLog.session_id == sid).order_by(GameLog.created_at.desc()).limit(5)
    )
    contents = [l.content for l in logs_q.scalars().all()]
    assert any("[AI 代演]" in c for c in contents)

    # 验证：last_turn.last_actor_user_id 是 offline（不是 host）
    await db_session.refresh(sess)
    lt = sess.game_state.get("last_turn") or {}
    assert lt.get("last_actor_user_id") == offline["user_id"]
    assert lt.get("ai_takeover") is True
    assert lt.get("takeover_by") == host["user_id"]
    assert sess.game_state["multiplayer"]["current_speaker_user_id"] == host["user_id"]
    await db_session.refresh(char)
    assert char.is_player is True
    assert char.user_id == offline["user_id"]
    sm_after_takeover = (await db_session.execute(
        _select(SessionMember).where(
            SessionMember.session_id == sid,
            SessionMember.user_id == offline["user_id"],
        )
    )).scalar_one()
    assert sm_after_takeover.character_id == char.id
    assert any(
        event["type"] == "dm_speak_turn" and event["user_id"] == host["user_id"]
        for event in broadcasts
    )
    room_updates = [event["room"] for event in broadcasts if event["type"] == "room_state_updated"]
    assert any(room["current_speaker_user_id"] == host["user_id"] for room in room_updates)
    latest_room = room_updates[-1]
    host_member = next(member for member in latest_room["members"] if member["user_id"] == host["user_id"])
    assert host_member["is_online"] is True


async def test_ai_takeover_rejected_when_speaker_online(
    client, db_session, sample_module,
):
    """speaker 还在线 → 触发 AI 代演应被 409 拒绝。"""
    from datetime import datetime
    from models import Character, SessionMember
    from sqlalchemy.orm.attributes import flag_modified
    from models import Session
    from sqlalchemy import select as _select
    import uuid as _uuid

    host    = await _register(client, "host_online_check")
    speaker = await _register(client, "online_speaker")

    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_h(speaker["token"]),
                       json={"room_code": create["room_code"]})

    # 准备 + claim 角色
    char = Character(
        id=str(_uuid.uuid4()), name="speaker 角色",
        race="Human", char_class="Fighter", level=1,
        ability_scores={"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        hp_current=12, is_player=True, session_id=sid,
    )
    db_session.add(char)
    await db_session.commit()
    await client.post(f"/game/rooms/{sid}/claim-character",
                       headers=_h(speaker["token"]),
                       json={"character_id": char.id})

    # 设 speaker
    sess = await db_session.get(Session, sid)
    gs = dict(sess.game_state or {})
    gs.setdefault("multiplayer", {})["current_speaker_user_id"] = speaker["user_id"]
    sess.game_state = gs
    flag_modified(sess, "game_state")
    # speaker 刚刚刷新过 last_seen
    sm = (await db_session.execute(
        _select(SessionMember).where(
            SessionMember.session_id == sid,
            SessionMember.user_id == speaker["user_id"],
        )
    )).scalar_one()
    sm.last_seen_at = datetime.utcnow()
    await db_session.commit()

    r = await client.post(f"/game/sessions/{sid}/ai-takeover", headers=_h(host["token"]))
    assert r.status_code == 409  # speaker 仍在线，拒绝


async def test_ai_takeover_rejected_for_self(
    client, db_session, sample_module,
):
    """触发方就是当前 speaker → 400（请直接出招）。"""
    from sqlalchemy.orm.attributes import flag_modified
    from models import Session

    host = await _register(client, "host_self_takeover")
    create = (await client.post("/game/rooms/create", headers=_h(host["token"]), json={
        "module_id": sample_module.id, "save_name": "T", "max_players": 4,
    })).json()

    sess = await db_session.get(Session, create["session_id"])
    gs = dict(sess.game_state or {})
    gs.setdefault("multiplayer", {})["current_speaker_user_id"] = host["user_id"]
    sess.game_state = gs
    flag_modified(sess, "game_state")
    await db_session.commit()

    r = await client.post(f"/game/sessions/{create['session_id']}/ai-takeover",
                           headers=_h(host["token"]))
    assert r.status_code == 400


async def test_ai_takeover_singleplayer_rejected(
    client, sample_session, sample_user,
):
    """单人模式 session → 400。"""
    login = await client.post("/auth/login", json={
        "username": sample_user.username, "password": "password",
    })
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    r = await client.post(f"/game/sessions/{sample_session.id}/ai-takeover", headers=headers)
    assert r.status_code == 400


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


async def test_fifty_online_users_are_partitioned_across_four_player_rooms(
    client, sample_module,
):
    """
    50 在线用户不是"一局 50 人"：每局仍最多 4 人。

    这里模拟 50 个用户分布在 13 个房间中（12 间满 4 人，最后一间 2 人），
    并验证成员列表、默认分队、DM 风格、满员拒绝都按房间隔离。
    """
    users = [
        await _register(client, f"capacity_user_{idx:02d}")
        for idx in range(50)
    ]

    rooms = []
    cursor = 0
    room_sizes = [4] * 12 + [2]
    style_by_room = ["classic", "dark_fantasy", "lighthearted", "epic_crpg", "hardcore"]

    for room_idx, size in enumerate(room_sizes):
        host = users[cursor]
        dm_style = style_by_room[room_idx % len(style_by_room)]
        created = (await client.post(
            "/game/rooms/create",
            headers=_h(host["token"]),
            json={
                "module_id": sample_module.id,
                "save_name": f"容量隔离房 {room_idx}",
                "max_players": 4,
                "dm_style": dm_style,
            },
        )).json()
        room_user_ids = [host["user_id"]]
        cursor += 1

        for _ in range(size - 1):
            guest = users[cursor]
            joined = await client.post(
                "/game/rooms/join",
                headers=_h(guest["token"]),
                json={"room_code": created["room_code"]},
            )
            assert joined.status_code == 200, joined.text
            room_user_ids.append(guest["user_id"])
            cursor += 1

        rooms.append({
            "session_id": created["session_id"],
            "room_code": created["room_code"],
            "host": host,
            "dm_style": dm_style,
            "user_ids": room_user_ids,
        })

    assert cursor == 50
    assert len({room["room_code"] for room in rooms}) == len(rooms)

    overflow = await _register(client, "capacity_overflow")
    full_room = rooms[0]
    full_join = await client.post(
        "/game/rooms/join",
        headers=_h(overflow["token"]),
        json={"room_code": full_room["room_code"]},
    )
    assert full_join.status_code == 409
    assert "房间已满" in full_join.text

    all_seen_user_ids = set()
    for room_idx, room in enumerate(rooms):
        info_resp = await client.get(
            f"/game/rooms/{room['session_id']}",
            headers=_h(room["host"]["token"]),
        )
        assert info_resp.status_code == 200, info_resp.text
        info = info_resp.json()

        member_ids = {member["user_id"] for member in info["members"]}
        expected_ids = set(room["user_ids"])
        assert member_ids == expected_ids
        assert len(member_ids) <= 4
        assert info["max_players"] == 4
        assert info["room_code"] == room["room_code"]
        assert info["host_user_id"] == room["host"]["user_id"]
        assert info["dm_style"]["key"] == room["dm_style"]

        groups = {group["id"]: group for group in info["party_groups"]}
        assert groups["main"]["member_user_ids"] == room["user_ids"]
        assert set(info["group_readiness"]["main"]).issubset(member_ids)

        all_seen_user_ids.update(member_ids)

        if room_idx > 0:
            assert member_ids.isdisjoint(set(rooms[room_idx - 1]["user_ids"]))

    assert all_seen_user_ids == {user["user_id"] for user in users}
