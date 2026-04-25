"""
状态恢复 / 持久化测试 —— 验证刷新页面、WS 断线重连后玩家不丢上下文。

主要保护点：
  - player_action 后 session.game_state.last_turn 必须写库
  - GET /sessions/{id} 把 last_turn 原样回传
  - 多人模式：last_actor_user_id 字段精确反映"是谁触发的"
  - ws_manager: 同一 user 的旧连接在新连接到来时被踢
"""
import pytest

pytestmark = pytest.mark.integration


async def _auth_headers(client, sample_user):
    r = await client.post("/auth/login", json={
        "username": sample_user.username, "password": "password",
    })
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ─── last_turn 持久化 ───────────────────────────────────

async def test_action_writes_last_turn_to_game_state(
    client, db_session, sample_session, sample_user,
):
    """
    一次 player_action 后，session.game_state.last_turn 应包含：
      - last_actor_user_id（触发的 user）
      - action_type
      - ts（时间戳）
      - player_choices / needs_check（可空，但 key 必在）
    """
    headers = await _auth_headers(client, sample_user)

    r = await client.post("/game/action", headers=headers, json={
        "session_id": sample_session.id,
        "action_text": "我推开门",
    })
    assert r.status_code == 200, r.text

    # 重新拉 session，验证 last_turn 被写入
    await db_session.refresh(sample_session)
    gs = sample_session.game_state or {}
    lt = gs.get("last_turn")
    assert lt is not None, "last_turn 未写入"
    assert lt["last_actor_user_id"] == sample_user.id
    assert lt["action_type"]   # 不空
    assert "ts" in lt
    # mock 的 DM 返回 player_choices=[] / needs_check={"required": False}
    # → 写入时 needs_check 应被 normalize 为 None（仅当 required=True 才保留）
    assert lt["player_choices"] == []
    assert lt["needs_check"] is None


async def test_get_session_returns_last_turn(
    client, db_session, sample_session, sample_user,
):
    """GET /sessions/{id} 应该带回 game_state.last_turn —— 这是前端刷新时唯一的恢复来源。"""
    headers = await _auth_headers(client, sample_user)

    # 先触发一次 action 把 last_turn 写库
    await client.post("/game/action", headers=headers, json={
        "session_id": sample_session.id, "action_text": "测试",
    })

    r = await client.get(f"/game/sessions/{sample_session.id}", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["game_state"].get("last_turn") is not None
    assert data["game_state"]["last_turn"]["last_actor_user_id"] == sample_user.id


# ─── needs_check 持久化（玩家刷新后该看到检定按钮） ──

async def test_needs_check_required_persisted_to_last_turn(
    client, db_session, sample_session, sample_user, monkeypatch,
):
    """
    DM 返回 needs_check.required=True 时，last_turn.needs_check 必须保留这个 dict
    （前端刷新后据此重新显示"投掷 d20"按钮）。
    """
    import json as _json
    import services.langgraph_client as lc

    # 临时让 mock 返回带 needs_check 的响应
    async def fake_call_dm_agent_with_check(**kwargs):
        payload = {
            "action_type": "exploration",
            "narrative":   "你需要做个隐匿检定",
            "player_choices": [],
            "companion_reactions": "",
            "state_delta": {},
            "needs_check": {"required": True, "check_type": "隐匿", "dc": 13, "context": "悄悄过去"},
            "combat_triggered": False, "combat_ended": False,
            "dice_display": [], "scene_vibe": "", "clues": [],
        }
        return {
            "result":      _json.dumps(payload, ensure_ascii=False),
            "success":     True,
            "action_type": "exploration",
            "combat_triggered": False,
        }

    monkeypatch.setattr(lc.langgraph_client, "call_dm_agent", fake_call_dm_agent_with_check)

    headers = await _auth_headers(client, sample_user)
    r = await client.post("/game/action", headers=headers, json={
        "session_id": sample_session.id, "action_text": "悄悄过去",
    })
    assert r.status_code == 200, r.text

    await db_session.refresh(sample_session)
    lt = sample_session.game_state["last_turn"]
    assert lt["needs_check"] is not None
    assert lt["needs_check"]["required"] is True
    assert lt["needs_check"]["check_type"] == "隐匿"
    assert lt["needs_check"]["dc"] == 13


# ─── flag_modified 约定 ─────────────────────────────────

async def test_subsequent_action_overwrites_last_turn(
    client, db_session, sample_session, sample_user,
):
    """连续两次 action，last_turn 应该被第二次覆盖（时间戳变化、actor 不变）。"""
    headers = await _auth_headers(client, sample_user)
    await client.post("/game/action", headers=headers, json={
        "session_id": sample_session.id, "action_text": "动作 1",
    })
    await db_session.refresh(sample_session)
    ts1 = sample_session.game_state["last_turn"]["ts"]

    # 等一下确保时间戳能不同
    import asyncio
    await asyncio.sleep(0.01)

    await client.post("/game/action", headers=headers, json={
        "session_id": sample_session.id, "action_text": "动作 2",
    })
    await db_session.refresh(sample_session)
    ts2 = sample_session.game_state["last_turn"]["ts"]

    assert ts2 != ts1


# ─── ws_manager 单连接保证 ──────────────────────────────

async def test_ws_manager_replaces_old_connection_for_same_user():
    """同一 user 在同一房间发起新连接，旧连接应被踢掉。"""
    from services.ws_manager import WSManager

    class FakeWS:
        def __init__(self, name):
            self.name = name
            self.closed_with = None
        async def send_json(self, payload): pass
        async def close(self, code=None, reason=None):
            self.closed_with = (code, reason)

    mgr = WSManager()
    sid, uid = "s1", "u1"
    ws_old = FakeWS("old")
    ws_new = FakeWS("new")

    await mgr.connect(sid, uid, ws_old)
    assert mgr.user_ws[(sid, uid)] is ws_old

    # 第二次连接同一 user → 老连接被踢
    await mgr.connect(sid, uid, ws_new)
    assert mgr.user_ws[(sid, uid)] is ws_new
    assert ws_old.closed_with is not None
    assert ws_old.closed_with[0] == 4000  # "Replaced by new connection"


async def test_ws_manager_disconnect_cleans_up():
    from services.ws_manager import WSManager

    class FakeWS:
        async def send_json(self, payload): pass
        async def close(self, code=None, reason=None): pass

    mgr = WSManager()
    sid, uid = "s2", "u2"
    ws = FakeWS()

    await mgr.connect(sid, uid, ws)
    assert sid in mgr.rooms
    assert (sid, uid) in mgr.user_ws

    meta = await mgr.disconnect(ws)
    assert meta == (sid, uid)
    # 房间该清空
    assert sid not in mgr.rooms or len(mgr.rooms.get(sid, set())) == 0
    assert (sid, uid) not in mgr.user_ws


async def test_ws_manager_broadcast_skips_excluded_user():
    """exclude_user_id 的连接不应收到广播。"""
    from services.ws_manager import WSManager
    from schemas.ws_events import MemberOnline

    class RecordingWS:
        def __init__(self): self.sent = []
        async def send_json(self, payload): self.sent.append(payload)
        async def close(self, code=None, reason=None): pass

    mgr = WSManager()
    ws_a = RecordingWS()
    ws_b = RecordingWS()
    await mgr.connect("s3", "ua", ws_a)
    await mgr.connect("s3", "ub", ws_b)

    # 广播事件，排除 ua
    await mgr.broadcast("s3", MemberOnline(user_id="ub"), exclude_user_id="ua")

    assert ws_a.sent == []
    assert len(ws_b.sent) == 1
    assert ws_b.sent[0]["type"] == "member_online"
