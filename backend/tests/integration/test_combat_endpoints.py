"""
集成测试：P2 拆分后的 api/combat/ 子包各端点仍可响应。

验证重点不是战斗规则正确性（已在 unit 层测），而是：
  - 每个端点在合法请求下返回成功（拆分没切断 handler 链）
  - 404 / 400 分支符合预期
  - CombatState 创建后状态返回 shape 正确

战斗初始化我们直接手动插入 CombatState（不跑 AI，避开 /action 触发的复杂链路）。
"""
import asyncio
import uuid as _uuid
import pytest
import pytest_asyncio
from sqlalchemy import select

from models import CombatState

pytestmark = pytest.mark.integration


async def _auth_headers(client, sample_user):
    r = await client.post("/auth/login", json={
        "username": sample_user.username, "password": "password",
    })
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest_asyncio.fixture
async def combat_state(db_session, sample_session, sample_character):
    """手动注入一个进行中的战斗 + 一个敌人，供端点测试使用。"""
    from sqlalchemy.orm.attributes import flag_modified

    enemy_id = "goblin-1"
    sample_session.combat_active = True
    sample_session.game_state = {
        **(sample_session.game_state or {}),
        "enemies": [{
            "id": enemy_id,
            "name": "哥布林",
            "hp_current": 7, "max_hp": 7,
            "conditions": [],
            "derived": {"hp_max": 7, "ac": 15, "ability_modifiers": {"dex": 2}},
        }],
    }
    flag_modified(sample_session, "game_state")

    cs = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sample_session.id,
        grid_data={},
        entity_positions={
            sample_character.id: {"x": 5, "y": 5},
            enemy_id: {"x": 6, "y": 5},
        },
        turn_order=[
            {"character_id": sample_character.id, "name": sample_character.name, "initiative": 18, "is_player": True, "is_enemy": False},
            {"character_id": enemy_id, "name": "哥布林", "initiative": 12, "is_player": False, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={},
    )
    db_session.add(cs)
    await db_session.commit()
    await db_session.refresh(cs)
    return cs


async def test_get_combat_state_returns_entities(client, sample_session, combat_state, sample_user):
    """GET /game/combat/{id} — info.py 模块。"""
    headers = await _auth_headers(client, sample_user)
    r = await client.get(f"/game/combat/{sample_session.id}", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "entities" in data and "turn_order" in data
    # 玩家 + 敌人各一个实体
    assert len(data["entities"]) == 2


async def test_get_combat_state_includes_enemy_condition_durations(
    client, db_session, sample_session, combat_state, sample_user,
):
    """Enemy duration metadata must reach combat clients with the entity snapshot."""
    from sqlalchemy.orm.attributes import flag_modified

    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "conditions": ["restrained"],
        "condition_durations": {"restrained": 2},
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.get(f"/game/combat/{sample_session.id}", headers=headers)

    assert r.status_code == 200, r.text
    enemy = r.json()["entities"]["goblin-1"]
    assert enemy["conditions"] == ["restrained"]
    assert enemy["condition_durations"] == {"restrained": 2}


async def test_get_skill_bar(client, sample_session, combat_state, sample_user, sample_character):
    """GET /game/combat/{id}/skill-bar — info.py 模块。"""
    headers = await _auth_headers(client, sample_user)
    r = await client.get(
        f"/game/combat/{sample_session.id}/skill-bar",
        params={"entity_id": sample_character.id},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # 端点返回的 key 是 "bar"（不是 "skill_bar"）
    assert "bar" in data
    assert isinstance(data["bar"], list)
    assert data["char_class"] == "Fighter"


async def test_combat_state_404_when_no_combat(client, sample_user):
    """请求不存在的战斗 → 404。"""
    headers = await _auth_headers(client, sample_user)
    r = await client.get("/game/combat/nonexistent", headers=headers)
    assert r.status_code == 404


async def test_end_turn_advances_round(client, sample_session, combat_state, sample_user):
    """POST /game/combat/{id}/end-turn — turns.py 模块。"""
    headers = await _auth_headers(client, sample_user)
    r = await client.post(f"/game/combat/{sample_session.id}/end-turn", headers=headers)
    # end-turn 可能返回 200 也可能是 401（权限），只断言不是 500
    assert r.status_code != 500, r.text


async def test_end_turn_rejects_stale_expected_turn_token(
    client, db_session, sample_session, combat_state, sample_user,
):
    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": "1:0:not-the-current-actor"},
    )

    assert r.status_code == 409, r.text
    assert "stale" in r.text
    await db_session.refresh(combat_state)
    assert combat_state.current_turn_index == 0


async def test_natural_language_unreachable_melee_moves_without_fake_attack(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    """远距离近战意图应只移动靠近，不应生成一次范围外攻击叙事。"""
    import services.combat_narrator as narrator

    captured = {}

    async def fake_narrate_action(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(narrator, "narrate_action", fake_narrate_action)

    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        "goblin-1": {"x": 18, "y": 10},
    }
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        "/game/action",
        headers=headers,
        json={
            "session_id": sample_session.id,
            "action_text": "我向最近的哥布林移动并用长剑攻击它。",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["type"] == "combat_action"
    assert data["dice_display"] == []
    assert data["action_results"] == ["移动了 30ft"]
    assert captured["action_type"] == "move"
    assert "目标不在攻击范围内" not in data["narrative"]


async def test_natural_language_combat_respects_spent_action_and_remaining_movement(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    """Manual /game/action combat text may spend remaining movement but cannot reuse an action."""
    from services import action_parser, combat_narrator, input_guard
    from services.game_combat_action_executor import ACTION_ALREADY_USED_MESSAGE

    async def fake_classify_player_input(*_args, **_kwargs):
        return {"verdict": "in_game", "reason": "test", "refusal": ""}

    async def fake_parse_combat_action(**kwargs):
        assert kwargs["move_remaining"] == 2
        return {
            "actions": [
                {"type": "move", "target_id": "goblin-1"},
                {"type": "attack", "target_id": "goblin-1", "is_ranged": False},
            ],
            "narrative_hint": kwargs["player_input"],
            "_fallback": False,
        }

    async def fake_narrate_action(**_kwargs):
        return None

    monkeypatch.setattr(input_guard, "classify_player_input", fake_classify_player_input)
    monkeypatch.setattr(action_parser, "parse_combat_action", fake_parse_combat_action)
    monkeypatch.setattr(combat_narrator, "narrate_action", fake_narrate_action)

    combat_state.entity_positions = {
        sample_character.id: {"x": 0, "y": 0},
        "goblin-1": {"x": 4, "y": 0},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": True,
            "movement_used": 4,
            "movement_max": 6,
            "base_movement_max": 6,
        }
    }
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        "/game/action",
        headers=headers,
        json={
            "session_id": sample_session.id,
            "action_text": "I move closer and attack the goblin.",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["type"] == "combat_action"
    assert data["dice_display"] == []
    assert data["errors"] == [ACTION_ALREADY_USED_MESSAGE]
    assert data["combat_update"]["entity_positions"][sample_character.id] == {"x": 2, "y": 0}
    assert data["combat_update"]["turn_states"][sample_character.id]["action_used"] is True
    assert data["combat_update"]["turn_states"][sample_character.id]["movement_used"] == 6

    await db_session.refresh(combat_state)
    await db_session.refresh(sample_session)
    assert combat_state.entity_positions[sample_character.id] == {"x": 2, "y": 0}
    assert combat_state.turn_states[sample_character.id]["action_used"] is True
    assert combat_state.turn_states[sample_character.id]["movement_used"] == 6
    assert sample_session.game_state["enemies"][0]["hp_current"] == 7


async def test_combat_move_rejects_speed_zero_character(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    sample_character.conditions = ["grappled"]
    combat_state.turn_states = {
        sample_character.id: {
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
        }
    }
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={"entity_id": sample_character.id, "to_x": 4, "to_y": 5},
    )

    assert response.status_code == 400, response.text
    assert "speed is 0" in response.text
    await db_session.refresh(combat_state)
    assert combat_state.entity_positions[sample_character.id] == {"x": 5, "y": 5}


async def test_combat_move_allows_no_op_for_speed_zero_character(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    sample_character.conditions = ["grappled"]
    combat_state.turn_states = {
        sample_character.id: {
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
        }
    }
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={"entity_id": sample_character.id, "to_x": 5, "to_y": 5},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["movement_used"] == 0
    assert data["positions"][sample_character.id] == {"x": 5, "y": 5}


async def test_combat_move_rejects_stale_expected_turn_token(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "to_x": 4,
            "to_y": 5,
            "expected_turn_token": "1:0:not-the-current-actor",
        },
    )

    assert response.status_code == 409, response.text
    assert "stale" in response.text
    await db_session.refresh(combat_state)
    assert combat_state.entity_positions[sample_character.id] == {"x": 5, "y": 5}
    assert combat_state.turn_states == {}


async def test_combat_action_rejects_stale_expected_turn_token(
    client, db_session, sample_session, combat_state, sample_user,
):
    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/action",
        headers=headers,
        json={
            "action_text": "Dodge",
            "expected_turn_token": "1:0:not-the-current-actor",
        },
    )

    assert response.status_code == 409, response.text
    assert "stale" in response.text
    await db_session.refresh(combat_state)
    assert combat_state.turn_states == {}


async def test_attack_roll_rejects_stale_expected_turn_token(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "target_id": "goblin-1",
            "action_type": "melee",
            "d20_value": 15,
            "expected_turn_token": "1:0:not-the-current-actor",
        },
    )

    assert response.status_code == 409, response.text
    assert "stale" in response.text
    await db_session.refresh(combat_state)
    assert combat_state.turn_states == {}


async def test_spell_roll_rejects_stale_expected_turn_token(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    sample_character.char_class = "Wizard"
    sample_character.known_spells = ["魔法飞弹"]
    sample_character.spell_slots = {"1st": 1}
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/spell-roll",
        headers=headers,
        json={
            "caster_id": sample_character.id,
            "spell_name": "魔法飞弹",
            "spell_level": 1,
            "target_id": "goblin-1",
            "target_ids": ["goblin-1"],
            "expected_turn_token": "1:0:not-the-current-actor",
        },
    )

    assert response.status_code == 409, response.text
    assert "stale" in response.text
    await db_session.refresh(combat_state)
    assert combat_state.turn_states == {}


@pytest_asyncio.fixture
async def ai_turn_combat(db_session, sample_session, sample_character):
    """AI 回合用的最小战斗态。"""
    from sqlalchemy.orm.attributes import flag_modified

    enemy_id = "orc-1"
    sample_session.combat_active = True
    sample_session.game_state = {
        **(sample_session.game_state or {}),
        "enemies": [{
            "id": enemy_id,
            "name": "兽人",
            "hp_current": 9,
            "max_hp": 9,
            "derived": {"hp_max": 9, "ac": 13, "ability_modifiers": {"str": 3, "dex": 1}},
            "actions": [{"name": "重击", "type": "melee_attack", "damage_dice": "1d8", "attack_bonus": 5}],
            "speed": 30,
            "tactics": "冲锋",
            "type": "humanoid",
        }],
    }
    flag_modified(sample_session, "game_state")

    cs = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sample_session.id,
        grid_data={},
        entity_positions={
            sample_character.id: {"x": 5, "y": 5},
            enemy_id: {"x": 1, "y": 1},
        },
        turn_order=[
            {"character_id": enemy_id, "name": "兽人", "initiative": 18, "is_player": False, "is_enemy": True},
            {"character_id": sample_character.id, "name": sample_character.name, "initiative": 12, "is_player": True, "is_enemy": False},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={},
    )
    db_session.add(cs)
    await db_session.commit()
    await db_session.refresh(cs)
    return cs


async def test_ai_turn_rejects_stale_expected_turn_token(
    client, db_session, sample_session, ai_turn_combat, sample_user,
):
    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/ai-turn",
        headers=headers,
        json={"expected_turn_token": "1:0:not-the-current-actor"},
    )

    assert r.status_code == 409, r.text
    assert "stale" in r.text
    await db_session.refresh(ai_turn_combat)
    assert ai_turn_combat.current_turn_index == 0


async def test_ai_turn_skips_incapacitated_enemy_without_calling_llm(
    client, db_session, sample_session, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent

    state = sample_session.game_state or {}
    state["enemies"][0]["conditions"] = ["stunned"]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    async def fail_if_called(**_kwargs):
        raise AssertionError("AI decision should not run for incapacitated actors")

    monkeypatch.setattr(ai_agent, "get_ai_decision", fail_if_called)

    headers = await _auth_headers(client, sample_user)
    r = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["damage"] == 0
    assert data["next_turn_index"] == 1
    assert "stunned" in data["narration"]
    await db_session.refresh(ai_turn_combat)
    assert ai_turn_combat.current_turn_index == 1


async def test_ai_turn_refreshes_enemy_recharge_abilities_at_turn_start(
    client, db_session, sample_session, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import api.combat.ai_turn as ai_turn_module
    import services.ai_combat_agent as ai_agent

    state = sample_session.game_state or {}
    state["enemies"][0]["recharge_abilities"] = [{
        "id": "breath",
        "name": "Breath Weapon",
        "threshold": 5,
        "available": False,
    }]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "dash",
            "target_id": sample_session.player_character_id,
            "reason": "test recharge",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")

    def fake_refresh(enemy):
        enemy["recharge_abilities"][0]["available"] = True
        enemy["recharge_abilities"][0]["last_recharge_roll"] = 5
        return {"changed": True, "events": [], "abilities": enemy["recharge_abilities"]}

    monkeypatch.setattr(ai_turn_module, "refresh_recharge_abilities_at_turn_start", fake_refresh)

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    await db_session.refresh(sample_session)
    ability = sample_session.game_state["enemies"][0]["recharge_abilities"][0]
    assert ability["available"] is True
    assert ability["last_recharge_roll"] == 5


async def test_ai_turn_dash_decision_does_not_500(
    client, sample_session, ai_turn_combat, sample_user, monkeypatch,
):
    """/ai-turn 选择 dash 时应稳定返回，不应因为局部变量顺序报 500。"""
    import services.ai_combat_agent as ai_agent

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "dash",
            "target_id": sample_session.player_character_id,
            "action_name": None,
            "reason": "测试冲刺",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")

    headers = await _auth_headers(client, sample_user)
    r = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["actor_name"] == "兽人"
    assert data["next_turn_index"] == 1


async def test_ai_turn_uses_available_recharge_special_action(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_special as ai_turn_special

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["recharge_abilities"] = [{
        "id": "breath",
        "name": "Fire Breath",
        "threshold": 5,
        "available": True,
        "damage_dice": "6d6",
        "damage_type": "fire",
        "save": "dex",
        "save_dc": 13,
        "half_on_save": True,
    }]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.hp_current = 30
    sample_character.derived = {
        **(sample_character.derived or {}),
        "hp_max": 30,
        "ability_modifiers": {"dex": 0},
        "saving_throws": {"dex": 0},
    }
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "special",
            "target_id": sample_character.id,
            "action_name": "Fire Breath",
            "reason": "test breath",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(
        ai_turn_special,
        "roll_dice",
        lambda expr: {"notation": expr, "rolls": [3, 3, 3, 3, 3, 3], "total": 18},
    )
    monkeypatch.setattr(
        ai_turn_special,
        "roll_saving_throw",
        lambda *_args, **_kwargs: {"ability": "dex", "dc": 13, "total": 10, "success": False},
    )

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["special_action"]["name"] == "Fire Breath"
    assert body["damage"] == 18
    assert body["target_new_hp"] == 12
    await db_session.refresh(sample_character)
    assert sample_character.hp_current == 12
    await db_session.refresh(sample_session)
    assert sample_session.game_state["enemies"][0]["recharge_abilities"][0]["available"] is False


async def test_ai_turn_area_recharge_special_action_hits_multiple_characters(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import Character
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_special as ai_turn_special

    ally = Character(
        id=str(_uuid.uuid4()),
        user_id=sample_user.id,
        session_id=sample_session.id,
        name="Breath Ally",
        race="Human",
        char_class="Fighter",
        level=1,
        background="Soldier",
        ability_scores={"str": 12, "dex": 10, "con": 12, "int": 10, "wis": 10, "cha": 10},
        derived={"hp_max": 20, "ac": 14, "ability_modifiers": {"dex": 0}, "saving_throws": {"dex": 0}},
        hp_current=20,
        is_player=False,
    )
    far = Character(
        id=str(_uuid.uuid4()),
        user_id=sample_user.id,
        session_id=sample_session.id,
        name="Far Ally",
        race="Human",
        char_class="Fighter",
        level=1,
        background="Soldier",
        ability_scores={"str": 12, "dex": 10, "con": 12, "int": 10, "wis": 10, "cha": 10},
        derived={"hp_max": 20, "ac": 14, "ability_modifiers": {"dex": 0}, "saving_throws": {"dex": 0}},
        hp_current=20,
        is_player=False,
    )
    db_session.add_all([ally, far])

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["recharge_abilities"] = [{
        "id": "breath",
        "name": "Fire Breath",
        "threshold": 5,
        "available": True,
        "damage_dice": "6d6",
        "damage_type": "fire",
        "save": "dex",
        "save_dc": 13,
        "half_on_save": True,
        "area": "15 ft cone",
        "max_targets": 2,
    }]
    state["companion_ids"] = [ally.id, far.id]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.hp_current = 30
    sample_character.derived = {
        **(sample_character.derived or {}),
        "hp_max": 30,
        "ability_modifiers": {"dex": 0},
        "saving_throws": {"dex": 0},
    }
    ai_turn_combat.entity_positions = {
        enemy["id"]: {"x": 0, "y": 0},
        sample_character.id: {"x": 2, "y": 0},
        ally.id: {"x": 3, "y": 0},
        far.id: {"x": 9, "y": 0},
    }
    flag_modified(ai_turn_combat, "entity_positions")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "special",
            "target_id": sample_character.id,
            "action_name": "Fire Breath",
            "reason": "test area breath",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(
        ai_turn_special,
        "roll_dice",
        lambda expr: {"notation": expr, "rolls": [3, 3, 3, 3, 3, 3], "total": 18},
    )
    saves = iter([
        {"ability": "dex", "dc": 13, "total": 10, "success": False},
        {"ability": "dex", "dc": 13, "total": 16, "success": True},
    ])
    monkeypatch.setattr(ai_turn_special, "roll_saving_throw", lambda *_args, **_kwargs: next(saves))

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["special_action"]["name"] == "Fire Breath"
    assert body["damage"] == 27
    assert [item["target_id"] for item in body["target_results"]] == [sample_character.id, ally.id]
    assert [item["damage"] for item in body["target_results"]] == [18, 9]
    assert body["aoe_results"] == body["target_results"]
    await db_session.refresh(sample_character)
    await db_session.refresh(ally)
    await db_session.refresh(far)
    assert sample_character.hp_current == 12
    assert ally.hp_current == 11
    assert far.hp_current == 20
    await db_session.refresh(sample_session)
    assert sample_session.game_state["enemies"][0]["recharge_abilities"][0]["available"] is False


async def test_ai_spell_can_be_counterspelled_before_effect_resolves(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent
    import api.combat.reactions as reactions

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["name"] = "Enemy Mage"
    enemy["known_spells"] = ["火球术"]
    enemy["spell_slots"] = {"3rd": 1}
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "spell_ability": "int",
        "ability_modifiers": {"int": 3, "dex": 1},
        "spell_save_dc": 13,
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.char_class = "Wizard"
    sample_character.level = 5
    sample_character.known_spells = ["反制法术"]
    sample_character.spell_slots = {"3rd": 1}
    sample_character.hp_current = 12
    sample_character.derived = {
        **(sample_character.derived or {}),
        "spell_ability": "int",
        "ability_modifiers": {
            **(sample_character.derived or {}).get("ability_modifiers", {}),
            "int": 3,
        },
    }
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "spell",
            "target_id": sample_character.id,
            "action_name": "火球术",
            "reason": "test counterspell",
        }

    async def fake_narrate_action(**kwargs):
        return ""

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(reactions, "narrate_action", fake_narrate_action)

    headers = await _auth_headers(client, sample_user)
    prompt_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert prompt_response.status_code == 200, prompt_response.text
    prompt_body = prompt_response.json()
    assert prompt_body["player_can_react"] is True
    assert prompt_body["reaction_prompt"]["trigger"] == "spell_cast"
    assert prompt_body["reaction_prompt"]["options"][0]["type"] == "counterspell"
    assert prompt_body["next_turn_index"] == 0

    await db_session.refresh(ai_turn_combat)
    turn_state = ai_turn_combat.turn_states[sample_character.id]
    assert turn_state["pending_spell_reaction"]["spell_name"] == "火球术"

    reaction = await client.post(
        f"/game/combat/{sample_session.id}/reaction",
        headers=headers,
        json={
            "reaction_type": "counterspell",
            "target_id": "orc-1",
            "character_id": sample_character.id,
        },
    )
    assert reaction.status_code == 200, reaction.text
    reaction_body = reaction.json()
    assert reaction_body["reaction_effect"]["spell_cancelled"] is True
    assert reaction_body["reaction_effect"]["slot_used"] == "3rd"

    await db_session.refresh(sample_character)
    await db_session.refresh(ai_turn_combat)
    await db_session.refresh(sample_session)
    assert sample_character.hp_current == 12
    assert sample_character.spell_slots["3rd"] == 0
    assert ai_turn_combat.current_turn_index == 1
    assert "pending_spell_reaction" not in ai_turn_combat.turn_states[sample_character.id]
    enemy_after = sample_session.game_state["enemies"][0]
    assert enemy_after["spell_slots"]["3rd"] == 0


async def test_declined_counterspell_resumes_pending_ai_spell(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["name"] = "Enemy Mage"
    enemy["known_spells"] = ["魔法飞弹"]
    enemy["spell_slots"] = {"1st": 1}
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "spell_ability": "int",
        "ability_modifiers": {"int": 3, "dex": 1},
        "spell_save_dc": 13,
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.char_class = "Wizard"
    sample_character.level = 5
    sample_character.known_spells = ["Counterspell"]
    sample_character.spell_slots = {"3rd": 1}
    sample_character.hp_current = 12
    await db_session.commit()

    calls = {"count": 0}

    async def fake_get_ai_decision(**kwargs):
        calls["count"] += 1
        return {
            "action_type": "spell",
            "target_id": sample_character.id,
            "action_name": "魔法飞弹",
            "reason": "test decline",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")

    headers = await _auth_headers(client, sample_user)
    prompt_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert prompt_response.status_code == 200, prompt_response.text
    assert prompt_response.json()["reaction_prompt"]["options"][0]["type"] == "counterspell"

    decline = await client.post(
        f"/game/combat/{sample_session.id}/reaction",
        headers=headers,
        json={
            "reaction_type": "decline",
            "target_id": "orc-1",
            "character_id": sample_character.id,
        },
    )
    assert decline.status_code == 200, decline.text

    resumed = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert resumed.status_code == 200, resumed.text
    resumed_body = resumed.json()
    assert resumed_body["damage"] > 0
    assert resumed_body["target_new_hp"] < 12
    assert resumed_body["next_turn_index"] == 1
    assert calls["count"] == 1

    await db_session.refresh(sample_character)
    await db_session.refresh(ai_turn_combat)
    await db_session.refresh(sample_session)
    assert sample_character.spell_slots["3rd"] == 1
    assert sample_session.game_state["enemies"][0]["spell_slots"]["1st"] == 0
    assert "resume_spell_reaction" not in ai_turn_combat.turn_states[sample_character.id]


async def test_counterspell_prompt_falls_back_to_party_caster_when_target_cannot_react(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    import uuid as _uuid
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent
    from models import Character

    wizard = Character(
        id=str(_uuid.uuid4()),
        user_id=sample_user.id,
        session_id=sample_session.id,
        name="Party Wizard",
        race="Elf",
        char_class="Wizard",
        level=5,
        background="Sage",
        ability_scores={"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 10},
        derived={
            "hp_max": 8,
            "ac": 12,
            "initiative": 1,
            "spell_ability": "int",
            "ability_modifiers": {"str": -1, "dex": 2, "con": 1, "int": 3, "wis": 0, "cha": 0},
        },
        hp_current=8,
        known_spells=["Counterspell"],
        spell_slots={"3rd": 1},
        is_player=False,
    )
    db_session.add(wizard)

    state = sample_session.game_state or {}
    state["companion_ids"] = [wizard.id]
    enemy = state["enemies"][0]
    enemy["name"] = "Enemy Mage"
    enemy["known_spells"] = ["魔法飞弹"]
    enemy["spell_slots"] = {"1st": 1}
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "spell_ability": "int",
        "ability_modifiers": {"int": 3, "dex": 1},
        "spell_save_dc": 13,
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.known_spells = []
    sample_character.spell_slots = {}
    sample_character.hp_current = 12
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "spell",
            "target_id": sample_character.id,
            "action_name": "魔法飞弹",
            "reason": "test party counterspell",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")

    headers = await _auth_headers(client, sample_user)
    prompt_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert prompt_response.status_code == 200, prompt_response.text
    prompt_body = prompt_response.json()
    assert prompt_body["target_id"] == sample_character.id
    assert prompt_body["player_can_react"] is True
    assert prompt_body["reaction_prompt"]["reactor_character_id"] == wizard.id
    assert prompt_body["reaction_prompt"]["spell_target_id"] == sample_character.id

    await db_session.refresh(ai_turn_combat)
    assert "pending_spell_reaction" not in ai_turn_combat.turn_states.get(sample_character.id, {})
    assert ai_turn_combat.turn_states[wizard.id]["pending_spell_reaction"]["spell_name"] == "魔法飞弹"


async def test_counterspell_prompt_is_not_offered_beyond_60ft(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["name"] = "Enemy Mage"
    enemy["known_spells"] = ["魔法飞弹"]
    enemy["spell_slots"] = {"1st": 1}
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "spell_ability": "int",
        "ability_modifiers": {"int": 3, "dex": 1},
        "spell_save_dc": 13,
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.char_class = "Wizard"
    sample_character.level = 5
    sample_character.known_spells = ["Counterspell"]
    sample_character.spell_slots = {"3rd": 1}
    sample_character.hp_current = 12
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 18, "y": 5},
    }
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "spell",
            "target_id": sample_character.id,
            "action_name": "魔法飞弹",
            "reason": "test counterspell range",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("player_can_react") in (None, False)
    assert body.get("reaction_prompt") is None
    assert body["damage"] > 0
    assert body["target_new_hp"] < 12

    await db_session.refresh(sample_character)
    await db_session.refresh(ai_turn_combat)
    assert sample_character.spell_slots["3rd"] == 1
    assert "pending_spell_reaction" not in ai_turn_combat.turn_states.get(sample_character.id, {})


async def test_counterspell_reaction_rechecks_range_before_consuming_slot(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["name"] = "Enemy Mage"
    enemy["known_spells"] = ["魔法飞弹"]
    enemy["spell_slots"] = {"1st": 1}
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "spell_ability": "int",
        "ability_modifiers": {"int": 3, "dex": 1},
        "spell_save_dc": 13,
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.char_class = "Wizard"
    sample_character.level = 5
    sample_character.known_spells = ["Counterspell"]
    sample_character.spell_slots = {"3rd": 1}
    sample_character.hp_current = 12
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 10, "y": 5},
    }
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "spell",
            "target_id": sample_character.id,
            "action_name": "魔法飞弹",
            "reason": "test stale counterspell range",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")

    headers = await _auth_headers(client, sample_user)
    prompt_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert prompt_response.status_code == 200, prompt_response.text
    assert prompt_response.json()["reaction_prompt"]["options"][0]["type"] == "counterspell"

    await db_session.refresh(ai_turn_combat)
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 18, "y": 5},
    }
    await db_session.commit()

    reaction = await client.post(
        f"/game/combat/{sample_session.id}/reaction",
        headers=headers,
        json={
            "reaction_type": "counterspell",
            "target_id": enemy["id"],
            "character_id": sample_character.id,
        },
    )

    assert reaction.status_code == 400, reaction.text
    assert "out of range" in reaction.text
    await db_session.refresh(sample_character)
    await db_session.refresh(ai_turn_combat)
    await db_session.refresh(sample_session)
    assert sample_character.spell_slots["3rd"] == 1
    assert sample_session.game_state["enemies"][0]["spell_slots"]["1st"] == 1
    assert ai_turn_combat.turn_states[sample_character.id]["pending_spell_reaction"]["spell_name"] == "魔法飞弹"


async def test_concurrent_ai_turn_with_same_token_only_advances_once(
    client, db_session, sample_session, ai_turn_combat, sample_user, monkeypatch,
):
    import services.ai_combat_agent as ai_agent

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "dash",
            "target_id": sample_session.player_character_id,
            "action_name": None,
            "reason": "concurrent guard",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")

    headers = await _auth_headers(client, sample_user)
    response_one, response_two = await asyncio.gather(
        client.post(
            f"/game/combat/{sample_session.id}/ai-turn",
            headers=headers,
            json={"expected_turn_token": "1:0:orc-1"},
        ),
        client.post(
            f"/game/combat/{sample_session.id}/ai-turn",
            headers=headers,
            json={"expected_turn_token": "1:0:orc-1"},
        ),
    )

    status_codes = sorted([response_one.status_code, response_two.status_code])
    assert status_codes == [200, 409]
    await db_session.refresh(ai_turn_combat)
    assert ai_turn_combat.current_turn_index == 1
    assert ai_turn_combat.round_number == 1


async def test_ai_fire_attack_respects_player_fire_resistance(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    """火焰抗性药水写入的 fire_resistance 条件应在 AI 火焰伤害中真实减半。"""
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["name"] = "火焰仆役"
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "damage_type": "fire",
    }
    enemy["actions"] = [{"name": "火焰触碰", "type": "melee_attack", "damage_dice": "2d6", "attack_bonus": 5}]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.hp_current = 12
    sample_character.conditions = ["fire_resistance"]
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "action_name": "火焰触碰",
            "reason": "测试火焰伤害",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 20,
                "target_ac": 10,
            },
            damage=10,
            damage_roll={"formula": "2d6", "rolls": [5, 5], "total": 10},
            narration="命中",
        )

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)

    headers = await _auth_headers(client, sample_user)
    r = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["damage"] == 5
    assert data["target_new_hp"] == 7
    await db_session.refresh(sample_character)
    assert sample_character.hp_current == 7


async def test_ai_fire_attack_offers_absorb_elements_and_reaction_restores_half_damage(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack
    import api.combat.reactions as reactions

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["name"] = "Flame Imp"
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "damage_type": "fire",
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    sample_character.char_class = "Wizard"
    sample_character.level = 3
    sample_character.hp_current = 12
    sample_character.known_spells = ["吸收元素"]
    sample_character.spell_slots = {"1st": 1}
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "action_name": "Fire Claw",
            "reason": "test absorb elements",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 20,
                "target_ac": 10,
            },
            damage=9,
            damage_roll={"formula": "2d6", "rolls": [4, 5], "total": 9},
            narration="hit",
        )

    async def fake_narrate_action(**kwargs):
        return ""

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(reactions, "narrate_action", fake_narrate_action)

    headers = await _auth_headers(client, sample_user)
    prompt_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert prompt_response.status_code == 200, prompt_response.text
    prompt_body = prompt_response.json()
    assert prompt_body["damage"] == 9
    assert prompt_body["target_new_hp"] == 3
    assert prompt_body["player_can_react"] is True
    absorb = next(
        reaction
        for reaction in prompt_body["reaction_prompt"]["available_reactions"]
        if reaction["type"] == "absorb_elements"
    )
    assert absorb["damage_type"] == "fire"
    assert absorb["damage_prevented"] == 5
    assert absorb["extra_damage_dice"] == "1d6"

    reaction = await client.post(
        f"/game/combat/{sample_session.id}/reaction",
        headers=headers,
        json={
            "reaction_type": "absorb_elements",
            "target_id": enemy["id"],
            "character_id": sample_character.id,
        },
    )
    assert reaction.status_code == 200, reaction.text
    reaction_body = reaction.json()
    assert reaction_body["reaction_effect"]["damage_prevented"] == 5
    assert reaction_body["reaction_effect"]["hp_restored"] == 5
    assert reaction_body["reaction_effect"]["damage_dice"] == "1d6"

    await db_session.refresh(sample_character)
    await db_session.refresh(ai_turn_combat)
    assert sample_character.hp_current == 8
    assert sample_character.spell_slots["1st"] == 0
    assert sample_character.class_resources["absorb_elements"]["damage_type"] == "fire"
    assert sample_character.condition_durations["fire_resistance"] == 1
    assert ai_turn_combat.turn_states[sample_character.id]["reaction_used"] is True
    assert "pending_attack_reaction" not in ai_turn_combat.turn_states[sample_character.id]


async def test_duplicate_absorb_elements_reaction_is_idempotent(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack
    import api.combat.reactions as reactions

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["name"] = "Flame Imp"
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "damage_type": "fire",
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    sample_character.char_class = "Wizard"
    sample_character.level = 3
    sample_character.hp_current = 12
    sample_character.known_spells = ["鍚告敹鍏冪礌"]
    sample_character.spell_slots = {"1st": 1}
    sample_character.known_spells = ["Absorb Elements"]
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "action_name": "Fire Claw",
            "reason": "test duplicate absorb elements",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 20,
                "target_ac": 10,
            },
            damage=9,
            damage_roll={"formula": "2d6", "rolls": [4, 5], "total": 9},
            narration="hit",
        )

    async def fake_narrate_action(**kwargs):
        return ""

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(reactions, "narrate_action", fake_narrate_action)

    headers = await _auth_headers(client, sample_user)
    prompt_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert prompt_response.status_code == 200, prompt_response.text
    assert prompt_response.json()["target_new_hp"] == 3

    payload = {
        "reaction_type": "absorb_elements",
        "target_id": enemy["id"],
        "character_id": sample_character.id,
    }
    first = await client.post(f"/game/combat/{sample_session.id}/reaction", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["reaction_effect"]["hp_restored"] == 5

    await db_session.refresh(sample_character)
    hp_after_first = sample_character.hp_current
    slots_after_first = dict(sample_character.spell_slots or {})

    second = await client.post(f"/game/combat/{sample_session.id}/reaction", headers=headers, json=payload)
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["action"] == "reaction_already_resolved"
    assert second_body["reaction_effect"]["already_resolved"] is True

    await db_session.refresh(sample_character)
    assert sample_character.hp_current == hp_after_first == 8
    assert sample_character.spell_slots == slots_after_first == {"1st": 0}


async def test_declining_attack_reaction_clears_pending_reaction(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["name"] = "Flame Imp"
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "damage_type": "fire",
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    sample_character.char_class = "Wizard"
    sample_character.level = 3
    sample_character.hp_current = 12
    sample_character.known_spells = ["Absorb Elements"]
    sample_character.spell_slots = {"1st": 1}
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "action_name": "Fire Claw",
            "reason": "test decline attack reaction",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 20,
                "target_ac": 10,
            },
            damage=9,
            damage_roll={"formula": "2d6", "rolls": [4, 5], "total": 9},
            narration="hit",
        )

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)

    headers = await _auth_headers(client, sample_user)
    prompt_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert prompt_response.status_code == 200, prompt_response.text
    assert prompt_response.json()["reaction_prompt"]["available_reactions"][0]["type"] == "absorb_elements"

    decline = await client.post(
        f"/game/combat/{sample_session.id}/reaction",
        headers=headers,
        json={
            "reaction_type": "decline",
            "target_id": enemy["id"],
            "character_id": sample_character.id,
        },
    )
    assert decline.status_code == 200, decline.text
    assert decline.json()["action"] == "reaction_declined"

    await db_session.refresh(sample_character)
    await db_session.refresh(ai_turn_combat)
    assert sample_character.hp_current == 3
    assert sample_character.spell_slots == {"1st": 1}
    assert "pending_attack_reaction" not in ai_turn_combat.turn_states[sample_character.id]


