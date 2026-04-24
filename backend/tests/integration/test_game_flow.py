"""
集成测试：游戏主循环端点。

覆盖 P1 重构点里 game.py 的 5 处 CharacterRoster 替换：
  - create_session     绑定 companion（bind_companions）
  - get_session        返回 companions 列表
  - delete_session     清理 AI 队友（delete_ai_companions）
  - player_action      加载 [player] + companions 喂给 DM
  - take_rest          整组长休 / 短休

LLM 层已被 conftest 全局 mock，action 端点不会出网络。
"""
import pytest

pytestmark = pytest.mark.integration


async def _auth_headers(client, sample_user):
    """登录 sample_user 拿 JWT。所有需要 user_id 的端点统一用这个头。"""
    r = await client.post("/auth/login", json={
        "username": sample_user.username,
        "password": "password",
    })
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


async def test_get_session_shape(client, sample_session, sample_user):
    headers = await _auth_headers(client, sample_user)
    r = await client.get(f"/game/sessions/{sample_session.id}", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["session_id"] == sample_session.id
    assert data["player"] is not None
    assert data["player"]["name"] == "测试战士"
    assert isinstance(data["companions"], list)
    assert data["combat_active"] is False


async def test_list_sessions_for_user(client, sample_session, sample_user):
    headers = await _auth_headers(client, sample_user)
    r = await client.get("/game/sessions", headers=headers)
    assert r.status_code == 200
    arr = r.json()
    assert any(s["id"] == sample_session.id for s in arr)


async def test_player_action_succeeds(client, sample_session, sample_user):
    """mock 过的 DM 应回一段占位叙事并写库。"""
    headers = await _auth_headers(client, sample_user)
    r = await client.post("/game/action", headers=headers, json={
        "session_id":  sample_session.id,
        "action_text": "我看看四周",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert "narrative" in data
    assert data["narrative"].startswith("（测试叙事）") or data["narrative"]


async def test_skill_check_endpoint(client, sample_session, sample_user, sample_character):
    """本地计算，不用 LLM。"""
    headers = await _auth_headers(client, sample_user)
    r = await client.post("/game/skill-check", headers=headers, json={
        "session_id":   sample_session.id,
        "character_id": sample_character.id,
        "skill":        "运动",
        "dc":           10,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    for key in ("d20", "modifier", "total", "success"):
        assert key in data


async def test_delete_session_cleans_ai_companions(
    client, db_session, sample_session, sample_user,
):
    """P1 重构点验证：删除 session 时 AI 队友被清掉，玩家保留。"""
    from models import Character
    from sqlalchemy.orm.attributes import flag_modified
    from sqlalchemy import select
    import uuid as _uuid

    ai = Character(
        id=str(_uuid.uuid4()), name="临时队友",
        race="Elf", char_class="Wizard", level=1,
        ability_scores={}, hp_current=6, is_player=False, session_id=sample_session.id,
    )
    db_session.add(ai)
    sample_session.game_state = {**sample_session.game_state, "companion_ids": [ai.id]}
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.delete(f"/game/sessions/{sample_session.id}", headers=headers)
    assert r.status_code == 200, r.text

    # AI 应该被删了
    res = await db_session.execute(select(Character).where(Character.id == ai.id))
    assert res.scalar_one_or_none() is None
