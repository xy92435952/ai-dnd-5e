"""
集成测试：app 启动与基础路由。

目的：通过 TestClient 调用真实 HTTP handler 链，确认 app 启动、CORS 配置、
健康检查、/docs、/spells 等最基础的端点可用。
这层测试 token 消耗最小——发现 500 基本就是中间件或 app 配置出错。
"""
import pytest

pytestmark = pytest.mark.integration


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": "0.1.0"}


async def test_openapi_schema_served(client):
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert "paths" in schema
    # 几个关键路径必须存在
    assert "/health" in schema["paths"]
    assert "/game/sessions" in schema["paths"]
    assert "/game/combat/{session_id}" in schema["paths"]


async def test_spells_list_public(client):
    """GET /game/spells 是公开接口，应返回法术数组。"""
    r = await client.get("/game/spells")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # 每条至少有 name / level
    first = data[0]
    assert "name" in first and "level" in first


async def test_spells_by_class(client):
    """GET /game/spells/class/Wizard — 按职业过滤。"""
    r = await client.get("/game/spells/class/Wizard")
    assert r.status_code == 200
    spells = r.json()
    assert isinstance(spells, list)


async def test_nonexistent_session_returns_404(client):
    """获取不存在的 session 应为 404。"""
    r = await client.get("/game/sessions/nonexistent-id")
    assert r.status_code == 404


async def test_character_options_endpoint(client):
    """GET /characters/options — 前端创角向导依赖的数据接口。"""
    r = await client.get("/characters/options")
    assert r.status_code == 200
    opts = r.json()
    # 这些 key 前端直接解构消费
    for key in ("races", "classes"):
        assert key in opts, f"/characters/options 缺少 {key}"
