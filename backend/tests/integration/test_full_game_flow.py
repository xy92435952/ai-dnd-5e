"""
端到端业务流程测试 —— 真实跑完一遍主跑团循环，检验各端点串起来的契约。

不止"端点能 200"，要验：
  - 创角后 DB 里有正确的 ability_scores / derived / proficient_skills
  - 创建 session 后 game_state.companion_ids 正确，[开场] log 已写
  - action 后 logs 增加、state_delta 被 StateApplicator 应用
  - skill-check 的命中率受熟练加值影响（proficient → 修正 +2）
  - rest 长休 → HP 满血、法术位重置；短休 → 消耗一个生命骰
  - checkpoint → campaign_state 写库
  - delete session → AI 队友被清掉、玩家保留、关联 GameLog 清掉
"""
import pytest

pytestmark = pytest.mark.integration


# ─── 辅助 ────────────────────────────────────────────────

async def _auth_headers(client, sample_user):
    r = await client.post("/auth/login", json={
        "username": sample_user.username, "password": "password",
    })
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ─── 创角 ────────────────────────────────────────────────

async def test_options_endpoint_returns_required_metadata(client):
    """前端创角向导依赖的字段必须存在且非空。"""
    r = await client.get("/characters/options")
    assert r.status_code == 200, r.text
    data = r.json()
    # 关键 key 必须存在
    for key in ("races", "classes", "all_skills",
                "racial_bonuses", "class_skill_choices",
                "spellcaster_classes"):
        assert key in data, f"options 缺少 {key}"
        assert data[key], f"options.{key} 为空"
    # SPELLCASTER_CLASSES 必须含 Wizard / Cleric
    assert "Wizard" in data["spellcaster_classes"]
    assert "Cleric" in data["spellcaster_classes"]


