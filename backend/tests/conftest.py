"""
测试总 conftest — 提供全套 fixture 供 smoke / unit / integration 共用。

设计目标：
  - 不依赖真实 LLM（所有 langgraph_client 方法被 mock）
  - 不依赖真实 ChromaDB（chromadb_path 指向临时目录，RAG stub 直接返回空）
  - 不依赖外部 Postgres（内存 SQLite）
  - 每个 test 拿到干净的 DB（表结构 create_all → test 结束清空）

为了让所有测试共用同一个数据库实例（方便跨 fixture 传递 ORM 对象），
我们在 session 级别创建一次 engine，在 function 级别 truncate 表。
"""
from __future__ import annotations

import os
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock

# ── 测试环境变量：必须在 import backend 模块前设置 ────────────────
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true")
os.environ.setdefault("CHROMADB_PATH", str(Path(__file__).parent / "_tmp_chroma"))
os.environ.setdefault("LANGGRAPH_DB_PATH", str(Path(__file__).parent / "_tmp_langgraph.db"))
os.environ.setdefault("JWT_SECRET", "test-secret-dont-use-in-prod")
os.environ.setdefault("ENV", "development")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


# ── 全局：mock LangGraph 客户端 ───────────────────────────────────
# 在 import chain 加载前就把这几个 async 方法替换掉，避免真实 LLM 调用。
# 注意：这些 patch 覆盖整个测试 session，通过 autouse fixture 应用。

@pytest.fixture(autouse=True, scope="session")
def _mock_llm_layer():
    """mock LangGraph / LLM，确保测试全程不触发网络请求。"""
    patches = []

    # LangGraph DM 代理：call_dm_agent 真实返回的是
    # {"result": <JSON 字符串>, "success": True, ...}（见 graphs/dm_agent.py）
    # 由 StateApplicator.apply 在 api/game.py 中解析 result 字段
    import json as _json
    async def fake_call_dm_agent(**kwargs):
        payload = {
            "action_type": "exploration",
            "narrative":   "（测试叙事）你环顾四周，什么也没发生。",
            "player_choices": [],
            # companion_reactions 的契约是 str（见 ApplyResult）
            "companion_reactions": "",
            "state_delta": {},
            # needs_check 的契约是带 required 字段的 dict
            "needs_check": {"required": False},
            "combat_triggered": False,
            "combat_ended":     False,
            "dice_display": [],
            "scene_vibe": "",
            "clues": [],
        }
        return {
            "result":  _json.dumps(payload, ensure_ascii=False),
            "success": True,
            "action_type":     "exploration",
            "combat_triggered": False,
        }

    async def fake_parse_module(text):
        return (
            {
                "setting": "测试设定",
                "tone":    "测试基调",
                "plot_summary": "测试剧情",
                "scenes":  [{"title": "测试场景 1", "description": "空旷的房间。"}],
                "npcs":    [],
                "monsters": [],
                "magic_items": [],
            },
            [],  # rag chunks
        )

    async def fake_generate_party(**kwargs):
        return []

    async def fake_generate_campaign_state(**kwargs):
        return {
            "completed_scenes": [],
            "key_decisions":    [],
            "npc_registry":     {},
            "quest_log":        [],
            "world_flags":      {},
        }

    import services.langgraph_client as lc
    patches.append(patch.object(lc.langgraph_client, "call_dm_agent",            fake_call_dm_agent))
    patches.append(patch.object(lc.langgraph_client, "parse_module",             fake_parse_module))
    patches.append(patch.object(lc.langgraph_client, "generate_party",           fake_generate_party))
    patches.append(patch.object(lc.langgraph_client, "generate_campaign_state",  fake_generate_campaign_state))

    # 跳过 DM Agent 的 SqliteSaver 初始化（测试场景下不需要对话记忆持久化）
    async def fake_initialize_memory():
        return None
    import services.graphs.dm_agent as dm_agent
    patches.append(patch.object(dm_agent, "initialize_memory", fake_initialize_memory))

    # 拦截 api.game._generate_opening：它直接调 services.llm.get_llm，不走
    # langgraph_client，conftest 上面的 mock 拦不住。给它一个稳定 stub。
    async def fake_generate_opening(parsed, raw_scene):
        return (raw_scene or "（测试开场）你站在矿洞口，回头还能看到村庄的灯火。").strip()
    import api.game as game_module
    patches.append(patch.object(game_module, "_generate_opening", fake_generate_opening))

    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


