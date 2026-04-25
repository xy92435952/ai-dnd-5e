"""
单元测试：schemas/ws_events.py 所有事件类型。

验证：
  - 每种事件都能正常构造、model_dump 出合法 payload
  - type 字段被 Literal 固定，不能随便改
  - WS_EVENT_TYPES 集合与 Union 成员严格一一对应（防止"定义了新类但忘了注册"）
  - ws_manager.broadcast 接受 Pydantic 实例能正确序列化
"""
import json
import pytest
import pytest_asyncio

from schemas.ws_events import (
    WSEvent, WS_EVENT_TYPES,
    MemberJoined, MemberLeft, RoomDissolved, GameStarted,
    AiCompanionsFilled, MemberKicked, HostTransferred, CharacterClaimed,
    MemberOnline, MemberOffline, Typing,
    DMThinkingStart, DMResponded, DMSpeakTurn,
    CombatUpdate, TurnChanged, EntityMoved,
)


ALL_CLASSES = [
    MemberJoined, MemberLeft, RoomDissolved, GameStarted,
    AiCompanionsFilled, MemberKicked, HostTransferred, CharacterClaimed,
    MemberOnline, MemberOffline, Typing,
    DMThinkingStart, DMResponded, DMSpeakTurn,
    CombatUpdate, TurnChanged, EntityMoved,
]


class TestEventShape:
    def test_all_classes_have_type_field(self):
        """每个事件类都应定义 `type: Literal[...]`。"""
        for cls in ALL_CLASSES:
            assert "type" in cls.model_fields
            t = cls.model_fields["type"].default
            assert isinstance(t, str) and len(t) > 0

    def test_ws_event_types_matches_union(self):
        """WS_EVENT_TYPES 集合必须与类列表一一对应，避免漏注册。"""
        from_classes = {cls.model_fields["type"].default for cls in ALL_CLASSES}
        assert from_classes == set(WS_EVENT_TYPES)

    def test_model_dump_contains_type_key(self):
        """model_dump 产生的 payload 必须含 type 字段（前端 switch 依赖它）。"""
        e = DMThinkingStart(by_user_id="u1", action_text="试探")
        d = e.model_dump(mode="json")
        assert d["type"] == "dm_thinking_start"
        assert d["by_user_id"] == "u1"
        assert d["action_text"] == "试探"


class TestSampleEvents:
    """给关键事件各写一个构造样例，确保必填字段都没遗漏。"""

    def test_member_joined(self):
        e = MemberJoined(user_id="u1", members=[{"user_id": "u1"}])
        assert e.type == "member_joined"

    def test_member_left_optional_host(self):
        """host_transferred_to 是 Optional。"""
        e = MemberLeft(user_id="u1", members=[])
        assert e.host_transferred_to is None

    def test_dm_responded_defaults(self):
        """companion_reactions / dice_display 等有合理默认值。"""
        e = DMResponded(
            by_user_id="u1",
            action_type="exploration",
            narrative="你推开门",
        )
        assert e.companion_reactions == ""
        assert e.dice_display == []
        assert e.combat_triggered is False
        assert e.combat_ended is False

    def test_dm_speak_turn_auto_default_false(self):
        """auto 默认 False（玩家手动推进）；自动推进时调用方显式传 True。"""
        e = DMSpeakTurn(user_id="u1")
        assert e.auto is False

    def test_entity_moved_position(self):
        e = EntityMoved(entity_id="g1", position={"x": 3, "y": 5})
        d = e.model_dump(mode="json")
        assert d["position"] == {"x": 3, "y": 5}

    def test_turn_changed_requires_round_fields(self):
        with pytest.raises(Exception):
            TurnChanged()  # 缺 round_number / next_turn_index


class TestRoundTrip:
    """validate → model → dump → validate 回环，验证字段不丢失。"""

    def test_round_trip(self):
        originals = [
            MemberJoined(user_id="u1", members=[]),
            DMResponded(by_user_id="u1", action_type="combat", narrative="铛！"),
            EntityMoved(entity_id="g1", position={"x": 1, "y": 2}),
        ]
        for e in originals:
            d = e.model_dump(mode="json")
            # 用 JSON 字符串往返确保可序列化
            s = json.dumps(d, ensure_ascii=False)
            d2 = json.loads(s)
            re_constructed = type(e).model_validate(d2)
            assert re_constructed.model_dump() == e.model_dump()


# ─── ws_manager 集成 ──────────────────────────────────────

class FakeWebSocket:
    """伪造 WebSocket，记录所有 send_json 调用。"""
    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        # 模拟 ws 的 send_json 要求参数可序列化
        json.dumps(payload)
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_ws_manager_accepts_pydantic():
    """ws_manager.broadcast 传 Pydantic 实例应该自动 model_dump。"""
    from services.ws_manager import WSManager

    mgr = WSManager()
    ws = FakeWebSocket()
    session_id = "s1"

    # 手动注册（不走完整 connect 流程）
    mgr.rooms[session_id] = {ws}
    mgr.ws_meta[ws] = (session_id, "u1")
    mgr.user_ws[(session_id, "u1")] = ws

    event = DMThinkingStart(by_user_id="u1", action_text="行动")
    ok = await mgr.broadcast(session_id, event)
    assert ok == 1
    assert ws.sent[0]["type"] == "dm_thinking_start"
    assert ws.sent[0]["by_user_id"] == "u1"


@pytest.mark.asyncio
async def test_ws_manager_accepts_dict_backward_compat():
    """老的 dict 广播继续工作（向后兼容）。"""
    from services.ws_manager import WSManager

    mgr = WSManager()
    ws = FakeWebSocket()
    session_id = "s1"
    mgr.rooms[session_id] = {ws}
    mgr.ws_meta[ws] = (session_id, "u1")
    mgr.user_ws[(session_id, "u1")] = ws

    await mgr.broadcast(session_id, {"type": "legacy_event", "x": 1})
    assert ws.sent[0] == {"type": "legacy_event", "x": 1}
