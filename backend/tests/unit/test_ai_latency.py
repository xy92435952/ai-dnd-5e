import logging

from services.ai_latency import AILatencyTrace
from services import game_exploration_service
from services import game_combat_action_service


def test_ai_latency_trace_records_step_durations(caplog):
    clock = {"value": 10.0}
    trace = AILatencyTrace(
        route="/game/action",
        session_id="s1",
        user_id="u1",
        metadata={"mode": "exploration"},
        now=lambda: clock["value"],
    )

    with trace.step("context"):
        clock["value"] += 0.25
    with caplog.at_level(logging.INFO):
        trace.log_success(extra={"model": "dm-model"})

    assert trace.timings_ms["context"] == 250
    assert "ai_latency route=/game/action status=success" in caplog.text
    assert "context_ms=250" in caplog.text
    assert "total_ms=250" in caplog.text
    assert "model=dm-model" in caplog.text


def test_ai_latency_logger_is_info_visible_by_default():
    assert logging.getLogger("ai_latency").getEffectiveLevel() <= logging.INFO


def test_ai_latency_mirrors_to_uvicorn_logger_when_available(monkeypatch):
    calls = []
    uvicorn_logger = logging.getLogger("uvicorn")
    previous_handlers = list(uvicorn_logger.handlers)
    previous_propagate = uvicorn_logger.propagate

    class FakeHandler(logging.Handler):
        def emit(self, record):
            calls.append(record.getMessage())

    handler = FakeHandler()
    uvicorn_logger.handlers = [handler]
    uvicorn_logger.propagate = False
    monkeypatch.setattr(logging.getLogger("uvicorn.error"), "info", lambda msg: calls.append(msg))
    try:
        AILatencyTrace(route="/probe", now=lambda: 1.0).log_success()
    finally:
        uvicorn_logger.handlers = previous_handlers
        uvicorn_logger.propagate = previous_propagate

    assert any("ai_latency route=/probe status=success" in call for call in calls)


def test_exploration_action_logs_segmented_ai_latency(monkeypatch, caplog):
    clock = {"value": 1.0}
    built_inputs = {
        "player_action": "我检查祭坛",
        "game_state": "{}",
        "module_context": "{}",
        "campaign_memory": "",
        "retrieved_context": "",
    }

    class FakeBuilder:
        def __init__(self, **kwargs):
            pass

        async def build(self, **kwargs):
            clock["value"] += 0.10
            return built_inputs

    class FakeLangGraphClient:
        async def call_dm_agent(self, **kwargs):
            clock["value"] += 0.20
            return {
                "success": True,
                "result": '{"action_type":"investigation","narrative":"你看到符文。","state_delta":{},"player_choices":[],"needs_check":{"required":false},"dice_results":[]}',
            }

    class FakeApplicator:
        def __init__(self, db):
            pass

        async def apply(self, **kwargs):
            clock["value"] += 0.30

            class Applied:
                action_type = "investigation"
                narrative = "你看到符文。"
                companion_reactions = ""
                dice_display = []
                player_choices = []
                needs_check = {"required": False}
                combat_triggered = False
                combat_ended = False
                combat_end_result = None
                initial_enemies = []
                errors = []

            return Applied()

    class FakeDb:
        async def commit(self):
            clock["value"] += 0.05

    class FakeSession:
        id = "s1"
        is_multiplayer = False
        combat_active = False
        game_state = {}

    monkeypatch.setattr(game_exploration_service, "ContextBuilder", FakeBuilder)
    monkeypatch.setattr(game_exploration_service, "StateApplicator", FakeApplicator)
    monkeypatch.setattr(game_exploration_service, "langgraph_client", FakeLangGraphClient())
    monkeypatch.setattr(game_exploration_service, "flag_modified", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        game_exploration_service,
        "AILatencyTrace",
        lambda **kwargs: AILatencyTrace(**kwargs, now=lambda: clock["value"]),
    )

    with caplog.at_level(logging.INFO, logger="ai_latency"):
        import asyncio
        asyncio.run(game_exploration_service.execute_exploration_action(
            db=FakeDb(),
            session=FakeSession(),
            module=None,
            characters=[],
            actor=None,
            actor_user_id="u1",
            action_text="我检查祭坛",
        ))

    assert "ai_latency route=/game/action status=success" in caplog.text
    assert "context_ms=100" in caplog.text
    assert "dm_agent_ms=200" in caplog.text
    assert "apply_state_ms=300" in caplog.text
    assert "commit_ms=50" in caplog.text
    assert "module_context_chars=2" in caplog.text


def test_combat_action_logs_segmented_ai_latency(monkeypatch, caplog):
    clock = {"value": 5.0}

    async def fake_parse_combat_action(**kwargs):
        clock["value"] += 0.11
        return {
            "actions": [{"type": "dodge"}],
            "narrative_hint": "守势",
            "_fallback": False,
        }

    async def fake_narrate_action(**kwargs):
        clock["value"] += 0.22
        return "你压低重心，稳稳摆出防御架势。"

    class FakeDb:
        def add(self, _obj):
            pass

        async def commit(self):
            clock["value"] += 0.33

    class FakeSession:
        id = "s-combat"
        user_id = "user-1"
        game_state = {"enemies": [{"id": "enemy-1", "name": "骷髅", "hp_current": 7, "hp_max": 7}]}
        combat_active = True

    class FakeCombatState:
        entity_positions = {"char-1": {"x": 0, "y": 0}, "enemy-1": {"x": 1, "y": 0}}
        turn_states = {}
        current_turn_index = 0
        round_number = 2

    class FakePlayer:
        id = "char-1"
        name = "伊莉丝"
        char_class = "Fighter"
        hp_current = 12
        is_player = True
        derived = {"hp_max": 12, "movement": 6}

    import services.action_parser as action_parser
    import services.combat_narrator as combat_narrator
    import api.combat as combat_api

    monkeypatch.setattr(action_parser, "parse_combat_action", fake_parse_combat_action)
    monkeypatch.setattr(combat_narrator, "narrate_action", fake_narrate_action)
    monkeypatch.setattr(
        combat_api,
        "_save_ts",
        lambda combat, entity_id, turn_state: setattr(
            combat,
            "turn_states",
            {**(combat.turn_states or {}), str(entity_id): turn_state},
        ),
    )
    monkeypatch.setattr(
        game_combat_action_service,
        "AILatencyTrace",
        lambda **kwargs: AILatencyTrace(**kwargs, now=lambda: clock["value"]),
    )

    with caplog.at_level(logging.INFO, logger="ai_latency"):
        import asyncio
        asyncio.run(game_combat_action_service.execute_natural_language_combat_action(
            db=FakeDb(),
            session=FakeSession(),
            combat_state=FakeCombatState(),
            player=FakePlayer(),
            characters=[FakePlayer()],
            action_text="我采取闪避动作",
        ))

    assert "ai_latency route=/game/action status=success" in caplog.text
    assert "mode=combat" in caplog.text
    assert "parse_ms=110" in caplog.text
    assert "execute_ms=0" in caplog.text
    assert "narrate_ms=220" in caplog.text
    assert "commit_ms=330" in caplog.text
    assert "parsed_actions=1" in caplog.text
    assert "action_results=1" in caplog.text