# ── DB fixtures ──────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def engine():
    """每个测试函数一个独立的内存 SQLite engine。"""
    from database import Base

    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        # 触发所有模型类的注册（通过 models 包的 __init__）
        import models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    """单次 test 内用的 AsyncSession。"""
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s


# ── FastAPI app / client fixtures ────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def app(engine):
    """
    返回注入了测试 engine 的 FastAPI app。
    通过覆盖 get_db 依赖让所有端点共享测试 engine。
    """
    import main as main_mod
    from database import get_db
    from sqlalchemy.ext.asyncio import async_sessionmaker

    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db_override():
        async with Session() as s:
            yield s

    main_mod.app.dependency_overrides[get_db] = _get_db_override
    yield main_mod.app
    main_mod.app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def client(app):
    """绑定到测试 app 的 httpx AsyncClient。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Seed data fixtures ───────────────────────────────────────────

@pytest_asyncio.fixture
async def sample_user(db_session):
    """插入一个测试用户并返回 ORM 对象。"""
    from models import User
    import uuid as _uuid, bcrypt
    u = User(
        id=str(_uuid.uuid4()),
        username="testuser",
        password_hash=bcrypt.hashpw(b"password", bcrypt.gensalt()).decode(),
        display_name="测试玩家",
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def sample_module(db_session):
    """插入一个已解析的测试模组。"""
    from models import Module
    import uuid as _uuid
    m = Module(
        id=str(_uuid.uuid4()),
        name="测试模组",
        file_path="",
        file_type="md",
        parsed_content={
            "setting": "测试设定",
            "tone":    "标准冒险",
            "plot_summary": "用于测试的占位剧情",
            "scenes":  [{"title": "第一章", "description": "测试场景"}],
            "npcs":    [],
            "monsters": [],
            "magic_items": [],
        },
        parse_status="done",
        parse_error=None,
        level_min=1, level_max=3, recommended_party_size=4,
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)
    return m


@pytest_asyncio.fixture
async def sample_character(db_session, sample_user):
    """插入一个 1 级战士玩家角色。"""
    from models import Character
    import uuid as _uuid

    ability_scores = {"str": 16, "dex": 14, "con": 15, "int": 10, "wis": 12, "cha": 8}
    derived = {
        "hp_max": 12, "ac": 16, "initiative": 2,
        "proficiency_bonus": 2, "attack_bonus": 5,
        "ability_modifiers": {"str": 3, "dex": 2, "con": 2, "int": 0, "wis": 1, "cha": -1},
        "spell_slots_max": {},
        "saving_throws": {"str": 5, "con": 4},
    }
    c = Character(
        id=str(_uuid.uuid4()),
        user_id=sample_user.id,
        name="测试战士",
        race="Human",
        char_class="Fighter",
        level=1,
        background="Soldier",
        ability_scores=ability_scores,
        derived=derived,
        hp_current=12,
        proficient_skills=["运动", "感知"],
        proficient_saves=["str", "con"],
        is_player=True,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def sample_session(db_session, sample_module, sample_character, sample_user):
    """创建一个绑定了 character 的游戏 Session（开场状态）。"""
    from models import Session as GameSession
    import uuid as _uuid

    s = GameSession(
        id=str(_uuid.uuid4()),
        user_id=sample_user.id,
        module_id=sample_module.id,
        player_character_id=sample_character.id,
        current_scene="测试场景",
        session_history="",
        game_state={"companion_ids": [], "scene_index": 0, "flags": {}},
        save_name="pytest 存档",
        combat_active=False,
    )
    sample_character.session_id = s.id
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s