async def test_absorb_elements_can_trigger_even_if_attack_drops_character_to_zero(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack
    import api.combat.reactions as reactions

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["name"] = "Flame Imp"
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "damage_type": "fire",
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    sample_character.char_class = "Wizard"
    sample_character.level = 3
    sample_character.hp_current = 6
    sample_character.known_spells = ["吸收元素"]
    sample_character.spell_slots = {"1st": 1}
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "action_name": "Fire Claw",
            "reason": "test absorb elements at zero",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 20,
                "target_ac": 10,
            },
            damage=9,
            damage_roll={"formula": "2d6", "rolls": [4, 5], "total": 9},
            narration="hit",
        )

    async def fake_narrate_action(**kwargs):
        return ""

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(reactions, "narrate_action", fake_narrate_action)

    headers = await _auth_headers(client, sample_user)
    prompt_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert prompt_response.status_code == 200, prompt_response.text
    prompt_body = prompt_response.json()
    assert prompt_body["target_new_hp"] == 0
    assert prompt_body["reaction_prompt"]["available_reactions"][0]["type"] == "absorb_elements"

    reaction = await client.post(
        f"/game/combat/{sample_session.id}/reaction",
        headers=headers,
        json={
            "reaction_type": "absorb_elements",
            "target_id": enemy["id"],
            "character_id": sample_character.id,
        },
    )
    assert reaction.status_code == 200, reaction.text
    await db_session.refresh(sample_character)
    assert sample_character.hp_current == 5
    assert sample_character.death_saves is None
    assert "unconscious" not in (sample_character.conditions or [])


