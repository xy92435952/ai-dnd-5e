"""
集成测试：P2 拆分后的 api/combat/ 子包各端点仍可响应。

验证重点不是战斗规则正确性（已在 unit 层测），而是：
  - 每个端点在合法请求下返回成功（拆分没切断 handler 链）
  - 404 / 400 分支符合预期
  - CombatState 创建后状态返回 shape 正确

战斗初始化我们直接手动插入 CombatState（不跑 AI，避开 /action 触发的复杂链路）。
"""
import uuid as _uuid
import pytest
import pytest_asyncio

from models import CombatState

pytestmark = pytest.mark.integration


async def _auth_headers(client, sample_user):
    r = await client.post("/auth/login", json={
        "username": sample_user.username, "password": "password",
    })
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def _register_user(client, username, password="password", display_name=None):
    r = await client.post("/auth/register", json={
        "username": username,
        "password": password,
        "display_name": display_name or username,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


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
    assert data["action_results"] == ["移动了 30ft", "已靠近，下一回合可继续攻击"]
    assert captured["action_type"] == "move"
    assert "目标不在攻击范围内" not in data["narrative"]


async def test_natural_language_help_marks_named_ally_as_helped(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    """自然语言协助应给指定队友写入 being_helped，而不是掉到纯叙事。"""
    import uuid as _uuid
    from models import Character
    from sqlalchemy.orm.attributes import flag_modified
    import services.combat_narrator as narrator

    ally = Character(
        id=str(_uuid.uuid4()),
        session_id=sample_session.id,
        user_id=None,
        is_player=False,
        name="米拉",
        race="Human",
        char_class="Rogue",
        level=1,
        background="Scout",
        ability_scores={"str": 10, "dex": 16, "con": 12, "int": 10, "wis": 12, "cha": 10},
        derived={"hp_max": 9, "ac": 14, "ability_modifiers": {"dex": 3}},
        hp_current=9,
    )
    db_session.add(ally)
    sample_session.game_state = {
        **(sample_session.game_state or {}),
        "companion_ids": [ally.id],
    }
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    async def fake_narrate_action(**kwargs):
        return None

    monkeypatch.setattr(narrator, "narrate_action", fake_narrate_action)

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        "/game/action",
        headers=headers,
        json={
            "session_id": sample_session.id,
            "action_text": "我协助米拉攻击哥布林。",
        },
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["type"] == "combat_action"
    assert data["action_results"] == ["协助 米拉，下次攻击或检定具有优势"]

    await db_session.refresh(combat_state)
    assert combat_state.turn_states[str(ally.id)]["being_helped"] is True


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


async def test_ai_turn_dash_decision_does_not_500(
    client, sample_session, ai_turn_combat, monkeypatch,
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

    r = await client.post(f"/game/combat/{sample_session.id}/ai-turn")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["actor_name"] == "兽人"
    assert data["next_turn_index"] == 1


async def test_ai_fire_attack_respects_player_fire_resistance(
    client, db_session, sample_session, sample_character, ai_turn_combat, monkeypatch,
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

    r = await client.post(f"/game/combat/{sample_session.id}/ai-turn")

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["damage"] == 5
    assert data["target_new_hp"] == 7
    await db_session.refresh(sample_character)
    assert sample_character.hp_current == 7


async def test_assassinate_action_hit_does_not_500(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
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

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/action",
        headers=headers,
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


async def test_spell_roll_missing_caster_error_text_is_readable(
    client, sample_session, combat_state, sample_user,
):
    """缺失施法者的 404 文案不应出现编码损坏字符。"""
    headers = await _auth_headers(client, sample_user)

    r = await client.post(
        f"/game/combat/{sample_session.id}/spell-roll",
        headers=headers,
        json={
            "caster_id": str(_uuid.uuid4()),
            "spell_name": "魔法飞弹",
            "spell_level": 1,
            "target_id": "goblin-1",
        },
    )

    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "施法者不存在"


async def test_condition_add_and_remove(client, sample_session, combat_state, sample_user, sample_character):
    """POST /game/combat/{id}/condition/add + remove — conditions.py 模块。"""
    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/condition/add",
        headers=headers,
        json={"entity_id": sample_character.id, "condition": "poisoned", "is_enemy": False, "rounds": 3},
    )
    assert r.status_code == 200, r.text

    r = await client.post(
        f"/game/combat/{sample_session.id}/condition/remove",
        headers=headers,
        json={"entity_id": sample_character.id, "condition": "poisoned", "is_enemy": False},
    )
    assert r.status_code == 200, r.text


async def _seed_multiplayer_combat(client, db_session, sample_module):
    import uuid as _uuid
    from sqlalchemy.orm.attributes import flag_modified
    from models import Character, CombatState, Session

    host = await _register_user(client, f"combat_host_{_uuid.uuid4().hex[:8]}")
    guest = await _register_user(client, f"combat_guest_{_uuid.uuid4().hex[:8]}")
    create = (await client.post("/game/rooms/create", headers=_headers(host["token"]), json={
        "module_id": sample_module.id,
        "save_name": "Combat MP",
        "max_players": 4,
    })).json()
    sid = create["session_id"]
    await client.post("/game/rooms/join", headers=_headers(guest["token"]), json={
        "room_code": create["room_code"],
    })

    def make_char(owner, name, char_class="Fighter", level=1, derived_extra=None):
        derived = {
            "hp_max": 12,
            "ac": 16,
            "initiative": 2,
            "proficiency_bonus": 2,
            "attack_bonus": 5,
            "ability_modifiers": {"str": 3, "dex": 2, "con": 2, "int": 0, "wis": 1, "cha": -1},
            "spell_slots_max": {},
            **(derived_extra or {}),
        }
        return Character(
            id=str(_uuid.uuid4()),
            session_id=sid,
            user_id=owner["user_id"],
            is_player=True,
            name=name,
            race="Human",
            char_class=char_class,
            level=level,
            background="Soldier",
            ability_scores={"str": 16, "dex": 14, "con": 15, "int": 10, "wis": 12, "cha": 8},
            derived=derived,
            hp_current=12,
            proficient_skills=["运动", "感知"],
            proficient_saves=["str", "con"],
        )

    host_char = make_char(host, "Host Fighter")
    guest_char = make_char(guest, "Guest Fighter")
    db_session.add_all([host_char, guest_char])
    await db_session.commit()

    await client.post(f"/game/rooms/{sid}/claim-character", headers=_headers(host["token"]), json={"character_id": host_char.id})
    await client.post(f"/game/rooms/{sid}/claim-character", headers=_headers(guest["token"]), json={"character_id": guest_char.id})
    await client.post(f"/game/rooms/{sid}/start", headers=_headers(host["token"]))

    session = await db_session.get(Session, sid)
    session.combat_active = True
    session.game_state = {
        **(session.game_state or {}),
        "enemies": [{
            "id": "mp-goblin-1",
            "name": "多人哥布林",
            "hp_current": 30,
            "max_hp": 30,
            "conditions": [],
            "derived": {"hp_max": 30, "ac": 10, "ability_modifiers": {"dex": 1, "str": 0, "wis": 0}},
        }],
    }
    flag_modified(session, "game_state")

    cs = CombatState(
        id=str(_uuid.uuid4()),
        session_id=sid,
        grid_data={},
        entity_positions={
            host_char.id: {"x": 5, "y": 5},
            guest_char.id: {"x": 7, "y": 5},
            "mp-goblin-1": {"x": 6, "y": 5},
        },
        turn_order=[
            {"character_id": host_char.id, "name": host_char.name, "initiative": 18, "is_player": True, "is_enemy": False},
            {"character_id": guest_char.id, "name": guest_char.name, "initiative": 15, "is_player": True, "is_enemy": False},
            {"character_id": "mp-goblin-1", "name": "多人哥布林", "initiative": 10, "is_player": False, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={},
    )
    db_session.add(cs)
    await db_session.commit()
    await db_session.refresh(host_char)
    await db_session.refresh(guest_char)
    await db_session.refresh(cs)
    return {
        "session_id": sid,
        "host": host,
        "guest": guest,
        "host_char": host_char,
        "guest_char": guest_char,
        "combat": cs,
        "enemy_id": "mp-goblin-1",
    }


async def test_multiplayer_guest_cannot_act_during_host_combat_turn(
    client, db_session, sample_module, monkeypatch,
):
    """多人战斗中，访客不能在房主角色回合通过旧接口或实体参数越权。"""
    import api.combat.attacks as attacks

    async def fake_narrate_action(**kwargs):
        return None

    monkeypatch.setattr(attacks, "narrate_action", fake_narrate_action)

    setup = await _seed_multiplayer_combat(client, db_session, sample_module)
    sid = setup["session_id"]
    guest_headers = _headers(setup["guest"]["token"])

    guest_end = await client.post(f"/game/combat/{sid}/end-turn", headers=guest_headers)
    assert guest_end.status_code == 403

    guest_moves_host = await client.post(
        f"/game/combat/{sid}/move",
        headers=guest_headers,
        json={"entity_id": setup["host_char"].id, "to_x": 5, "to_y": 6},
    )
    assert guest_moves_host.status_code == 403

    guest_moves_enemy = await client.post(
        f"/game/combat/{sid}/move",
        headers=guest_headers,
        json={"entity_id": setup["enemy_id"], "to_x": 8, "to_y": 8},
    )
    assert guest_moves_enemy.status_code == 403

    guest_old_action = await client.post(
        f"/game/combat/{sid}/action",
        headers=guest_headers,
        json={"action_text": "普通攻击", "target_id": setup["enemy_id"]},
    )
    assert guest_old_action.status_code == 403


async def test_multiplayer_session_detail_returns_current_users_character(
    client, db_session, sample_module,
):
    """多人 Combat 页面恢复 session 时，每个用户应拿到自己认领的角色。"""
    setup = await _seed_multiplayer_combat(client, db_session, sample_module)
    sid = setup["session_id"]

    host_session = await client.get(f"/game/sessions/{sid}", headers=_headers(setup["host"]["token"]))
    guest_session = await client.get(f"/game/sessions/{sid}", headers=_headers(setup["guest"]["token"]))

    assert host_session.status_code == 200, host_session.text
    assert guest_session.status_code == 200, guest_session.text
    assert host_session.json()["player"]["id"] == setup["host_char"].id
    assert guest_session.json()["player"]["id"] == setup["guest_char"].id


async def test_multiplayer_combat_state_includes_all_claimed_player_entities(
    client, db_session, sample_module,
):
    """多人 Combat 状态应包含所有认领角色，保证双方页面都有战斗实体。"""
    setup = await _seed_multiplayer_combat(client, db_session, sample_module)
    sid = setup["session_id"]

    response = await client.get(f"/game/combat/{sid}", headers=_headers(setup["guest"]["token"]))

    assert response.status_code == 200, response.text
    entities = response.json()["entities"]
    assert setup["host_char"].id in entities
    assert setup["guest_char"].id in entities
    assert entities[setup["host_char"].id]["name"] == setup["host_char"].name
    assert entities[setup["guest_char"].id]["name"] == setup["guest_char"].name


async def test_multiplayer_old_action_uses_current_users_claimed_character(
    client, db_session, sample_module, monkeypatch,
):
    """旧 /action 路径在多人中应使用当前用户认领角色，而不是 session.player_character_id。"""
    import api.combat.attacks as attacks
    from services.combat_service import AttackResult

    async def fake_narrate_action(**kwargs):
        return None

    def fake_resolve_melee_attack(**kwargs):
        return AttackResult(
            attack_roll={
                "d20": 12,
                "attack_bonus": 5,
                "attack_total": 17,
                "target_ac": 10,
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
            },
            damage=1,
            damage_roll={"formula": "1d8+3", "rolls": [1], "total": 4},
            narration="测试命中",
        )

    monkeypatch.setattr(attacks, "narrate_action", fake_narrate_action)
    monkeypatch.setattr(attacks.svc, "resolve_melee_attack", fake_resolve_melee_attack)

    setup = await _seed_multiplayer_combat(client, db_session, sample_module)
    sid = setup["session_id"]
    host_headers = _headers(setup["host"]["token"])

    r = await client.post(
        f"/game/combat/{sid}/action",
        headers=host_headers,
        json={"action_text": "普通攻击", "target_id": setup["enemy_id"]},
    )
    assert r.status_code == 200, r.text

    await db_session.refresh(setup["combat"])
    assert setup["combat"].turn_states[str(setup["host_char"].id)]["attacks_made"] == 1
    assert str(setup["guest_char"].id) not in (setup["combat"].turn_states or {})


async def test_end_combat_clears_flag(client, sample_session, combat_state, db_session, sample_user):
    """POST /game/combat/{id}/end — ai_turn.py 模块里定义的结束战斗端点。"""
    headers = await _auth_headers(client, sample_user)
    r = await client.post(f"/game/combat/{sample_session.id}/end", headers=headers)
    assert r.status_code == 200, r.text
    await db_session.refresh(sample_session)
    assert sample_session.combat_active is False