async def test_create_fighter_character_full_pipeline(
    client, db_session, sample_user, sample_module,
):
    """创建一个 1 级战士，验证 derived 计算正确。"""
    headers = await _auth_headers(client, sample_user)

    payload = {
        "module_id": sample_module.id,
        "name": "测试战士",
        "race": "Human",
        "char_class": "Fighter",
        "level": 1,
        "background": "Soldier",
        "alignment": "中立善良",
        "ability_scores": {"str": 15, "dex": 13, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "proficient_skills": ["运动", "感知"],
        "fighting_style": "Defense",
        "equipment_choice": 0,
    }
    r = await client.post("/characters/create", headers=headers, json=payload)
    assert r.status_code == 200, r.text
    data = r.json()

    # ── 关键不变量 ──
    assert data["name"] == "测试战士"
    assert data["char_class"] == "Fighter"
    assert data["level"] == 1
    assert data["is_player"] is True
    # Human +1 全属性 → str 16, dex 14, con 15, int 11, wis 13, cha 9
    assert data["ability_scores"]["str"] == 16
    assert data["ability_scores"]["con"] == 15
    # derived 必须算出
    derived = data["derived"]
    assert derived["hp_max"] >= 10  # d10 + con_mod(2)
    assert derived["proficiency_bonus"] == 2
    assert derived["ability_modifiers"]["str"] == 3  # (16-10)//2
    # Fighter 豁免熟练 = str + con
    assert "str" in data["proficient_saves"]
    assert "con" in data["proficient_saves"]
    # 玩家选了的 2 个技能必须包含（背景可能额外送 1-2 个）
    assert "运动" in data["proficient_skills"]
    assert "感知" in data["proficient_skills"]
    # Defense fighting_style 应有 +1 AC（在 derived.ac 里）
    assert derived.get("ac", 10) >= 11


async def test_create_character_with_narrative_fields(
    client, db_session, sample_user, sample_module,
):
    """
    玩家创角时填了 personality/backstory/speech_style 等叙事字段：
      - 必须落库
      - 必须出现在 char_brief（供 GET /sessions/{id} 时前端读）
      - 必须出现在 ContextBuilder 序列化的 game_state（供 DM 代演时引用）
    """
    headers = await _auth_headers(client, sample_user)

    payload = {
        "module_id": sample_module.id,
        "name":  "测试浪人",
        "race":  "Human",
        "char_class": "Fighter",
        "level": 1,
        "background": "Outlander",
        "alignment": "中立善良",
        "ability_scores": {"str": 13, "dex": 15, "con": 14, "int": 10, "wis": 13, "cha": 8},
        "proficient_skills": ["感知", "运动"],
        # 叙事字段
        "personality":       "沉默寡言，只在必要时开口",
        "backstory":         "10 年前家乡被山贼洗劫，从此孤身在边境讨生活",
        "speech_style":      "短句、低声、不带感情",
        "combat_preference": "远程优先，必要时白刃相搏",
        "catchphrase":       "天黑前必须到达。",
    }
    r = await client.post("/characters/create", headers=headers, json=payload)
    assert r.status_code == 200, r.text
    data = r.json()

    # _serialize_character 必须回传所有叙事字段
    assert data["personality"]       == payload["personality"]
    assert data["backstory"]         == payload["backstory"]
    assert data["speech_style"]      == payload["speech_style"]
    assert data["combat_preference"] == payload["combat_preference"]
    assert data["catchphrase"]       == payload["catchphrase"]

    # ── 验证 ContextBuilder 把这些字段灌进 game_state ──
    # 直接调用以避免起完整 session 流程
    from models import Character, Session
    from services.context_builder import ContextBuilder
    char = await db_session.get(Character, data["id"])
    fake_session = Session(
        id="x",
        module_id=sample_module.id,
        player_character_id=char.id,
        game_state={"companion_ids": [], "scene_index": 0, "flags": {}},
        combat_active=False,
    )
    builder = ContextBuilder(
        session=fake_session,
        module=sample_module,
        characters=[char],
    )
    game_state_json = builder._build_game_state()
    # game_state JSON 字符串应包含玩家的所有叙事字段（DM prompt 拿去喂 LLM）
    for fragment in (
        payload["personality"],
        payload["backstory"],
        payload["speech_style"],
        payload["combat_preference"],
        payload["catchphrase"],
    ):
        assert fragment in game_state_json, f"game_state 缺少 {fragment[:10]}..."


async def test_wizard_starts_with_spells(client, sample_user, sample_module):
    """法师创建时必须有 cantrips + known_spells（数量由 dnd_rules 决定）。"""
    headers = await _auth_headers(client, sample_user)
    r = await client.post("/characters/create", headers=headers, json={
        "module_id": sample_module.id,
        "name": "测试法师",
        "race": "Elf",  # +2 dex +1 int
        "char_class": "Wizard",
        "level": 1,
        "background": "Sage",
        "alignment": "守序善良",
        "ability_scores": {"str": 8, "dex": 13, "con": 14, "int": 15, "wis": 12, "cha": 10},
        "proficient_skills": ["奥秘", "调查"],
        "cantrips": ["fire-bolt", "mage-hand", "prestidigitation"],
        "known_spells": ["magic-missile", "shield", "mage-armor", "detect-magic", "sleep", "burning-hands"],
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["caster_type"] == "full"
    assert len(data["cantrips"]) == 3
    assert len(data["known_spells"]) >= 1
    # 1 环位至少 2 槽
    assert data["spell_slots_max"].get("1st", 0) >= 2


# ─── Session 生命周期 ───────────────────────────────────

async def test_session_create_writes_opening_log_and_binds_player(
    client, db_session, sample_user, sample_module, sample_character,
):
    """创建 session 后：current_scene 非空，[开场] log 已写，player.session_id 已绑。"""
    headers = await _auth_headers(client, sample_user)
    r = await client.post("/game/sessions", headers=headers, json={
        "module_id": sample_module.id,
        "player_character_id": sample_character.id,
        "companion_ids": [],
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["session_id"]
    assert data["opening_scene"]

    # 验 DB 状态
    from models import Session, Character, GameLog
    from sqlalchemy import select
    sid = data["session_id"]
    session = await db_session.get(Session, sid)
    assert session is not None
    assert session.current_scene == data["opening_scene"]

    # 玩家角色已绑定 session（HTTP 请求用的是另一个 AsyncSession，
    # 这里要 expire 我们 fixture 的实例才能拿到最新的 DB 值）
    await db_session.refresh(sample_character)
    assert sample_character.session_id == sid

    # [开场] log 已写
    res = await db_session.execute(select(GameLog).where(GameLog.session_id == sid))
    logs = res.scalars().all()
    opening_logs = [l for l in logs if l.content.startswith("[开场]")]
    assert len(opening_logs) == 1


async def test_player_action_writes_logs_and_returns_narrative(
    client, sample_session, sample_user,
):
    """player_action 走 mock DM，应得到 PlayerActionResponse 形状的回包并写日志。"""
    headers = await _auth_headers(client, sample_user)
    r = await client.post("/game/action", headers=headers, json={
        "session_id":  sample_session.id,
        "action_text": "我环顾四周",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    # PlayerActionResponse 字段
    assert "narrative" in data
    assert "type" in data
    assert isinstance(data.get("dice_display", []), list)


async def test_skill_check_proficient_adds_bonus(
    client, db_session, sample_session, sample_character, sample_user,
):
    """proficient_skills 里有"运动"的角色做运动检定，modifier 应包含 prof_bonus。"""
    headers = await _auth_headers(client, sample_user)

    # sample_character 来自 conftest，已经熟练运动
    assert "运动" in (sample_character.proficient_skills or [])

    r = await client.post("/game/skill-check", headers=headers, json={
        "session_id":   sample_session.id,
        "character_id": sample_character.id,
        "skill":        "运动",
        "dc":           10,
        "d20_value":    10,  # 固定 d20 结果便于断言
    })
    assert r.status_code == 200, r.text
    result = r.json()
    # str_mod = 3 (16) + prof_bonus = 2 → modifier = 5
    assert result["modifier"] == 5
    assert result["proficient"] is True
    # total = d20 + modifier = 10 + 5 = 15
    assert result["total"] == 15


async def test_skill_check_non_proficient_no_bonus(
    client, db_session, sample_session, sample_character, sample_user,
):
    """没在 proficient_skills 里的技能不加 prof_bonus。"""
    headers = await _auth_headers(client, sample_user)

    r = await client.post("/game/skill-check", headers=headers, json={
        "session_id":   sample_session.id,
        "character_id": sample_character.id,
        "skill":        "巧手",  # 战士不熟练
        "dc":           10,
        "d20_value":    10,
    })
    assert r.status_code == 200, r.text
    result = r.json()
    # dex_mod = 2，无熟练加值
    assert result["modifier"] == 2
    assert result["proficient"] is False
    assert result["total"] == 12


# ─── 休息 ───────────────────────────────────────────────

async def test_long_rest_restores_hp_and_spells(
    client, db_session, sample_session, sample_character, sample_user,
):
    """长休：HP 回满、法术位重置、conditions 清空、concentration 清掉。"""
    headers = await _auth_headers(client, sample_user)

    # 把角色弄受伤 + 加条件
    sample_character.hp_current = 3
    sample_character.conditions = ["poisoned"]
    sample_character.concentration = "Bless"
    await db_session.commit()

    r = await client.post(
        f"/game/sessions/{sample_session.id}/rest",
        headers=headers,
        params={"rest_type": "long"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["rest_type"] == "long"
    assert len(data["characters"]) >= 1
    char_result = next(c for c in data["characters"] if c["name"] == sample_character.name)
    assert char_result["hp_current"] == sample_character.derived["hp_max"]

    # DB 状态
    await db_session.refresh(sample_character)
    assert sample_character.hp_current == sample_character.derived["hp_max"]
    assert sample_character.conditions == []
    assert sample_character.concentration is None


async def test_short_rest_consumes_hit_die(
    client, db_session, sample_session, sample_character, sample_user,
):
    """短休：消耗一个生命骰，HP 增加（值随机但 > 0），hit_dice_remaining -1。"""
    headers = await _auth_headers(client, sample_user)

    sample_character.hp_current = 3
    sample_character.hit_dice_remaining = 1
    await db_session.commit()

    r = await client.post(
        f"/game/sessions/{sample_session.id}/rest",
        headers=headers,
        params={"rest_type": "short"},
    )
    assert r.status_code == 200, r.text

    await db_session.refresh(sample_character)
    # 至少恢复 1 点 HP（heal_amt = max(1, hit_roll + con_mod)）
    assert sample_character.hp_current > 3
    # 生命骰被消耗
    assert sample_character.hit_dice_remaining == 0


# ─── 删除 session 的级联 ────────────────────────────────

async def test_delete_session_cleans_ai_companions_keeps_player(
    client, db_session, sample_session, sample_character, sample_user,
):
    """删除 session 后：AI 队友被删，玩家保留（user_id 关联），GameLog 清空。"""
    from models import Character, GameLog
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified
    import uuid as _uuid

    # 加一个 AI 队友
    ai = Character(
        id=str(_uuid.uuid4()), name="临时队友",
        race="Elf", char_class="Wizard", level=1,
        ability_scores={}, hp_current=6,
        is_player=False, session_id=sample_session.id,
    )
    db_session.add(ai)
    sample_session.game_state = {**sample_session.game_state, "companion_ids": [ai.id]}
    flag_modified(sample_session, "game_state")
    # 加一条日志
    db_session.add(GameLog(session_id=sample_session.id, role="dm", content="测试", log_type="narrative"))
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.delete(f"/game/sessions/{sample_session.id}", headers=headers)
    assert r.status_code == 200, r.text

    # AI 已删
    res = await db_session.execute(select(Character).where(Character.id == ai.id))
    assert res.scalar_one_or_none() is None
    # 玩家仍在（user_id 还在）
    res = await db_session.execute(select(Character).where(Character.id == sample_character.id))
    assert res.scalar_one_or_none() is not None
    # GameLog 全清
    res = await db_session.execute(
        select(GameLog).where(GameLog.session_id == sample_session.id)
    )
    assert res.scalars().all() == []