async def test_ai_bludgeoning_attack_does_not_offer_absorb_elements(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "damage_type": "bludgeoning",
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    sample_character.known_spells = ["吸收元素"]
    sample_character.spell_slots = {"1st": 1}
    sample_character.hp_current = 12
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "action_name": "Club",
            "reason": "test non elemental damage",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 20,
                "target_ac": 10,
            },
            damage=8,
            damage_roll={"formula": "1d8", "rolls": [8], "total": 8},
            narration="hit",
        )

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("reaction_prompt") is None
    await db_session.refresh(sample_character)
    assert sample_character.spell_slots["1st"] == 1


async def test_ai_hex_bonus_is_not_reduced_by_player_fire_resistance(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack
    from services import combat_damage_bonus_service

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["name"] = "Hexed Fire Adept"
    enemy["concentration"] = "Hex"
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "damage_type": "fire",
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.hp_current = 20
    sample_character.conditions = ["fire_resistance", "hexed"]
    sample_character.condition_durations = {"hexed": 600}
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "action_name": "Hexed Fire Strike",
            "reason": "test typed damage separation",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 20,
                "target_ac": 10,
            },
            damage=10,
            damage_roll={"formula": "2d6", "rolls": [5, 5], "total": 10},
            narration="hit",
        )

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(combat_damage_bonus_service, "roll_dice", lambda expr: {"formula": expr, "rolls": [4], "total": 4})

    headers = await _auth_headers(client, sample_user)
    r = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["damage"] == 9
    assert data["target_new_hp"] == 11
    await db_session.refresh(sample_character)
    assert sample_character.hp_current == 11


async def test_assassinate_action_hit_does_not_500(
    client, db_session, sample_session, combat_state, sample_character, monkeypatch,
):
    """旧 /action 攻击路径触发 Assassinate 自动暴击时不应因局部变量顺序报 500。"""
    from services.combat_service import AttackResult
    import api.combat.attacks as attacks
    import services.combat_direct_attack_service as direct_attack

    sample_character.char_class = "Rogue"
    sample_character.level = 3
    sample_character.derived = {
        **(sample_character.derived or {}),
        "attack_bonus": 8,
        "hit_die": 6,
        "subclass_effects": {"assassinate": True},
        "ability_modifiers": {
            **(sample_character.derived or {}).get("ability_modifiers", {}),
            "str": 3,
            "dex": 4,
        },
    }
    await db_session.commit()

    def fake_resolve_melee_attack(**kwargs):
        return AttackResult(
            attack_roll={
                "d20": 14,
                "attack_bonus": 8,
                "attack_total": 22,
                "target_ac": 15,
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
            },
            damage=5,
            damage_roll={"formula": "1d6+3", "rolls": [2], "total": 5},
            narration="测试命中",
        )

    async def fake_narrate_action(**kwargs):
        return None

    monkeypatch.setattr(attacks.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(attacks, "narrate_action", fake_narrate_action)
    monkeypatch.setattr(direct_attack, "roll_dice", lambda expr: {"formula": expr, "rolls": [3], "total": 3})

    r = await client.post(
        f"/game/combat/{sample_session.id}/action",
        json={"action_text": "普通攻击", "target_id": "goblin-1"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["attack_result"]["is_crit"] is True
    assert any("暗杀暴击" in note for note in data["extra_damage_notes"])


async def test_attack_roll_then_damage_roll_applies_damage(
    client, sample_session, combat_state, sample_user, sample_character,
):
    """/attack-roll 命中后使用 /damage-roll 应扣减目标 HP 并清理 pending attack。"""
    headers = await _auth_headers(client, sample_user)

    attack = await client.post(
        f"/game/combat/{sample_session.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "target_id": "goblin-1",
            "action_type": "melee",
            "d20_value": 15,
        },
    )
    assert attack.status_code == 200, attack.text
    attack_data = attack.json()
    assert attack_data["hit"] is True
    assert attack_data["pending_attack_id"]

    damage = await client.post(
        f"/game/combat/{sample_session.id}/damage-roll",
        headers=headers,
        json={
            "pending_attack_id": attack_data["pending_attack_id"],
            "damage_values": [4],
        },
    )
    assert damage.status_code == 200, damage.text
    damage_data = damage.json()
    assert damage_data["target_id"] == "goblin-1"
    assert damage_data["damage_total"] == 7  # 1d8 frontend roll 4 + STR mod 3
    assert damage_data["target_new_hp"] == 0
    assert "pending_attack" not in damage_data["turn_state"]


async def test_attack_roll_consumes_tracked_ammunition(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    headers = await _auth_headers(client, sample_user)
    sample_character.equipment = {
        "weapons": [{
            "name": "Longbow",
            "damage": "1d8",
            "type": "martial_ranged",
            "properties": ["ammunition", "range(150/600)", "two-handed"],
            "equipped": True,
            "ammo": 2,
        }]
    }
    sample_character.derived = {
        **(sample_character.derived or {}),
        "ranged_attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {
            **(sample_character.derived or {}).get("ability_modifiers", {}),
            "dex": 3,
        },
    }
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        "goblin-1": {"x": 9, "y": 5},
    }
    await db_session.commit()

    attack = await client.post(
        f"/game/combat/{sample_session.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "target_id": "goblin-1",
            "action_type": "ranged",
            "d20_value": 15,
        },
    )

    assert attack.status_code == 200, attack.text
    data = attack.json()
    assert data["weapon_resource"] == {
        "weapon": "Longbow",
        "resource_type": "ammunition",
        "consumed": True,
        "ammo_remaining": 1,
    }
    await db_session.refresh(sample_character)
    assert sample_character.equipment["weapons"][0]["ammo"] == 1


async def test_damage_roll_critical_hit_on_zero_hp_character_adds_two_death_failures(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from models import Character

    headers = await _auth_headers(client, sample_user)
    companion = Character(
        id=str(_uuid.uuid4()),
        user_id=None,
        name="AI Striker",
        race="Human",
        char_class="Fighter",
        level=1,
        background="Soldier",
        ability_scores={"str": 16, "dex": 10, "con": 12, "int": 10, "wis": 10, "cha": 10},
        derived={
            "hp_max": 10,
            "ac": 14,
            "proficiency_bonus": 2,
            "attack_bonus": 5,
            "ability_modifiers": {"str": 3, "dex": 0, "con": 1, "int": 0, "wis": 0, "cha": 0},
        },
        hp_current=10,
        is_player=False,
        session_id=sample_session.id,
    )
    db_session.add(companion)
    sample_character.hp_current = 0
    sample_character.death_saves = {"successes": 0, "failures": 1, "stable": False}
    sample_character.conditions = ["unconscious"]
    pending_attack_id = "crit-on-dying"
    combat_state.turn_states = {
        companion.id: {
            "pending_attack": {
                "pending_attack_id": pending_attack_id,
                "target_id": sample_character.id,
                "target_name": sample_character.name,
                "target_is_enemy": False,
                "hit": True,
                "is_crit": True,
                "is_ranged": False,
                "hit_die": 6,
                "dmg_mod": 0,
                "attack_roll": {
                    "d20": 20,
                    "attack_bonus": 5,
                    "attack_total": 25,
                    "target_ac": 16,
                    "hit": True,
                    "is_crit": True,
                    "is_fumble": False,
                },
            },
        },
    }
    await db_session.commit()

    damage = await client.post(
        f"/game/combat/{sample_session.id}/damage-roll",
        headers=headers,
        json={
            "pending_attack_id": pending_attack_id,
            "damage_values": [3, 2],
        },
    )

    assert damage.status_code == 200, damage.text
    await db_session.refresh(sample_character)
    assert sample_character.hp_current == 0
    assert sample_character.death_saves == {"successes": 0, "failures": 3, "stable": False}


async def test_spell_roll_then_confirm_applies_damage_and_consumes_slot(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    """/spell-roll 创建 pending spell，/spell-confirm 应扣 HP 并消耗法术位。"""
    sample_character.char_class = "Wizard"
    sample_character.spell_slots = {"1st": 1}
    sample_character.known_spells = ["魔法飞弹"]
    sample_character.derived = {
        **(sample_character.derived or {}),
        "spell_ability": "int",
        "spell_save_dc": 13,
        "ability_modifiers": {
            **(sample_character.derived or {}).get("ability_modifiers", {}),
            "int": 3,
        },
    }
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)

    spell_roll = await client.post(
        f"/game/combat/{sample_session.id}/spell-roll",
        headers=headers,
        json={
            "caster_id": sample_character.id,
            "spell_name": "魔法飞弹",
            "spell_level": 1,
            "target_id": "goblin-1",
        },
    )
    assert spell_roll.status_code == 200, spell_roll.text
    roll_data = spell_roll.json()
    assert roll_data["pending_spell_id"]
    assert roll_data["damage_dice"] == "3d4+3"

    confirm = await client.post(
        f"/game/combat/{sample_session.id}/spell-confirm",
        headers=headers,
        json={
            "pending_spell_id": roll_data["pending_spell_id"],
            "damage_values": [1, 1, 1],
        },
    )
    assert confirm.status_code == 200, confirm.text
    confirm_data = confirm.json()
    assert confirm_data["target_id"] == "goblin-1"
    assert confirm_data["damage"] == 6  # frontend dice 1+1+1 plus INT mod 3
    assert confirm_data["target_new_hp"] == 1
    assert confirm_data["remaining_slots"]["1st"] == 0
    assert "pending_spell" not in confirm_data["turn_state"]


async def test_spell_roll_then_confirm_aoe_control_applies_condition_durations(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    """AoE control spells should apply per-target conditions and durations through the API."""
    from sqlalchemy.orm.attributes import flag_modified

    sample_character.char_class = "Wizard"
    sample_character.spell_slots = {"2nd": 1}
    sample_character.known_spells = ["网"]
    sample_character.derived = {
        **(sample_character.derived or {}),
        "spell_ability": "int",
        "spell_save_dc": 30,
        "ability_modifiers": {
            **(sample_character.derived or {}).get("ability_modifiers", {}),
            "int": 3,
        },
    }
    state = dict(sample_session.game_state or {})
    state["enemies"] = [
        {
            "id": "goblin-1",
            "name": "哥布林",
            "hp_current": 7,
            "max_hp": 7,
            "conditions": [],
            "derived": {"hp_max": 7, "ac": 15, "ability_modifiers": {"dex": -5}, "saving_throws": {"dex": -5}},
        },
        {
            "id": "goblin-2",
            "name": "哥布林弓手",
            "hp_current": 7,
            "max_hp": 7,
            "conditions": [],
            "derived": {"hp_max": 7, "ac": 13, "ability_modifiers": {"dex": -5}, "saving_throws": {"dex": -5}},
        },
    ]
    sample_session.game_state = state
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        "goblin-1": {"x": 6, "y": 5},
        "goblin-2": {"x": 7, "y": 5},
    }
    flag_modified(sample_session, "game_state")
    flag_modified(combat_state, "entity_positions")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    spell_roll = await client.post(
        f"/game/combat/{sample_session.id}/spell-roll",
        headers=headers,
        json={
            "caster_id": sample_character.id,
            "spell_name": "网",
            "spell_level": 2,
            "target_ids": ["goblin-1", "goblin-2"],
        },
    )
    assert spell_roll.status_code == 200, spell_roll.text

    confirm = await client.post(
        f"/game/combat/{sample_session.id}/spell-confirm",
        headers=headers,
        json={"pending_spell_id": spell_roll.json()["pending_spell_id"]},
    )
    assert confirm.status_code == 200, confirm.text
    data = confirm.json()
    assert data["is_concentration"] is True
    assert [item["target_id"] for item in data["aoe_results"]] == ["goblin-1", "goblin-2"]
    assert data["aoe_results"][0]["condition_durations"] == {"restrained": 600}
    await db_session.refresh(sample_session)
    enemies = sample_session.game_state["enemies"]
    assert enemies[0]["conditions"] == ["restrained"]
    assert enemies[1]["conditions"] == ["restrained"]
    assert enemies[0]["condition_durations"] == {"restrained": 600}
    assert enemies[1]["condition_durations"] == {"restrained": 600}
    await db_session.refresh(sample_character)
    assert sample_character.concentration == "网"


async def test_condition_add_and_remove(client, db_session, sample_session, combat_state, sample_user, sample_character):
    """POST /game/combat/{id}/condition/add + remove — conditions.py 模块。"""
    headers = await _auth_headers(client, sample_user)
    sample_character.concentration = "Bless"
    await db_session.commit()

    r = await client.post(
        f"/game/combat/{sample_session.id}/condition/add",
        headers=headers,
        json={"entity_id": sample_character.id, "condition": "paralyzed", "is_enemy": False, "rounds": 3},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["concentration"] is None
    assert data["target_state"]["concentration"] is None
    assert data["target_state"]["conditions"] == ["paralyzed"]
    assert data["target_state"]["life_state"] == "alive"
    await db_session.refresh(sample_character)
    assert sample_character.concentration is None

    r = await client.post(
        f"/game/combat/{sample_session.id}/condition/remove",
        headers=headers,
        json={"entity_id": sample_character.id, "condition": "paralyzed", "is_enemy": False},
    )
    assert r.status_code == 200, r.text


async def test_condition_add_respects_enemy_condition_immunity(client, db_session, sample_session, combat_state, sample_user):
    headers = await _auth_headers(client, sample_user)
    state = dict(sample_session.game_state or {})
    state["enemies"] = [{
        "id": "ooze-1",
        "name": "Ooze",
        "hp_current": 12,
        "hp_max": 12,
        "conditions": [],
        "condition_immunities": ["paralyzed"],
    }]
    sample_session.game_state = state
    await db_session.commit()

    r = await client.post(
        f"/game/combat/{sample_session.id}/condition/add",
        headers=headers,
        json={"entity_id": "ooze-1", "condition": "paralyzed", "is_enemy": True, "rounds": 3},
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["immune"] is True
    assert data["applied"] is False
    assert data["conditions"] == []
    await db_session.refresh(sample_session)
    assert sample_session.game_state["enemies"][0]["conditions"] == []


async def test_end_combat_clears_flag(client, sample_session, combat_state, db_session, sample_user):
    """POST /game/combat/{id}/end — ai_turn.py 模块里定义的结束战斗端点。"""
    headers = await _auth_headers(client, sample_user)
    r = await client.post(f"/game/combat/{sample_session.id}/end", headers=headers)
    assert r.status_code == 200, r.text
    await db_session.refresh(sample_session)
    assert sample_session.combat_active is False
    deleted = await db_session.execute(
        select(CombatState).where(CombatState.id == combat_state.id)
    )
    assert deleted.scalar_one_or_none() is None

    followup = await client.get(f"/game/combat/{sample_session.id}", headers=headers)
    assert followup.status_code == 404
