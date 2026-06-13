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

from models import CombatState, GameLog

pytestmark = pytest.mark.integration


async def _auth_headers(client, sample_user):
    r = await client.post("/auth/login", json={
        "username": sample_user.username, "password": "password",
    })
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _patch_smite_narration(monkeypatch):
    from api.combat import smites

    async def fake_narrate_action(**_kwargs):
        return ""

    monkeypatch.setattr(smites, "narrate_action", fake_narrate_action)


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
            "cr": "1",
            "speed": 30,
            "resistances": ["poison"],
            "immunities": [],
            "vulnerabilities": ["radiant"],
            "condition_immunities": ["poisoned"],
            "actions": [{"name": "Scimitar"}],
            "special_abilities": [{"name": "Nimble Escape"}],
            "tactics": "Hide after striking.",
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


async def test_get_combat_state_returns_entities(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    """GET /game/combat/{id} — info.py 模块。"""
    sample_character.concentration = "Bless"
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.get(f"/game/combat/{sample_session.id}", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "entities" in data and "turn_order" in data
    # 玩家 + 敌人各一个实体
    assert len(data["entities"]) == 2
    assert data["entities"][sample_character.id]["concentration"] == "Bless"


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


async def test_get_combat_state_hides_unrevealed_enemy_details(
    client, sample_session, combat_state, sample_user,
):
    headers = await _auth_headers(client, sample_user)
    r = await client.get(f"/game/combat/{sample_session.id}", headers=headers)

    assert r.status_code == 200, r.text
    enemy = r.json()["entities"]["goblin-1"]
    assert "actions" not in enemy
    assert "resistances" not in enemy
    assert "revealed_stats" not in enemy


async def test_get_combat_state_exposes_legendary_action_resource_without_unrevealed_actions(
    client, db_session, sample_session, combat_state, sample_user,
):
    from sqlalchemy.orm.attributes import flag_modified

    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "legendary_actions": [
            {"name": "Tail Attack", "cost": 1},
            {"name": "Wing Buffet", "cost": 2},
        ],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 2,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.get(f"/game/combat/{sample_session.id}", headers=headers)

    assert r.status_code == 200, r.text
    enemy = r.json()["entities"]["goblin-1"]
    assert enemy["legendary_action_uses"] == 3
    assert enemy["legendary_action_uses_remaining"] == 2
    assert "legendary_actions" not in enemy


async def test_end_turn_legendary_action_prompt_and_endpoint_spends_resource(
    client, db_session, sample_session, combat_state, sample_user,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import GameLog

    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "legendary_actions": [
            {"id": "detect", "name": "Detect", "cost": 1, "description": "Perceive a threat."},
            {"id": "wing", "name": "Wing Attack", "cost": 2},
        ],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 2,
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    end_turn = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_session.player_character_id}"},
    )

    assert end_turn.status_code == 200, end_turn.text
    prompt = end_turn.json()["legendary_action_prompt"]
    assert prompt["actor_id"] == "goblin-1"
    assert prompt["remaining"] == 2
    assert [action["id"] for action in prompt["actions"]] == ["detect", "wing"]

    use_action = await client.post(
        f"/game/combat/{sample_session.id}/legendary-action",
        headers=headers,
        json={"actor_id": "goblin-1", "action_id": "detect"},
    )

    assert use_action.status_code == 200, use_action.text
    body = use_action.json()
    assert body["action"] == "legendary_action"
    assert body["actor_state"]["legendary_action_uses"] == 3
    assert body["actor_state"]["legendary_action_uses_remaining"] == 1
    assert body["dice_result"]["action_name"] == "Detect"

    await db_session.refresh(sample_session)
    enemy = sample_session.game_state["enemies"][0]
    assert enemy["legendary_action_uses_remaining"] == 1
    log_result = await db_session.execute(select(GameLog).where(GameLog.session_id == sample_session.id))
    assert any("uses Legendary Action: Detect" in log.content for log in log_result.scalars())

    followup = await client.get(f"/game/combat/{sample_session.id}", headers=headers)
    assert followup.status_code == 200, followup.text
    assert followup.json()["entities"]["goblin-1"]["legendary_action_uses_remaining"] == 1


async def test_legendary_action_attack_hits_target_and_updates_hp(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import GameLog
    from api.combat import legendary_actions as legendary_actions_api

    sample_character.hp_current = 20
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "legendary_actions": [{
            "id": "tail",
            "name": "Tail Strike",
            "cost": 1,
            "attack_bonus": 7,
            "damage_dice": "1d8+3",
            "damage_type": "bludgeoning",
        }],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 2,
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    monkeypatch.setattr(legendary_actions_api, "roll_attack", lambda *args, **kwargs: {
        "d20": 12,
        "attack_bonus": 7,
        "attack_total": 19,
        "target_ac": 14,
        "hit": True,
        "is_crit": False,
        "is_fumble": False,
    })
    monkeypatch.setattr(legendary_actions_api, "roll_dice", lambda notation: {
        "notation": notation,
        "rolls": [5],
        "bonus": 3,
        "total": 8,
    })
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    end_turn = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_session.player_character_id}"},
    )

    assert end_turn.status_code == 200, end_turn.text
    prompt_action = end_turn.json()["legendary_action_prompt"]["actions"][0]
    assert prompt_action["resolution"] == "attack"
    assert prompt_action["target_id"] == sample_character.id
    assert prompt_action["attack_bonus"] == 7
    assert prompt_action["damage_dice"] == "1d8+3"

    use_action = await client.post(
        f"/game/combat/{sample_session.id}/legendary-action",
        headers=headers,
        json={"actor_id": "goblin-1", "action_id": "tail", "target_id": sample_character.id},
    )

    assert use_action.status_code == 200, use_action.text
    body = use_action.json()
    assert body["resolution"] == "attack"
    assert body["hit"] is True
    assert body["damage"] == 8
    assert body["hp_before"] == 20
    assert body["target_state"]["hp_current"] == 12
    assert body["actor_state"]["legendary_action_uses_remaining"] == 1
    assert body["dice_result"]["attack"]["attack_total"] == 19
    assert body["dice_result"]["damage_roll"]["notation"] == "1d8+3"

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    assert sample_character.hp_current == 12
    assert sample_session.game_state["enemies"][0]["legendary_action_uses_remaining"] == 1
    log_result = await db_session.execute(select(GameLog).where(GameLog.session_id == sample_session.id))
    assert any("uses Legendary Action: Tail Strike" in log.content and "hits" in log.content for log in log_result.scalars())

    followup = await client.get(f"/game/combat/{sample_session.id}", headers=headers)
    assert followup.status_code == 200, followup.text
    assert followup.json()["entities"][sample_character.id]["hp_current"] == 12


async def test_legendary_action_attack_can_prompt_shield_and_restore_damage(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from api.combat import legendary_actions as legendary_actions_api
    from api.combat import reactions as reactions_api

    sample_character.char_class = "Wizard"
    sample_character.level = 3
    sample_character.hp_current = 20
    sample_character.known_spells = ["Shield"]
    sample_character.prepared_spells = []
    sample_character.spell_slots = {"1st": 1}
    sample_character.derived = {
        **(sample_character.derived or {}),
        "ac": 16,
        "hp_max": 20,
    }
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "legendary_actions": [{
            "id": "tail",
            "name": "Tail Strike",
            "cost": 1,
            "attack_bonus": 7,
            "damage_dice": "1d8+3",
            "damage_type": "bludgeoning",
        }],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 2,
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    monkeypatch.setattr(legendary_actions_api, "roll_attack", lambda *args, **kwargs: {
        "d20": 11,
        "attack_bonus": 7,
        "attack_total": 18,
        "target_ac": 16,
        "hit": True,
        "is_crit": False,
        "is_fumble": False,
    })
    monkeypatch.setattr(legendary_actions_api, "roll_dice", lambda notation: {
        "notation": notation,
        "rolls": [5],
        "bonus": 3,
        "total": 8,
    })

    async def fake_narrate_action(**kwargs):
        return ""

    monkeypatch.setattr(reactions_api, "narrate_action", fake_narrate_action)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    use_action = await client.post(
        f"/game/combat/{sample_session.id}/legendary-action",
        headers=headers,
        json={"actor_id": "goblin-1", "action_id": "tail", "target_id": sample_character.id},
    )

    assert use_action.status_code == 200, use_action.text
    body = use_action.json()
    assert body["resolution"] == "attack"
    assert body["damage"] == 8
    assert body["target_state"]["hp_current"] == 12
    assert body["player_can_react"] is True
    shield = body["reaction_prompt"]["available_reactions"][0]
    assert shield["type"] == "shield"
    assert shield["damage_prevented"] == 8

    await db_session.refresh(combat_state)
    pending = combat_state.turn_states[sample_character.id]["pending_attack_reaction"]
    assert pending["trigger"] == "incoming_attack"
    assert pending["events"][0]["attack_total"] == 18
    assert pending["events"][0]["target_ac"] == 16
    assert pending["events"][0]["damage"] == 8

    reaction = await client.post(
        f"/game/combat/{sample_session.id}/reaction",
        headers=headers,
        json={
            "reaction_type": "shield",
            "target_id": "goblin-1",
            "character_id": sample_character.id,
        },
    )
    assert reaction.status_code == 200, reaction.text
    reaction_body = reaction.json()
    assert reaction_body["reaction_effect"]["damage_prevented"] == 8
    assert reaction_body["reaction_effect"]["hp_restored"] == 8
    assert reaction_body["dice_result"]["type"] == "reaction"
    assert reaction_body["dice_result"]["reaction_type"] == "shield"
    assert reaction_body["dice_result"]["damage_prevented"] == 8
    assert reaction_body["dice_result"]["hp_restored"] == 8
    assert reaction_body["special_action"] == reaction_body["dice_result"]
    assert reaction_body["target_state"]["hp_current"] == 20

    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    assert sample_character.hp_current == 20
    assert sample_character.spell_slots["1st"] == 0
    assert combat_state.turn_states[sample_character.id]["reaction_used"] is True
    assert "pending_attack_reaction" not in combat_state.turn_states[sample_character.id]


async def test_legendary_action_save_failure_applies_damage_and_updates_hp(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import GameLog
    from api.combat import legendary_actions as legendary_actions_api

    sample_character.hp_current = 20
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "legendary_actions": [{
            "id": "wing",
            "name": "Wing Buffet",
            "cost": 2,
            "save": "dex",
            "save_dc": 15,
            "damage_dice": "2d6",
            "damage_type": "bludgeoning",
            "half_on_save": True,
        }],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 2,
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    monkeypatch.setattr(legendary_actions_api, "roll_saving_throw", lambda *args, **kwargs: {
        "ability": "dex",
        "d20": 5,
        "modifier": 2,
        "total": 7,
        "dc": 15,
        "success": False,
    })
    monkeypatch.setattr(legendary_actions_api, "roll_dice", lambda notation: {
        "notation": notation,
        "rolls": [4, 5],
        "bonus": 0,
        "total": 9,
    })
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    end_turn = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_session.player_character_id}"},
    )

    assert end_turn.status_code == 200, end_turn.text
    prompt_action = end_turn.json()["legendary_action_prompt"]["actions"][0]
    assert prompt_action["resolution"] == "save"
    assert prompt_action["target_id"] == sample_character.id
    assert prompt_action["save_ability"] == "dex"
    assert prompt_action["save_dc"] == 15
    assert prompt_action["damage_dice"] == "2d6"
    assert prompt_action["half_on_save"] is True

    use_action = await client.post(
        f"/game/combat/{sample_session.id}/legendary-action",
        headers=headers,
        json={"actor_id": "goblin-1", "action_id": "wing", "target_id": sample_character.id},
    )

    assert use_action.status_code == 200, use_action.text
    body = use_action.json()
    assert body["resolution"] == "save"
    assert body["save"]["success"] is False
    assert body["damage"] == 9
    assert body["hp_before"] == 20
    assert body["target_state"]["hp_current"] == 11
    assert body["target_state"]["save"]["dc"] == 15
    assert body["actor_state"]["legendary_action_uses_remaining"] == 0
    assert body["dice_result"]["save"]["ability"] == "dex"
    assert body["dice_result"]["damage_roll"]["notation"] == "2d6"
    assert body["special_action"] == body["dice_result"]

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    assert sample_character.hp_current == 11
    assert sample_session.game_state["enemies"][0]["legendary_action_uses_remaining"] == 0
    log_result = await db_session.execute(select(GameLog).where(GameLog.session_id == sample_session.id))
    assert any("uses Legendary Action: Wing Buffet" in log.content and "fails" in log.content for log in log_result.scalars())

    followup = await client.get(f"/game/combat/{sample_session.id}", headers=headers)
    assert followup.status_code == 200, followup.text
    assert followup.json()["entities"][sample_character.id]["hp_current"] == 11


async def test_legendary_action_save_condition_rider_applies_without_damage(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import GameLog
    from api.combat import legendary_actions as legendary_actions_api

    sample_character.hp_current = 20
    sample_character.concentration = "Bless"
    sample_character.conditions = []
    sample_character.condition_durations = {}
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "legendary_actions": [{
            "id": "mind-lock",
            "name": "Mind Lock",
            "cost": 1,
            "save": "wis",
            "save_dc": 15,
            "condition_on_failed_save": "stunned",
            "condition_duration_rounds": 1,
        }],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 1,
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    monkeypatch.setattr(legendary_actions_api, "roll_saving_throw", lambda *args, **kwargs: {
        "ability": "wis",
        "d20": 4,
        "modifier": 1,
        "total": 5,
        "dc": 15,
        "success": False,
    })
    monkeypatch.setattr(
        legendary_actions_api,
        "roll_dice",
        lambda notation: (_ for _ in ()).throw(AssertionError("non-damaging rider should not roll damage")),
    )
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    end_turn = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_session.player_character_id}"},
    )

    assert end_turn.status_code == 200, end_turn.text
    prompt_action = end_turn.json()["legendary_action_prompt"]["actions"][0]
    assert prompt_action["resolution"] == "save"
    assert prompt_action["target_id"] == sample_character.id
    assert prompt_action["save_ability"] == "wis"
    assert prompt_action["condition_on_failed_save"] == "stunned"
    assert prompt_action["condition_duration_rounds"] == 1
    assert "damage_dice" not in prompt_action

    use_action = await client.post(
        f"/game/combat/{sample_session.id}/legendary-action",
        headers=headers,
        json={"actor_id": "goblin-1", "action_id": "mind-lock", "target_id": sample_character.id},
    )

    assert use_action.status_code == 200, use_action.text
    body = use_action.json()
    assert body["resolution"] == "save"
    assert body["damage"] == 0
    assert body["target_state"]["hp_current"] == 20
    assert body["target_state"]["conditions"] == ["stunned"]
    assert body["target_state"]["condition_durations"] == {"stunned": 1}
    assert body["target_state"]["concentration"] is None
    assert body["condition_result"] == {
        "condition": "stunned",
        "applied": True,
        "immune": False,
        "duration_rounds": 1,
        "concentration_broken": True,
        "concentration_check": body["concentration_check"],
        "concentration_effect_updates": [],
    }
    assert body["concentration_check"]["broke"] is True
    assert body["concentration_check"]["automatic"] is True
    assert body["actor_state"]["legendary_action_uses_remaining"] == 0
    assert body["dice_result"]["condition_result"]["condition"] == "stunned"

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    assert sample_character.hp_current == 20
    assert sample_character.conditions == ["stunned"]
    assert sample_character.condition_durations == {"stunned": 1}
    assert sample_character.concentration is None
    assert sample_session.game_state["enemies"][0]["legendary_action_uses_remaining"] == 0
    log_result = await db_session.execute(select(GameLog).where(GameLog.session_id == sample_session.id))
    assert any("uses Legendary Action: Mind Lock" in log.content and "affected by stunned" in log.content for log in log_result.scalars())


async def test_legendary_action_save_forced_movement_pushes_failed_target(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import GameLog
    from services import combat_opportunity_attack_service as opportunity
    from api.combat import legendary_actions as legendary_actions_api

    sample_character.hp_current = 20
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "legendary_actions": [{
            "id": "wing-gust",
            "name": "Wing Gust",
            "cost": 1,
            "save": "str",
            "save_dc": 16,
            "push_distance_ft": 5,
        }],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 1,
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        "goblin-1": {"x": 6, "y": 5},
    }
    combat_state.turn_states = {
        "goblin-1": {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(sample_session, "game_state")
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_states")

    monkeypatch.setattr(legendary_actions_api, "roll_saving_throw", lambda *args, **kwargs: {
        "ability": "str",
        "d20": 6,
        "modifier": 2,
        "total": 8,
        "dc": 16,
        "success": False,
    })
    monkeypatch.setattr(
        legendary_actions_api,
        "roll_dice",
        lambda notation: (_ for _ in ()).throw(AssertionError("forced movement rider should not roll damage")),
    )
    monkeypatch.setattr(
        opportunity.svc,
        "resolve_melee_attack",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("forced movement must not trigger opportunity attacks")),
    )
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    end_turn = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_session.player_character_id}"},
    )

    assert end_turn.status_code == 200, end_turn.text
    prompt_action = end_turn.json()["legendary_action_prompt"]["actions"][0]
    assert prompt_action["resolution"] == "save"
    assert prompt_action["target_id"] == sample_character.id
    assert prompt_action["save_ability"] == "str"
    assert prompt_action["save_dc"] == 16
    assert prompt_action["push_distance_ft"] == 5
    assert "damage_dice" not in prompt_action

    use_action = await client.post(
        f"/game/combat/{sample_session.id}/legendary-action",
        headers=headers,
        json={"actor_id": "goblin-1", "action_id": "wing-gust", "target_id": sample_character.id},
    )

    assert use_action.status_code == 200, use_action.text
    body = use_action.json()
    assert body["resolution"] == "save"
    assert body["damage"] == 0
    assert body["target_state"]["hp_current"] == 20
    assert body["forced_movement"] == {
        "type": "push",
        "applied": True,
        "target_id": sample_character.id,
        "target_name": sample_character.name,
        "distance_ft": 5,
        "requested_distance_ft": 5,
        "steps": 1,
        "from": {"x": 5, "y": 5},
        "to": {"x": 4, "y": 5},
    }
    assert body["dice_result"]["forced_movement"]["to"] == {"x": 4, "y": 5}
    assert body["actor_state"]["legendary_action_uses_remaining"] == 0

    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    await db_session.refresh(sample_session)
    assert sample_character.hp_current == 20
    assert combat_state.entity_positions[sample_character.id] == {"x": 4, "y": 5}
    assert combat_state.turn_states["goblin-1"]["reaction_used"] is False
    assert sample_session.game_state["enemies"][0]["legendary_action_uses_remaining"] == 0
    log_result = await db_session.execute(select(GameLog).where(GameLog.session_id == sample_session.id))
    assert any("uses Legendary Action: Wing Gust" in log.content and "pushed" in log.content for log in log_result.scalars())


async def test_legendary_action_save_forced_movement_pulls_failed_target(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from api.combat import legendary_actions as legendary_actions_api

    sample_character.hp_current = 20
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "legendary_actions": [{
            "id": "gravity-tug",
            "name": "Gravity Tug",
            "cost": 1,
            "save": "str",
            "save_dc": 16,
            "pull_distance_ft": 5,
        }],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 1,
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    combat_state.entity_positions = {
        sample_character.id: {"x": 4, "y": 5},
        "goblin-1": {"x": 6, "y": 5},
    }
    flag_modified(sample_session, "game_state")
    flag_modified(combat_state, "entity_positions")

    monkeypatch.setattr(legendary_actions_api, "roll_saving_throw", lambda *args, **kwargs: {
        "ability": "str",
        "d20": 6,
        "modifier": 2,
        "total": 8,
        "dc": 16,
        "success": False,
    })
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    end_turn = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_session.player_character_id}"},
    )

    assert end_turn.status_code == 200, end_turn.text
    prompt_action = end_turn.json()["legendary_action_prompt"]["actions"][0]
    assert prompt_action["pull_distance_ft"] == 5

    use_action = await client.post(
        f"/game/combat/{sample_session.id}/legendary-action",
        headers=headers,
        json={"actor_id": "goblin-1", "action_id": "gravity-tug", "target_id": sample_character.id},
    )

    assert use_action.status_code == 200, use_action.text
    body = use_action.json()
    assert body["forced_movement"]["type"] == "pull"
    assert body["forced_movement"]["from"] == {"x": 4, "y": 5}
    assert body["forced_movement"]["to"] == {"x": 5, "y": 5}

    await db_session.refresh(combat_state)
    assert combat_state.entity_positions[sample_character.id] == {"x": 5, "y": 5}


async def test_legendary_action_multi_target_save_uses_shared_damage_roll(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import Character, GameLog
    from api.combat import legendary_actions as legendary_actions_api

    ally = Character(
        id=str(_uuid.uuid4()),
        user_id=None,
        name="Mara Quickstep",
        race="Human",
        char_class="Rogue",
        level=1,
        background="Scout",
        ability_scores={"str": 10, "dex": 16, "con": 12, "int": 10, "wis": 10, "cha": 10},
        derived={
            "hp_max": 20,
            "ac": 14,
            "proficiency_bonus": 2,
            "attack_bonus": 5,
            "ability_modifiers": {"str": 0, "dex": 3, "con": 1, "int": 0, "wis": 0, "cha": 0},
            "saving_throws": {"dex": 5},
        },
        hp_current=20,
        is_player=False,
        session_id=sample_session.id,
    )
    db_session.add(ally)
    sample_character.hp_current = 20

    state = dict(sample_session.game_state or {})
    state["companion_ids"] = [ally.id]
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "legendary_actions": [{
            "id": "wing",
            "name": "Wing Buffet",
            "cost": 2,
            "target_ids": [sample_character.id, ally.id],
            "target_names": [sample_character.name, ally.name],
            "save": "dex",
            "save_dc": 15,
            "damage_dice": "2d6",
            "damage_type": "bludgeoning",
            "half_on_save": True,
        }],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 2,
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    combat_state.entity_positions = {
        **(combat_state.entity_positions or {}),
        ally.id: {"x": 5, "y": 6},
    }
    flag_modified(sample_session, "game_state")
    flag_modified(combat_state, "entity_positions")

    saves = iter([
        {"ability": "dex", "d20": 5, "modifier": 2, "total": 7, "dc": 15, "success": False},
        {"ability": "dex", "d20": 17, "modifier": 5, "total": 22, "dc": 15, "success": True},
    ])
    monkeypatch.setattr(legendary_actions_api, "roll_saving_throw", lambda *args, **kwargs: next(saves))
    monkeypatch.setattr(legendary_actions_api, "roll_dice", lambda notation: {
        "notation": notation,
        "rolls": [4, 4],
        "bonus": 0,
        "total": 8,
    })
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    end_turn = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_session.player_character_id}"},
    )

    assert end_turn.status_code == 200, end_turn.text
    prompt_action = end_turn.json()["legendary_action_prompt"]["actions"][0]
    assert prompt_action["resolution"] == "save"
    assert prompt_action["target_ids"] == [sample_character.id, ally.id]
    assert prompt_action["target_count"] == 2
    assert prompt_action["target_names"] == [sample_character.name, ally.name]

    use_action = await client.post(
        f"/game/combat/{sample_session.id}/legendary-action",
        headers=headers,
        json={
            "actor_id": "goblin-1",
            "action_id": "wing",
            "target_ids": [sample_character.id, ally.id],
        },
    )

    assert use_action.status_code == 200, use_action.text
    body = use_action.json()
    assert body["resolution"] == "save"
    assert body["target_count"] == 2
    assert body["save_failed_count"] == 1
    assert body["save_succeeded_count"] == 1
    assert body["damage"] == 12
    assert [item["target_id"] for item in body["target_results"]] == [sample_character.id, ally.id]
    assert [item["damage"] for item in body["target_results"]] == [8, 4]
    assert [item["hp_current"] for item in body["target_results"]] == [12, 16]
    assert body["aoe_results"] == body["target_results"]
    assert body["actor_state"]["legendary_action_uses_remaining"] == 0
    assert body["dice_result"]["damage_roll"]["notation"] == "2d6"
    assert body["dice_result"]["target_results"][0]["save"]["success"] is False
    assert body["dice_result"]["target_results"][1]["save"]["success"] is True

    await db_session.refresh(sample_character)
    await db_session.refresh(ally)
    await db_session.refresh(sample_session)
    assert sample_character.hp_current == 12
    assert ally.hp_current == 16
    assert sample_session.game_state["enemies"][0]["legendary_action_uses_remaining"] == 0
    log_result = await db_session.execute(select(GameLog).where(GameLog.session_id == sample_session.id))
    assert any(
        "uses Legendary Action: Wing Buffet" in log.content and "2 targets affected" in log.content
        for log in log_result.scalars()
    )


async def test_legendary_action_area_template_prompt_derives_targets_and_resolves(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import Character, GameLog
    from api.combat import legendary_actions as legendary_actions_api

    ally = Character(
        id=str(_uuid.uuid4()),
        user_id=None,
        name="Mara Quickstep",
        race="Human",
        char_class="Rogue",
        level=1,
        background="Scout",
        ability_scores={"str": 10, "dex": 16, "con": 12, "int": 10, "wis": 10, "cha": 10},
        derived={
            "hp_max": 20,
            "ac": 14,
            "proficiency_bonus": 2,
            "attack_bonus": 5,
            "ability_modifiers": {"str": 0, "dex": 3, "con": 1, "int": 0, "wis": 0, "cha": 0},
            "saving_throws": {"dex": 5},
        },
        hp_current=20,
        is_player=False,
        session_id=sample_session.id,
    )
    db_session.add(ally)
    sample_character.hp_current = 20

    state = dict(sample_session.game_state or {})
    state["companion_ids"] = [ally.id]
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "legendary_actions": [{
            "id": "wing",
            "name": "Wing Buffet",
            "cost": 2,
            "area": "15 ft cone",
            "save": "dex",
            "save_dc": 15,
            "damage_dice": "2d6",
            "damage_type": "bludgeoning",
            "half_on_save": True,
        }],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 2,
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        ally.id: {"x": 5, "y": 6},
        "goblin-1": {"x": 6, "y": 5},
    }
    flag_modified(sample_session, "game_state")
    flag_modified(combat_state, "entity_positions")

    saves = iter([
        {"ability": "dex", "d20": 5, "modifier": 2, "total": 7, "dc": 15, "success": False},
        {"ability": "dex", "d20": 17, "modifier": 5, "total": 22, "dc": 15, "success": True},
    ])
    monkeypatch.setattr(legendary_actions_api, "roll_saving_throw", lambda *args, **kwargs: next(saves))
    monkeypatch.setattr(legendary_actions_api, "roll_dice", lambda notation: {
        "notation": notation,
        "rolls": [4, 4],
        "bonus": 0,
        "total": 8,
    })
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    end_turn = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_session.player_character_id}"},
    )

    assert end_turn.status_code == 200, end_turn.text
    prompt_action = end_turn.json()["legendary_action_prompt"]["actions"][0]
    assert prompt_action["resolution"] == "save"
    assert prompt_action["target_ids"] == [sample_character.id, ally.id]
    assert prompt_action["target_count"] == 2
    assert prompt_action["target_names"] == [sample_character.name, ally.name]
    assert prompt_action["area_template"] == "cone"
    assert prompt_action["area_range_ft"] == 15
    assert prompt_action["area_anchor_id"] == sample_character.id

    use_action = await client.post(
        f"/game/combat/{sample_session.id}/legendary-action",
        headers=headers,
        json={
            "actor_id": "goblin-1",
            "action_id": "wing",
            "target_ids": prompt_action["target_ids"],
        },
    )

    assert use_action.status_code == 200, use_action.text
    body = use_action.json()
    assert body["resolution"] == "save"
    assert body["target_count"] == 2
    assert body["save_failed_count"] == 1
    assert body["save_succeeded_count"] == 1
    assert [item["target_id"] for item in body["target_results"]] == [sample_character.id, ally.id]
    assert [item["damage"] for item in body["target_results"]] == [8, 4]
    assert [item["hp_current"] for item in body["target_results"]] == [12, 16]
    assert body["actor_state"]["legendary_action_uses_remaining"] == 0

    await db_session.refresh(sample_character)
    await db_session.refresh(ally)
    await db_session.refresh(sample_session)
    assert sample_character.hp_current == 12
    assert ally.hp_current == 16
    assert sample_session.game_state["enemies"][0]["legendary_action_uses_remaining"] == 0
    log_result = await db_session.execute(select(GameLog).where(GameLog.session_id == sample_session.id))
    assert any(
        "uses Legendary Action: Wing Buffet" in log.content and "2 targets affected" in log.content
        for log in log_result.scalars()
    )


async def test_lair_action_round_start_prompt_derives_targets_and_resolves_once_per_round(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import Character, GameLog
    from api.combat import legendary_actions as legendary_actions_api

    ally = Character(
        id=str(_uuid.uuid4()),
        user_id=None,
        name="Mara Quickstep",
        race="Human",
        char_class="Rogue",
        level=1,
        background="Scout",
        ability_scores={"str": 10, "dex": 16, "con": 12, "int": 10, "wis": 10, "cha": 10},
        derived={
            "hp_max": 20,
            "ac": 14,
            "proficiency_bonus": 2,
            "attack_bonus": 5,
            "ability_modifiers": {"str": 0, "dex": 3, "con": 1, "int": 0, "wis": 0, "cha": 0},
            "saving_throws": {"dex": 5},
        },
        hp_current=20,
        is_player=False,
        session_id=sample_session.id,
    )
    db_session.add(ally)
    sample_character.hp_current = 20

    state = dict(sample_session.game_state or {})
    state["companion_ids"] = [ally.id]
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "lair_actions": [{
            "id": "seismic-pulse",
            "name": "Seismic Pulse",
            "area": "15 ft radius",
            "targets": "multiple",
            "save": "dex",
            "save_dc": 15,
            "damage_dice": "2d6",
            "damage_type": "bludgeoning",
            "half_on_save": True,
        }],
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    combat_state.turn_order = [
        {"character_id": "goblin-1", "name": "Goblin", "initiative": 12, "is_player": False, "is_enemy": True},
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 8, "is_player": True, "is_enemy": False},
    ]
    combat_state.current_turn_index = 1
    combat_state.round_number = 1
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        ally.id: {"x": 5, "y": 6},
        "goblin-1": {"x": 6, "y": 5},
    }
    flag_modified(sample_session, "game_state")
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")

    saves = iter([
        {"ability": "dex", "d20": 5, "modifier": 2, "total": 7, "dc": 15, "success": False},
        {"ability": "dex", "d20": 17, "modifier": 5, "total": 22, "dc": 15, "success": True},
    ])
    monkeypatch.setattr(legendary_actions_api, "roll_saving_throw", lambda *args, **kwargs: next(saves))
    monkeypatch.setattr(legendary_actions_api, "roll_dice", lambda notation: {
        "notation": notation,
        "rolls": [4, 4],
        "bonus": 0,
        "total": 8,
    })
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    end_turn = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:1:{sample_session.player_character_id}"},
    )

    assert end_turn.status_code == 200, end_turn.text
    turn_body = end_turn.json()
    assert turn_body["round_number"] == 2
    assert turn_body["legendary_action_prompt"] is None
    prompt = turn_body["lair_action_prompt"]
    assert prompt["trigger"] == "lair_action"
    assert prompt["round_number"] == 2
    assert prompt["source_id"] == "goblin-1"
    prompt_action = prompt["actions"][0]
    assert prompt_action["resolution"] == "save"
    assert prompt_action["target_ids"] == [sample_character.id, ally.id]
    assert prompt_action["target_count"] == 2
    assert prompt_action["area_template"] == "radius"
    assert "cost" not in prompt_action
    assert "remaining_after" not in prompt_action

    use_action = await client.post(
        f"/game/combat/{sample_session.id}/lair-action",
        headers=headers,
        json={
            "source_id": "goblin-1",
            "action_id": "seismic-pulse",
            "target_ids": prompt_action["target_ids"],
        },
    )

    assert use_action.status_code == 200, use_action.text
    body = use_action.json()
    assert body["action"] == "lair_action"
    assert body["resolution"] == "save"
    assert body["target_count"] == 2
    assert body["save_failed_count"] == 1
    assert body["save_succeeded_count"] == 1
    assert [item["target_id"] for item in body["target_results"]] == [sample_character.id, ally.id]
    assert [item["damage"] for item in body["target_results"]] == [8, 4]
    assert [item["hp_current"] for item in body["target_results"]] == [12, 16]
    assert body["dice_result"]["type"] == "lair_action"
    assert body["dice_result"]["target_results"][0]["save"]["success"] is False
    assert body["special_action"] == body["dice_result"]

    second_use = await client.post(
        f"/game/combat/{sample_session.id}/lair-action",
        headers=headers,
        json={"source_id": "goblin-1", "action_id": "seismic-pulse", "target_ids": prompt_action["target_ids"]},
    )

    assert second_use.status_code == 400, second_use.text
    await db_session.refresh(sample_character)
    await db_session.refresh(ally)
    await db_session.refresh(sample_session)
    assert sample_character.hp_current == 12
    assert ally.hp_current == 16
    assert sample_session.game_state["lair_action_prompted_round"] == 2
    assert sample_session.game_state["lair_action_used_round"] == 2
    log_result = await db_session.execute(select(GameLog).where(GameLog.session_id == sample_session.id))
    assert any(
        "uses Lair Action: Seismic Pulse" in log.content and "2 targets affected" in log.content
        for log in log_result.scalars()
    )


async def test_lair_action_prompt_triggers_when_advancing_past_initiative_count_20(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from api.combat import legendary_actions as legendary_actions_api

    sample_character.hp_current = 20
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "lair_actions": [{
            "id": "seismic-pulse",
            "name": "Seismic Pulse",
            "area": "15 ft radius",
            "targets": "multiple",
            "save": "dex",
            "save_dc": 15,
            "damage_dice": "2d6",
            "damage_type": "bludgeoning",
            "half_on_save": True,
        }],
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    combat_state.turn_order = [
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 24, "is_player": True, "is_enemy": False},
        {"character_id": "goblin-1", "name": "Goblin", "initiative": 18, "is_player": False, "is_enemy": True},
    ]
    combat_state.current_turn_index = 0
    combat_state.round_number = 1
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        "goblin-1": {"x": 6, "y": 5},
    }
    flag_modified(sample_session, "game_state")
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")

    monkeypatch.setattr(legendary_actions_api, "roll_saving_throw", lambda *args, **kwargs: {
        "ability": "dex",
        "d20": 5,
        "modifier": 2,
        "total": 7,
        "dc": 15,
        "success": False,
    })
    monkeypatch.setattr(legendary_actions_api, "roll_dice", lambda notation: {
        "notation": notation,
        "rolls": [3, 3],
        "bonus": 0,
        "total": 6,
    })
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    end_turn = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_session.player_character_id}"},
    )

    assert end_turn.status_code == 200, end_turn.text
    turn_body = end_turn.json()
    assert turn_body["round_number"] == 1
    assert turn_body["next_turn_index"] == 1
    prompt = turn_body["lair_action_prompt"]
    assert prompt["timing"] == "initiative_count_20"
    assert prompt["round_number"] == 1
    assert "initiative count 20" in prompt["context"]
    prompt_action = prompt["actions"][0]
    assert prompt_action["target_ids"] == [sample_character.id]
    assert prompt_action["area_template"] == "radius"

    use_action = await client.post(
        f"/game/combat/{sample_session.id}/lair-action",
        headers=headers,
        json={
            "source_id": "goblin-1",
            "action_id": "seismic-pulse",
            "target_ids": prompt_action["target_ids"],
        },
    )

    assert use_action.status_code == 200, use_action.text
    body = use_action.json()
    assert body["action"] == "lair_action"
    assert body["round_number"] == 1
    assert body["target_new_hp"] == 14
    assert body["special_action"] == body["dice_result"]

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    assert sample_character.hp_current == 14
    assert sample_session.game_state["lair_action_prompted_round"] == 1
    assert sample_session.game_state["lair_action_used_round"] == 1


async def test_ai_turn_surfaces_lair_action_prompt_when_advancing_past_initiative_count_20(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent

    enemy_id = "orc-1"
    sample_character.hp_current = 20
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "lair_actions": [{
            "id": "seismic-pulse",
            "name": "Seismic Pulse",
            "area": "15 ft radius",
            "targets": "multiple",
            "save": "dex",
            "save_dc": 15,
            "damage_dice": "2d6",
            "damage_type": "bludgeoning",
            "half_on_save": True,
        }],
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    ai_turn_combat.turn_order = [
        {"character_id": enemy_id, "name": "Orc Lair Keeper", "initiative": 24, "is_player": False, "is_enemy": True},
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 18, "is_player": True, "is_enemy": False},
    ]
    ai_turn_combat.current_turn_index = 0
    ai_turn_combat.round_number = 1
    ai_turn_combat.entity_positions = {
        enemy_id: {"x": 6, "y": 5},
        sample_character.id: {"x": 5, "y": 5},
    }
    flag_modified(sample_session, "game_state")
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")

    async def fake_get_ai_decision(**_kwargs):
        return {
            "action_type": "dodge",
            "target_id": sample_character.id,
            "reason": "test lair timing",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/ai-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{enemy_id}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["next_turn_index"] == 1
    assert body["round_number"] == 1
    prompt = body["lair_action_prompt"]
    assert prompt["trigger"] == "lair_action"
    assert prompt["timing"] == "initiative_count_20"
    assert prompt["round_number"] == 1
    assert "initiative count 20" in prompt["context"]
    prompt_action = prompt["actions"][0]
    assert prompt_action["id"] == "seismic-pulse"
    assert prompt_action["target_ids"] == [sample_character.id]
    assert prompt_action["area_template"] == "radius"

    await db_session.refresh(sample_session)
    await db_session.refresh(ai_turn_combat)
    assert sample_session.game_state["lair_action_prompted_round"] == 1
    assert ai_turn_combat.current_turn_index == 1


async def test_ai_turn_surfaces_legendary_action_prompt_after_ai_turn(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent

    acting_enemy_id = "orc-1"
    legendary_enemy_id = "dragon-1"
    sample_character.hp_current = 20
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies.append({
        "id": legendary_enemy_id,
        "name": "Watching Dragon",
        "hp_current": 80,
        "max_hp": 80,
        "derived": {"hp_max": 80, "ac": 18, "ability_modifiers": {"str": 6, "dex": 0}},
        "legendary_actions": [
            {"id": "tail", "name": "Tail Attack", "cost": 1, "description": "Tail sweep."},
        ],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 2,
        "identified": True,
    })
    state["enemies"] = enemies
    sample_session.game_state = state
    ai_turn_combat.turn_order = [
        {"character_id": acting_enemy_id, "name": "Orc Caller", "initiative": 18, "is_player": False, "is_enemy": True},
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 12, "is_player": True, "is_enemy": False},
        {"character_id": legendary_enemy_id, "name": "Watching Dragon", "initiative": 10, "is_player": False, "is_enemy": True},
    ]
    ai_turn_combat.current_turn_index = 0
    ai_turn_combat.round_number = 1
    ai_turn_combat.entity_positions = {
        acting_enemy_id: {"x": 6, "y": 5},
        sample_character.id: {"x": 5, "y": 5},
        legendary_enemy_id: {"x": 7, "y": 5},
    }
    flag_modified(sample_session, "game_state")
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")

    async def fake_get_ai_decision(**_kwargs):
        return {
            "action_type": "dodge",
            "target_id": sample_character.id,
            "reason": "test legendary timing",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/ai-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{acting_enemy_id}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["next_turn_index"] == 1
    assert body["round_number"] == 1
    assert body["lair_action_prompt"] is None
    prompt = body["legendary_action_prompt"]
    assert prompt["trigger"] == "legendary_action"
    assert prompt["trigger_entity_id"] == acting_enemy_id
    assert prompt["actor_id"] == legendary_enemy_id
    assert prompt["remaining"] == 2
    assert [action["id"] for action in prompt["actions"]] == ["tail"]


async def test_predict_ranged_attack_adjacent_enemy_surfaces_close_penalty(
    client, sample_session, combat_state, sample_user, sample_character,
):
    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/predict",
        headers=headers,
        json={
            "attacker_id": sample_character.id,
            "target_id": "goblin-1",
            "action_key": "atk",
            "is_ranged": True,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["advantage"] is False
    assert data["disadvantage"] is True
    assert data["disadvantage_sources"] == ["attacker ranged close"]
    assert "劣势" in data["modifiers"]


async def test_predict_ranged_attack_adjacent_enemy_respects_crossbow_expert(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    sample_character.derived = {
        **(sample_character.derived or {}),
        "ranged_attack_bonus": 5,
        "feat_effects": {
            "Crossbow Expert": {"crossbow_expert": True},
        },
    }
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/predict",
        headers=headers,
        json={
            "attacker_id": sample_character.id,
            "target_id": "goblin-1",
            "action_key": "atk",
            "is_ranged": True,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["advantage"] is False
    assert data["disadvantage"] is False
    assert "attacker ranged close" not in data["disadvantage_sources"]
    assert "劣势" not in data["modifiers"]


async def test_inspect_enemy_reveals_stats_and_spends_action(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from api.combat._shared import _build_combat_snapshot
    from sqlalchemy.orm.attributes import flag_modified

    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "legendary_actions": [
            {"name": "Tail Attack", "cost": 1},
            {"name": "Wing Buffet", "cost": 2},
        ],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 2,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/inspect",
        headers=headers,
        json={
            "character_id": sample_character.id,
            "target_id": "goblin-1",
            "skill": "investigation",
            "d20_value": 13,
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["success"] is True
    assert data["turn_state"]["action_used"] is True
    assert "actions" in data["revealed_stats"]
    assert data["inspect_result"]["type"] == "enemy_inspect"
    assert data["inspect_result"]["actor_id"] == sample_character.id
    assert data["inspect_result"]["target_id"] == "goblin-1"
    assert data["inspect_result"]["skill"] == "investigation"
    assert data["inspect_result"]["dc"] == data["dc"]
    assert data["inspect_result"]["check"] == data["check"]
    assert "actions" in data["inspect_result"]["revealed_stats"]
    assert data["dice_result"] == data["inspect_result"]
    assert data["special_action"] == data["inspect_result"]
    assert data["enemy"]["actions"] == [{"name": "Scimitar"}]
    assert data["inspect_result"]["enemy"]["actions"] == [{"name": "Scimitar"}]
    assert data["enemy"]["legendary_actions"] == [
        {"name": "Tail Attack", "cost": 1},
        {"name": "Wing Buffet", "cost": 2},
    ]
    assert data["enemy"]["resistances"] == ["poison"]
    assert "tactics" not in data["enemy"]

    await db_session.refresh(sample_session)
    enemy = sample_session.game_state["enemies"][0]
    assert "revealed_stats" not in enemy
    assert "actions" in enemy["knowledge_state"]["by_character"][sample_character.id]["revealed_stats"]
    assert enemy["knowledge_state"]["by_character"][sample_character.id]["last_inspect"]["character_id"] == sample_character.id

    public_snapshot = await _build_combat_snapshot(db_session, sample_session, combat_state)
    assert "actions" not in public_snapshot["entities"]["goblin-1"]
    assert public_snapshot["entities"]["goblin-1"]["legendary_action_uses"] == 3
    assert public_snapshot["entities"]["goblin-1"]["legendary_action_uses_remaining"] == 2
    assert "legendary_actions" not in public_snapshot["entities"]["goblin-1"]
    private_snapshot = await _build_combat_snapshot(
        db_session,
        sample_session,
        combat_state,
        viewer_character_id=sample_character.id,
    )
    assert private_snapshot["entities"]["goblin-1"]["actions"] == [{"name": "Scimitar"}]
    assert private_snapshot["entities"]["goblin-1"]["legendary_actions"] == [
        {"name": "Tail Attack", "cost": 1},
        {"name": "Wing Buffet", "cost": 2},
    ]

    followup = await client.get(f"/game/combat/{sample_session.id}", headers=headers)
    assert followup.status_code == 200, followup.text
    entity = followup.json()["entities"]["goblin-1"]
    assert entity["actions"] == [{"name": "Scimitar"}]
    assert entity["legendary_actions"] == [
        {"name": "Tail Attack", "cost": 1},
        {"name": "Wing Buffet", "cost": 2},
    ]
    assert entity["condition_immunities"] == ["poisoned"]


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


async def test_lay_on_hands_cure_poison_class_feature_updates_state(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from api.combat import class_features

    async def fake_narrate_action(**_kwargs):
        return ""

    monkeypatch.setattr(class_features, "narrate_action", fake_narrate_action)
    sample_character.char_class = "Paladin"
    sample_character.level = 3
    sample_character.hp_current = 12
    sample_character.derived = {"hp_max": 24}
    sample_character.class_resources = {"lay_on_hands_remaining": 15}
    sample_character.conditions = ["poisoned", "prone"]
    sample_character.condition_durations = {"poisoned": 3, "prone": 1}
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/class-feature",
        headers=headers,
        json={"feature_name": "lay_on_hands_cure_poison"},
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["feature"] == "lay_on_hands_cure_poison"
    assert data["class_resources"]["lay_on_hands_remaining"] == 10
    assert data["turn_state"]["action_used"] is True
    assert data["hp_current"] == 12
    assert data["target_state"]["target_id"] == sample_character.id
    assert data["target_state"]["conditions"] == ["prone"]
    assert data["target_state"]["condition_durations"] == {"prone": 1}

    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    assert sample_character.class_resources["lay_on_hands_remaining"] == 10
    assert sample_character.conditions == ["prone"]
    assert sample_character.condition_durations == {"prone": 1}
    assert combat_state.turn_states[sample_character.id]["action_used"] is True


async def test_lay_on_hands_cure_disease_class_feature_updates_state(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from api.combat import class_features

    async def fake_narrate_action(**_kwargs):
        return ""

    monkeypatch.setattr(class_features, "narrate_action", fake_narrate_action)
    sample_character.char_class = "Paladin"
    sample_character.level = 3
    sample_character.hp_current = 12
    sample_character.derived = {"hp_max": 24}
    sample_character.class_resources = {"lay_on_hands_remaining": 15}
    sample_character.conditions = ["disease", "prone"]
    sample_character.condition_durations = {"disease": 3, "prone": 1}
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/class-feature",
        headers=headers,
        json={"feature_name": "lay_on_hands_cure_disease"},
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["feature"] == "lay_on_hands_cure_disease"
    assert data["class_resources"]["lay_on_hands_remaining"] == 10
    assert data["turn_state"]["action_used"] is True
    assert data["hp_current"] == 12
    assert data["target_state"]["target_id"] == sample_character.id
    assert data["target_state"]["conditions"] == ["prone"]
    assert data["target_state"]["condition_durations"] == {"prone": 1}

    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    assert sample_character.class_resources["lay_on_hands_remaining"] == 10
    assert sample_character.conditions == ["prone"]
    assert sample_character.condition_durations == {"prone": 1}
    assert combat_state.turn_states[sample_character.id]["action_used"] is True


async def test_patient_defense_class_feature_spends_ki_and_sets_dodging(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from api.combat import class_features

    async def fake_narrate_action(**_kwargs):
        return ""

    monkeypatch.setattr(class_features, "narrate_action", fake_narrate_action)
    sample_character.char_class = "Monk"
    sample_character.level = 3
    sample_character.class_resources = {"ki_remaining": 2}
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/class-feature",
        headers=headers,
        json={"feature_name": "ki_patient_defense"},
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["feature"] == "ki_patient_defense"
    assert data["class_resources"]["ki_remaining"] == 1
    assert data["turn_state"]["bonus_action_used"] is True
    assert data["turn_state"]["dodging"] is True
    assert data["target_state"]["target_id"] == sample_character.id
    assert data["target_state"]["class_resources"]["ki_remaining"] == 1
    assert data["actor_state"] == data["target_state"]
    assert data["dice_result"]["type"] == "class_feature"
    assert data["dice_result"]["feature"] == "ki_patient_defense"
    assert data["dice_result"]["target_state"] == data["target_state"]
    assert data["dice_result"]["turn_state"] == data["turn_state"]
    assert data["special_action"] == data["dice_result"]

    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    assert sample_character.class_resources["ki_remaining"] == 1
    assert combat_state.turn_states[sample_character.id]["bonus_action_used"] is True
    assert combat_state.turn_states[sample_character.id]["dodging"] is True


async def test_step_of_the_wind_dash_class_feature_spends_ki_and_extends_movement(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from api.combat import class_features

    async def fake_narrate_action(**_kwargs):
        return ""

    monkeypatch.setattr(class_features, "narrate_action", fake_narrate_action)
    sample_character.char_class = "Monk"
    sample_character.level = 3
    sample_character.class_resources = {"ki_remaining": 2}
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 6,
            "movement_max": 6,
            "base_movement_max": 6,
        },
    }
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/class-feature",
        headers=headers,
        json={"feature_name": "ki_step_of_the_wind_dash"},
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["feature"] == "ki_step_of_the_wind_dash"
    assert data["class_resources"]["ki_remaining"] == 1
    assert data["turn_state"]["bonus_action_used"] is True
    assert data["turn_state"]["movement_used"] == 6
    assert data["turn_state"]["movement_max"] == 12
    assert data["target_state"]["class_resources"]["ki_remaining"] == 1

    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    assert sample_character.class_resources["ki_remaining"] == 1
    assert combat_state.turn_states[sample_character.id]["bonus_action_used"] is True
    assert combat_state.turn_states[sample_character.id]["movement_used"] == 6
    assert combat_state.turn_states[sample_character.id]["movement_max"] == 12


async def test_martial_arts_attack_roll_uses_bonus_action_and_monk_die(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    sample_character.char_class = "Monk"
    sample_character.level = 5
    sample_character.equipment = {
        "weapons": [{
            "name": "Quarterstaff",
            "damage": "1d6",
            "type": "simple_melee",
            "properties": ["versatile(1d8)"],
            "equipped": True,
        }],
        "shield": {"name": "Shield", "equipped": False},
    }
    sample_character.derived = {
        **(sample_character.derived or {}),
        "attack_bonus": 6,
        "ability_modifiers": {"str": 1, "dex": 4},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": True,
            "bonus_action_used": False,
            "reaction_used": False,
            "attacks_made": 1,
            "attacks_max": 1,
        },
    }
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "target_id": "goblin-1",
            "action_type": "martial_arts",
            "d20_value": 15,
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["attack_bonus"] == 7
    assert data["damage_dice"] == "1d6+4"
    assert data["turn_state"]["bonus_action_used"] is True
    assert data["turn_state"]["attacks_made"] == 1
    assert data["turn_state"]["action_used"] is True
    assert data["turn_state"]["pending_attack"]["is_martial_arts"] is True
    assert data["turn_state"]["pending_attack"]["hit_die"] == 6
    assert data["turn_state"]["pending_attack"]["dmg_mod"] == 4
    assert data["turn_state"]["pending_attack"]["damage_type"] == "bludgeoning"
    assert "weapon_resource" not in data["turn_state"]["pending_attack"]
    assert data.get("weapon_resource") is None

    await db_session.refresh(combat_state)
    pending = combat_state.turn_states[sample_character.id]["pending_attack"]
    assert pending["is_martial_arts"] is True
    assert pending["damage_type"] == "bludgeoning"
    assert "weapon_resource" not in pending


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


async def test_delay_turn_moves_current_player_to_round_end(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/delay-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_character.id}"},
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["turn_order_delayed"] is True
    assert data["delayed_turn"]["actor_id"] == sample_character.id
    assert data["delayed_turn"]["from_index"] == 0
    assert data["delayed_turn"]["to_index"] == 1
    assert data["next_turn_index"] == 0
    assert data["round_number"] == 1

    await db_session.refresh(combat_state)
    assert combat_state.current_turn_index == 0
    assert combat_state.round_number == 1
    assert [entry["character_id"] for entry in combat_state.turn_order] == [
        "goblin-1",
        sample_character.id,
    ]


async def test_delay_turn_triggers_lair_action_prompt_when_crossing_initiative_count_20(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    sample_character.hp_current = 20
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "lair_actions": [{
            "id": "seismic-pulse",
            "name": "Seismic Pulse",
            "area": "15 ft radius",
            "targets": "multiple",
            "save": "dex",
            "save_dc": 15,
            "damage_dice": "2d6",
            "damage_type": "bludgeoning",
            "half_on_save": True,
        }],
        "identified": True,
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    combat_state.turn_order = [
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 24, "is_player": True, "is_enemy": False},
        {"character_id": "goblin-1", "name": "Goblin", "initiative": 18, "is_player": False, "is_enemy": True},
    ]
    combat_state.current_turn_index = 0
    combat_state.round_number = 1
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        "goblin-1": {"x": 6, "y": 5},
    }
    flag_modified(sample_session, "game_state")
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/delay-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_character.id}"},
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["turn_order_delayed"] is True
    assert data["next_turn_index"] == 0
    assert data["round_number"] == 1
    assert data["legendary_action_prompt"] is None
    prompt = data["lair_action_prompt"]
    assert prompt["timing"] == "initiative_count_20"
    assert prompt["round_number"] == 1
    assert "initiative count 20" in prompt["context"]
    prompt_action = prompt["actions"][0]
    assert prompt_action["target_ids"] == [sample_character.id]
    assert prompt_action["area_template"] == "radius"

    await db_session.refresh(combat_state)
    await db_session.refresh(sample_session)
    assert combat_state.current_turn_index == 0
    assert combat_state.round_number == 1
    assert [entry["character_id"] for entry in combat_state.turn_order] == [
        "goblin-1",
        sample_character.id,
    ]
    assert sample_session.game_state["lair_action_prompted_round"] == 1


async def test_delay_turn_moves_current_player_after_requested_later_combatant(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    state = dict(sample_session.game_state or {})
    first_enemy = dict((state.get("enemies") or [])[0])
    state["enemies"] = [
        {**first_enemy, "id": "goblin-1", "name": "Goblin Guard"},
        {**first_enemy, "id": "goblin-2", "name": "Goblin Archer"},
    ]
    sample_session.game_state = state
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        "goblin-1": {"x": 6, "y": 5},
        "goblin-2": {"x": 8, "y": 5},
    }
    combat_state.turn_order = [
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 18, "is_player": True, "is_enemy": False},
        {"character_id": "goblin-1", "name": "Goblin Guard", "initiative": 12, "is_player": False, "is_enemy": True},
        {"character_id": "goblin-2", "name": "Goblin Archer", "initiative": 10, "is_player": False, "is_enemy": True},
    ]
    flag_modified(sample_session, "game_state")
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_order")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/delay-turn",
        headers=headers,
        json={
            "expected_turn_token": f"1:0:{sample_character.id}",
            "after_entity_id": "goblin-1",
        },
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["turn_order_delayed"] is True
    assert data["delayed_turn"]["actor_id"] == sample_character.id
    assert data["delayed_turn"]["after_entity_id"] == "goblin-1"
    assert data["delayed_turn"]["after_entity_name"] == "Goblin Guard"
    assert data["delayed_turn"]["placement"] == "after_target"
    assert data["delayed_turn"]["reason"] == "delayed_after_target"
    assert data["delayed_turn"]["from_index"] == 0
    assert data["delayed_turn"]["to_index"] == 1
    assert data["next_turn_index"] == 0
    assert data["round_number"] == 1

    await db_session.refresh(combat_state)
    assert combat_state.current_turn_index == 0
    assert combat_state.round_number == 1
    assert [entry["character_id"] for entry in combat_state.turn_order] == [
        "goblin-1",
        sample_character.id,
        "goblin-2",
    ]


async def test_delay_turn_rejects_target_that_already_acted_this_round(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    combat_state.current_turn_index = 1
    combat_state.turn_order = [
        {"character_id": "goblin-1", "name": "Goblin Guard", "initiative": 18, "is_player": False, "is_enemy": True},
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 12, "is_player": True, "is_enemy": False},
        {"character_id": "goblin-2", "name": "Goblin Archer", "initiative": 10, "is_player": False, "is_enemy": True},
    ]
    flag_modified(combat_state, "turn_order")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/delay-turn",
        headers=headers,
        json={
            "expected_turn_token": f"1:1:{sample_character.id}",
            "after_entity_id": "goblin-1",
        },
    )

    assert r.status_code == 400, r.text
    assert "already acted" in r.text
    await db_session.refresh(combat_state)
    assert combat_state.current_turn_index == 1
    assert [entry["character_id"] for entry in combat_state.turn_order] == [
        "goblin-1",
        sample_character.id,
        "goblin-2",
    ]


async def test_delay_turn_rejects_after_actor_spent_turn_resources(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    combat_state.turn_states = {
        sample_character.id: {
            "action_used": True,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 2,
            "movement_max": 6,
            "attacks_made": 1,
        },
    }
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/delay-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_character.id}"},
    )

    assert r.status_code == 400, r.text
    assert "action economy" in r.text
    await db_session.refresh(combat_state)
    assert combat_state.current_turn_index == 0
    assert [entry["character_id"] for entry in combat_state.turn_order] == [
        sample_character.id,
        "goblin-1",
    ]


async def test_delay_turn_rejects_incapacitated_player_actor(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    sample_character.conditions = ["stunned"]
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/delay-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_character.id}"},
    )

    assert r.status_code == 400, r.text
    assert "Cannot delay while incapacitated" in r.text
    assert "stunned" in r.text
    await db_session.refresh(combat_state)
    assert combat_state.current_turn_index == 0
    assert [entry["character_id"] for entry in combat_state.turn_order] == [
        sample_character.id,
        "goblin-1",
    ]


async def test_delay_turn_rejects_stale_expected_turn_token(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/delay-turn",
        headers=headers,
        json={"expected_turn_token": "1:0:not-the-current-actor"},
    )

    assert r.status_code == 409, r.text
    assert "stale" in r.text
    await db_session.refresh(combat_state)
    assert combat_state.current_turn_index == 0
    assert [entry["character_id"] for entry in combat_state.turn_order] == [
        sample_character.id,
        "goblin-1",
    ]


async def test_delay_turn_allows_ai_driver_to_delay_enemy_turn(
    client, db_session, sample_session, ai_turn_combat, sample_user, sample_character,
):
    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/delay-turn",
        headers=headers,
        json={"expected_turn_token": "1:0:orc-1"},
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["turn_order_delayed"] is True
    assert data["delayed_turn"]["actor_id"] == "orc-1"
    assert data["delayed_turn"]["from_index"] == 0
    assert data["delayed_turn"]["to_index"] == 1
    assert data["next_turn_index"] == 0
    assert data["round_number"] == 1

    await db_session.refresh(ai_turn_combat)
    assert ai_turn_combat.current_turn_index == 0
    assert ai_turn_combat.round_number == 1
    assert [entry["character_id"] for entry in ai_turn_combat.turn_order] == [
        sample_character.id,
        "orc-1",
    ]


async def test_delay_turn_rejects_incapacitated_enemy_actor(
    client, db_session, sample_session, ai_turn_combat, sample_user,
):
    from sqlalchemy.orm.attributes import flag_modified

    enemy = sample_session.game_state["enemies"][0]
    enemy["conditions"] = ["stunned"]
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    r = await client.post(
        f"/game/combat/{sample_session.id}/delay-turn",
        headers=headers,
        json={"expected_turn_token": "1:0:orc-1"},
    )

    assert r.status_code == 400, r.text
    assert "Cannot delay while incapacitated" in r.text
    assert "stunned" in r.text
    await db_session.refresh(ai_turn_combat)
    assert ai_turn_combat.current_turn_index == 0
    assert [entry["character_id"] for entry in ai_turn_combat.turn_order] == [
        "orc-1",
        sample_session.player_character_id,
    ]


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


async def test_combat_move_triggers_hazard_damage(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from services import combat_hazard_service

    monkeypatch.setattr(
        combat_hazard_service,
        "roll_dice",
        lambda expr: {"notation": expr, "rolls": [4], "bonus": 0, "total": 4},
    )
    hp_before = sample_character.hp_current
    combat_state.grid_data = {
        "_encounter_template": {"hazards": ["sparking conduit"]},
        "4_5": "hazard",
    }
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        "goblin-1": {"x": 10, "y": 10},
    }
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={"entity_id": sample_character.id, "to_x": 4, "to_y": 5},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    hazard = data["hazard_result"]
    assert hazard["triggered"] is True
    assert hazard["cell"] == "4_5"
    assert hazard["damage"] == 4
    assert hazard["damage_type"] == "lightning"
    assert data["combat"]["entities"][sample_character.id]["hp_current"] == hp_before - 4
    assert data["entity_positions"][sample_character.id] == {"x": 4, "y": 5}

    await db_session.refresh(sample_character)
    assert sample_character.hp_current == hp_before - 4


async def test_end_turn_triggers_hazard_for_next_actor(
    client, db_session, sample_session, combat_state, sample_user, monkeypatch,
):
    from services import combat_hazard_service

    monkeypatch.setattr(
        combat_hazard_service,
        "roll_dice",
        lambda expr: {"notation": expr, "rolls": [3], "bonus": 0, "total": 3},
    )
    combat_state.grid_data = {
        "_encounter_template": {"hazards": ["sparking conduit"]},
        "6_5": "hazard",
    }
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/end-turn", headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["next_turn_index"] == 1
    assert data["turn_start_hazard"]["trigger"] == "turn_start"
    assert data["turn_start_hazard"]["target_id"] == "goblin-1"
    assert data["turn_start_hazard"]["damage"] == 3
    assert "taking 3 lightning damage" in data["turn_start_hazard_log"]

    await db_session.refresh(sample_session)
    assert sample_session.game_state["enemies"][0]["hp_current"] == 4


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


async def test_ai_turn_returns_turn_start_hazard_log_for_player_next_turn(
    client, db_session, sample_session, ai_turn_combat, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent
    from services import combat_hazard_service

    hazard = {
        "name": "Sparking Conduit",
        "label": "Sparking Conduit",
        "damage_dice": "2d6",
        "damage_type": "lightning",
        "save_dc": 99,
        "save_ability": "dex",
        "half_on_save": True,
        "cells": ["5_5"],
    }
    sample_character.hp_current = 20
    ai_turn_combat.grid_data = {
        "_encounter_template": {"hazards": [hazard]},
        "5_5": {"terrain": "hazard", **hazard},
    }
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        "orc-1": {"x": 6, "y": 5},
    }
    flag_modified(ai_turn_combat, "grid_data")
    flag_modified(ai_turn_combat, "entity_positions")

    monkeypatch.setattr(
        combat_hazard_service,
        "roll_dice",
        lambda expr: {"notation": expr, "rolls": [3, 3], "bonus": 0, "total": 6},
    )
    monkeypatch.setattr(
        combat_hazard_service,
        "roll_saving_throw",
        lambda _target, ability, dc: {
            "ability": ability,
            "d20": 1,
            "modifier": 0,
            "total": 1,
            "dc": dc,
            "success": False,
        },
    )

    async def fake_get_ai_decision(**_kwargs):
        return {
            "action_type": "dodge",
            "target_id": sample_character.id,
            "reason": "test player turn-start hazard",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["next_turn_index"] == 1
    assert data["turn_start_hazard"]["trigger"] == "turn_start"
    assert data["turn_start_hazard"]["target_id"] == sample_character.id
    assert data["turn_start_hazard"]["target_type"] == "character"
    assert data["turn_start_hazard"]["damage"] == 6
    assert "Smoke Sentinel" in data["turn_start_hazard_log"] or sample_character.name in data["turn_start_hazard_log"]
    assert "Sparking Conduit" in data["turn_start_hazard_log"]
    assert "taking 6 lightning damage" in data["turn_start_hazard_log"]

    await db_session.refresh(sample_character)
    assert sample_character.hp_current == 14


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


async def test_ai_turn_recharge_special_action_pushes_failed_save_target(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_special as ai_turn_special

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["recharge_abilities"] = [{
        "id": "thunder-breath",
        "name": "Thunder Breath",
        "threshold": 5,
        "available": True,
        "damage_dice": "2d6",
        "damage_type": "thunder",
        "save": "str",
        "save_dc": 13,
        "half_on_save": True,
        "push_distance_ft": 10,
    }]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.hp_current = 30
    sample_character.derived = {
        **(sample_character.derived or {}),
        "hp_max": 30,
        "ability_modifiers": {"str": 0},
        "saving_throws": {"str": 0},
    }
    ai_turn_combat.entity_positions = {
        enemy["id"]: {"x": 0, "y": 0},
        sample_character.id: {"x": 2, "y": 0},
    }
    flag_modified(ai_turn_combat, "entity_positions")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "special",
            "target_id": sample_character.id,
            "action_name": "Thunder Breath",
            "reason": "test thunder push",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(
        ai_turn_special,
        "roll_dice",
        lambda expr: {"notation": expr, "rolls": [4, 4], "total": 8},
    )
    monkeypatch.setattr(
        ai_turn_special,
        "roll_saving_throw",
        lambda *_args, **_kwargs: {"ability": "str", "dc": 13, "total": 9, "success": False},
    )

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["special_action"]["push_distance_ft"] == 10
    assert body["target_results"][0]["forced_movement"] == {
        "type": "push",
        "applied": True,
        "target_id": sample_character.id,
        "target_name": sample_character.name,
        "distance_ft": 10,
        "requested_distance_ft": 10,
        "steps": 2,
        "from": {"x": 2, "y": 0},
        "to": {"x": 4, "y": 0},
    }
    assert body["entity_positions"][sample_character.id] == {"x": 4, "y": 0}
    await db_session.refresh(ai_turn_combat)
    assert ai_turn_combat.entity_positions[sample_character.id] == {"x": 4, "y": 0}


async def test_ai_turn_recharge_special_action_pulls_failed_save_target(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_special as ai_turn_special

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["recharge_abilities"] = [{
        "id": "gravity-breath",
        "name": "Gravity Breath",
        "threshold": 5,
        "available": True,
        "damage_dice": "2d6",
        "damage_type": "force",
        "save": "str",
        "save_dc": 13,
        "half_on_save": True,
        "pull_distance_ft": 5,
    }]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.hp_current = 30
    sample_character.derived = {
        **(sample_character.derived or {}),
        "hp_max": 30,
        "ability_modifiers": {"str": 0},
        "saving_throws": {"str": 0},
    }
    ai_turn_combat.entity_positions = {
        enemy["id"]: {"x": 8, "y": 5},
        sample_character.id: {"x": 6, "y": 5},
    }
    flag_modified(ai_turn_combat, "entity_positions")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "special",
            "target_id": sample_character.id,
            "action_name": "Gravity Breath",
            "reason": "test gravity pull",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(
        ai_turn_special,
        "roll_dice",
        lambda expr: {"notation": expr, "rolls": [4, 4], "total": 8},
    )
    monkeypatch.setattr(
        ai_turn_special,
        "roll_saving_throw",
        lambda *_args, **_kwargs: {"ability": "str", "dc": 13, "total": 9, "success": False},
    )

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["special_action"]["pull_distance_ft"] == 5
    assert body["target_results"][0]["forced_movement"] == {
        "type": "pull",
        "applied": True,
        "target_id": sample_character.id,
        "target_name": sample_character.name,
        "distance_ft": 5,
        "requested_distance_ft": 5,
        "steps": 1,
        "from": {"x": 6, "y": 5},
        "to": {"x": 7, "y": 5},
    }
    assert body["entity_positions"][sample_character.id] == {"x": 7, "y": 5}
    await db_session.refresh(ai_turn_combat)
    assert ai_turn_combat.entity_positions[sample_character.id] == {"x": 7, "y": 5}


async def test_ai_recharge_condition_breaking_concentration_returns_tracked_effect_updates(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_concentration_effect_service import track_concentration_condition
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_special as ai_turn_special

    state = sample_session.game_state or {}
    attacker = state["enemies"][0]
    attacker["name"] = "Stun Channeler"
    attacker["recharge_abilities"] = [{
        "id": "psychic-stun",
        "name": "Psychic Stun",
        "threshold": 5,
        "available": True,
        "damage_dice": "2d6",
        "damage_type": "psychic",
        "save": "int",
        "save_dc": 15,
        "half_on_save": False,
        "condition_on_failed_save": "stunned",
        "condition_duration_rounds": 1,
    }]
    webbed_enemy = {
        "id": "webbed-goblin",
        "name": "Webbed Goblin",
        "hp_current": 7,
        "max_hp": 7,
        "conditions": ["restrained"],
        "condition_durations": {"restrained": 600},
        "derived": {"hp_max": 7, "ac": 12},
    }
    track_concentration_condition(
        webbed_enemy,
        "restrained",
        caster_id=sample_character.id,
        spell_name="Web",
        condition_preexisting=False,
    )
    state["enemies"] = [attacker, webbed_enemy]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.hp_current = 30
    sample_character.concentration = "Web"
    sample_character.conditions = []
    sample_character.condition_durations = {}
    sample_character.derived = {
        **(sample_character.derived or {}),
        "hp_max": 30,
        "ability_modifiers": {"int": 0},
        "saving_throws": {"int": 0},
    }
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "special",
            "target_id": sample_character.id,
            "action_name": "Psychic Stun",
            "reason": "test stun concentration cleanup",
        }

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(
        ai_turn_special,
        "roll_dice",
        lambda expr: {"notation": expr, "rolls": [4, 4], "total": 8},
    )
    monkeypatch.setattr(
        ai_turn_special,
        "roll_saving_throw",
        lambda *_args, **_kwargs: {"ability": "int", "dc": 15, "total": 8, "success": False},
    )

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["special_action"]["name"] == "Psychic Stun"
    assert body["special_action"]["condition_on_failed_save"] == "stunned"
    assert body["special_action"]["condition_duration_rounds"] == 1
    assert body["concentration_check"]["broke"] is True
    assert body["concentration_check"]["automatic"] is True
    assert body["concentration_check"]["spell_name"] == "Web"
    assert body["target_state"]["conditions"] == ["stunned"]
    assert body["target_state"]["concentration"] is None
    assert body["target_state"]["concentration_effect_updates"] == [{
        "target_id": "webbed-goblin",
        "target_name": "Webbed Goblin",
        "is_enemy": True,
        "removed_conditions": ["restrained"],
        "conditions": [],
        "condition_durations": {},
    }]
    assert body["target_results"][0]["concentration_check"]["broke"] is True
    assert body["target_results"][0]["concentration_effect_updates"] == body["target_state"]["concentration_effect_updates"]

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    assert sample_character.concentration is None
    assert sample_character.conditions == ["stunned"]
    cleaned = next(enemy for enemy in sample_session.game_state["enemies"] if enemy["id"] == "webbed-goblin")
    assert cleaned["conditions"] == []
    assert cleaned["condition_durations"] == {}


async def test_ai_skirmisher_repositions_after_ranged_attack(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_grid_service import chebyshev_distance
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["name"] = "Knife Dancer"
    enemy["tactical_role"] = "skirmisher"
    enemy["actions"] = [{"name": "Throwing Knife", "type": "ranged_attack", "damage_dice": "1d4", "attack_bonus": 5}]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    ai_turn_combat.entity_positions = {
        enemy["id"]: {"x": 5, "y": 2},
        sample_character.id: {"x": 5, "y": 5},
    }
    flag_modified(ai_turn_combat, "entity_positions")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "action_name": "Throwing Knife",
            "reason": "test skirmisher reposition",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": False,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 11,
                "target_ac": 14,
            },
            damage=0,
            damage_roll={"formula": "1d4", "rolls": [], "total": 0},
            narration="miss",
        )

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    old_distance = chebyshev_distance({"x": 5, "y": 2}, {"x": 5, "y": 5})
    new_position = body["entity_positions"][enemy["id"]]
    assert chebyshev_distance(new_position, {"x": 5, "y": 5}) > old_distance
    assert "游击撤步" in body["narration"]
    assert body["skirmisher_reposition"] == {
        "from": {"x": 5, "y": 2},
        "to": new_position,
        "steps": 2,
    }

    await db_session.refresh(ai_turn_combat)
    turn_state = ai_turn_combat.turn_states[enemy["id"]]
    assert turn_state["movement_used"] == 2
    assert turn_state["skirmisher_reposition"]["to"] == new_position


async def test_ai_movement_out_of_player_reach_triggers_player_opportunity_attack(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import Character
    from services.combat_service import AttackResult
    from services import combat_opportunity_attack_service as opportunity
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    ally = Character(
        id=str(_uuid.uuid4()),
        user_id=None,
        session_id=sample_session.id,
        is_player=False,
        name="Far Ally",
        race="Human",
        char_class="Fighter",
        level=2,
        ability_scores={"str": 14, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        derived={"hp_max": 20, "ac": 14, "ability_modifiers": {"str": 2, "dex": 1}},
        hp_current=20,
    )
    db_session.add(ally)

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["hp_current"] = 9
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "name": enemy.get("name", "Orc"),
        "hp_max": 9,
        "ac": 13,
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }
    state["companion_ids"] = [ally.id]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    ai_turn_combat.entity_positions = {
        enemy["id"]: {"x": 6, "y": 5},
        sample_character.id: {"x": 5, "y": 5},
        ally.id: {"x": 12, "y": 5},
    }
    ai_turn_combat.turn_order = [
        {"character_id": enemy["id"], "name": enemy["name"], "initiative": 18, "is_player": False, "is_enemy": True},
        {"character_id": ally.id, "name": ally.name, "initiative": 14, "is_player": False, "is_enemy": False},
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 12, "is_player": True, "is_enemy": False},
    ]
    ai_turn_combat.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "turn_states")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": ally.id,
            "reason": "test provoke opportunity while switching targets",
        }

    def fake_ai_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": False,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 11,
                "target_ac": 14,
            },
            damage=0,
            damage_roll={"formula": "1d8", "rolls": [], "total": 0},
            narration="miss",
        )

    def fake_opportunity_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 18,
                "target_ac": 13,
            },
            damage=4,
            damage_roll={"formula": "1d8", "rolls": [4], "total": 4},
            narration="opportunity hit",
        )

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_ai_attack)
    monkeypatch.setattr(opportunity.svc, "resolve_melee_attack", fake_opportunity_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["target_id"] == ally.id
    assert body["entity_positions"][enemy["id"]] == {"x": 11, "y": 5}
    assert body["opportunity_attacks"][0]["attacker"] == sample_character.name
    assert body["opportunity_attacks"][0]["target"] == enemy["name"]
    assert body["opportunity_attacks"][0]["damage"] == 4
    assert body["opportunity_attacks"][0]["attack_result"]["hit"] is True

    await db_session.refresh(ai_turn_combat)
    await db_session.refresh(sample_session)
    assert ai_turn_combat.turn_states[sample_character.id]["reaction_used"] is True
    assert ai_turn_combat.turn_states[enemy["id"]]["movement_used"] == 5
    refreshed_enemy = next(e for e in sample_session.game_state["enemies"] if e["id"] == enemy["id"])
    assert refreshed_enemy["hp_current"] == 5


async def test_ready_attack_endpoint_sets_trusted_ready_state(
    client, db_session, sample_session, sample_character, combat_state, sample_user,
):
    headers = await _auth_headers(client, sample_user)

    response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "attack",
            "trigger": "target_moves",
            "trigger_match": "leaves_reach",
            "target_id": "goblin-1",
            "condition_text": "当 Goblin 离开石门时发动一次攻击",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"] == "ready_action"
    assert body["ready_action"]["action_type"] == "attack"
    assert body["ready_action"]["trigger"] == "target_moves"
    assert body["ready_action"]["trigger_match"] == "leaves_reach"
    assert body["ready_action"]["target_id"] == "goblin-1"
    assert body["ready_action"]["condition_text"] == "当 Goblin 离开石门时发动一次攻击"

    await db_session.refresh(combat_state)
    turn_state = combat_state.turn_states[sample_character.id]
    assert turn_state["action_used"] is True
    assert turn_state["reaction_used"] is False
    assert turn_state["ready_action"]["target_id"] == "goblin-1"
    assert turn_state["ready_action"]["trigger_match"] == "leaves_reach"
    assert turn_state["ready_action"]["condition_text"] == "当 Goblin 离开石门时发动一次攻击"


async def test_ready_action_declaration_returns_structured_payload_and_combat_snapshot(
    client, db_session, sample_session, sample_character, combat_state, sample_user,
):
    from models import SessionMember

    sample_session.is_multiplayer = True
    sample_session.host_user_id = sample_user.id
    sample_session.room_code = "READY1"
    sample_character.user_id = sample_user.id
    db_session.add(SessionMember(
        session_id=sample_session.id,
        user_id=sample_user.id,
        character_id=sample_character.id,
        role="host",
    ))
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "attack",
            "trigger": "target_moves",
            "target_id": "goblin-1",
            "condition_text": "When Goblin moves, attack.",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"] == "ready_action"
    assert body["ready_action"]["action_type"] == "attack"
    assert body["ready_action"]["target_id"] == "goblin-1"
    assert body["ready_action"]["condition_text"] == "When Goblin moves, attack."
    assert body["dice_result"]["type"] == "ready_action_declared"
    assert body["dice_result"]["ready_action"] == body["ready_action"]
    assert body["special_action"] == body["dice_result"]
    ready_state = body["combat"]["turn_states"][sample_character.id]
    assert ready_state["action_used"] is True
    assert ready_state["ready_action"]["action_type"] == "attack"
    assert ready_state["ready_action"]["target_id"] == "goblin-1"
    assert ready_state["ready_action"]["condition_text"] == "When Goblin moves, attack."


async def test_ready_action_trigger_broadcasts_multiplayer_resolution(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import SessionMember
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat._shared as combat_shared
    import api.combat.ai_turn_attack as ai_turn_attack

    broadcasts = []

    async def fake_broadcast(session, event):
        broadcasts.append(event)

    monkeypatch.setattr(combat_shared, "broadcast_to_session", fake_broadcast)

    sample_session.is_multiplayer = True
    sample_session.host_user_id = sample_user.id
    sample_session.room_code = "READY2"
    sample_character.user_id = sample_user.id
    db_session.add(SessionMember(
        session_id=sample_session.id,
        user_id=sample_user.id,
        character_id=sample_character.id,
        role="host",
    ))

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["hp_current"] = 9
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "name": enemy.get("name", "Orc"),
        "hp_max": 9,
        "ac": 13,
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }
    state["enemies"] = [enemy]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    ai_turn_combat.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": enemy["id"],
            "name": enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    ai_turn_combat.current_turn_index = 0
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 10, "y": 5},
    }
    ai_turn_combat.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_states")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "reason": "test multiplayer ready trigger broadcast",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 18,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 13),
            },
            damage=3,
            damage_roll={"formula": "1d8", "rolls": [3], "total": 3},
            narration="hit",
        )

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "attack",
            "trigger": "target_moves",
            "target_id": enemy["id"],
            "condition_text": "When Orc moves, attack.",
        },
    )
    assert ready_response.status_code == 200, ready_response.text

    end_response = await client.post(f"/game/combat/{sample_session.id}/end-turn", headers=headers)
    assert end_response.status_code == 200, end_response.text

    ai_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert ai_response.status_code == 200, ai_response.text

    ai_updates = [
        event for event in broadcasts
        if event["type"] == "combat_update" and event.get("actor_id") == enemy["id"]
    ]
    assert ai_updates
    event = ai_updates[-1]
    assert event["ready_action_results"][0]["applied"] is True
    assert event["ready_action_results"][0]["trigger"] == "target_moves"
    assert event["ready_action_results"][0]["actor_id"] == sample_character.id
    assert event["ready_action_results"][0]["target_id"] == enemy["id"]
    assert event["ready_action_results"][0]["condition_text"] == "When Orc moves, attack."
    assert event["ready_action_results"][0]["damage"] == 3
    assert event["combat"]["entities"][enemy["id"]]["hp_current"] == 6


async def test_enemy_ready_attack_triggers_when_player_moves(
    client, db_session, sample_session, sample_character, combat_state, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import SessionMember
    from services.combat_ready_action_service import build_ready_attack_payload
    from services.combat_service import AttackResult
    import api.combat._shared as combat_shared
    import api.combat.movement as movement_api

    broadcasts = []

    async def fake_broadcast(session, event):
        broadcasts.append(event)

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 29,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 12),
            },
            damage=5,
            damage_roll={"formula": "1d1+4", "rolls": [1], "total": 5},
            narration="enemy ready hit",
        )

    monkeypatch.setattr(combat_shared, "broadcast_to_session", fake_broadcast)
    monkeypatch.setattr(movement_api.svc, "resolve_melee_attack", fake_resolve_melee_attack)

    sample_session.is_multiplayer = True
    sample_session.host_user_id = sample_user.id
    sample_session.room_code = "READY7"
    sample_character.user_id = sample_user.id
    sample_character.hp_current = 20
    sample_character.derived = {
        **dict(sample_character.derived or {}),
        "hp_max": 20,
        "ac": 12,
        "ability_modifiers": {"str": 3, "dex": 1, "con": 2, "int": 0, "wis": 0, "cha": 0},
    }
    db_session.add(SessionMember(
        session_id=sample_session.id,
        user_id=sample_user.id,
        character_id=sample_character.id,
        role="host",
    ))

    ready_enemy = {
        "id": "ready-enemy-sentinel",
        "name": "Ready Enemy Sentinel",
        "hp_current": 12,
        "hp_max": 12,
        "ac": 12,
        "conditions": [],
        "condition_durations": {},
        "derived": {
            "name": "Ready Enemy Sentinel",
            "hp_max": 12,
            "ac": 12,
            "attack_bonus": 24,
            "damage_dice": "1d1+4",
            "damage_type": "slashing",
            "ability_modifiers": {"str": 4, "dex": 1},
        },
        "actions": [{
            "id": "slash",
            "name": "Readied Slash",
            "type": "melee_attack",
            "attack_bonus": 24,
            "damage_dice": "1d1+4",
            "damage_type": "slashing",
        }],
        "speed": 30,
        "is_enemy": True,
    }
    sample_session.game_state = {**dict(sample_session.game_state or {}), "enemies": [ready_enemy]}
    flag_modified(sample_session, "game_state")

    combat_state.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": ready_enemy["id"],
            "name": ready_enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    combat_state.current_turn_index = 0
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        ready_enemy["id"]: {"x": 5, "y": 6},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "disengaged": True,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
        },
        ready_enemy["id"]: {
            "action_used": True,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
            "ready_action": build_ready_attack_payload(
                actor_id=ready_enemy["id"],
                actor_name=ready_enemy["name"],
                target_id=sample_character.id,
                target_name=sample_character.name,
                condition_text="When the hero moves, slash.",
            ),
        },
    }
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    move_response = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "to_x": 6,
            "to_y": 5,
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )
    assert move_response.status_code == 200, move_response.text
    body = move_response.json()
    result = body["ready_action_results"][0]
    assert result["applied"] is True, result
    assert result["action_type"] == "attack"
    assert result["actor_id"] == ready_enemy["id"]
    assert result["actor_is_enemy"] is True
    assert result["target_id"] == sample_character.id
    assert result["target_is_enemy"] is False
    assert result["condition_text"] == "When the hero moves, slash."
    assert result["attack_result"]["hit"] is True
    assert result["attack_result"]["attack_total"] == 29
    assert result["attack_result"]["enemy_action"]["name"] == "Readied Slash"
    assert result["damage"] == 5
    assert result["target_state"]["hp_current"] == 15
    assert result["turn_state"]["reaction_used"] is True
    assert "ready_action" not in result["turn_state"]

    move_events = [
        event for event in broadcasts
        if event["type"] == "entity_moved"
        and event.get("entity_id") == sample_character.id
        and event.get("ready_action_results")
    ]
    assert move_events
    event_result = move_events[-1]["ready_action_results"][0]
    assert event_result["actor_id"] == ready_enemy["id"]
    assert event_result["actor_is_enemy"] is True
    assert event_result["damage"] == 5
    assert event_result["target_state"]["hp_current"] == 15
    assert move_events[-1]["combat"]["entities"][sample_character.id]["hp_current"] == 15
    assert move_events[-1]["combat"]["turn_states"][ready_enemy["id"]]["reaction_used"] is True

    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    assert sample_character.hp_current == 15
    enemy_turn_state = combat_state.turn_states[ready_enemy["id"]]
    assert enemy_turn_state["reaction_used"] is True
    assert "ready_action" not in enemy_turn_state
    assert enemy_turn_state["ready_action_resolved"]["actor_is_enemy"] is True


async def test_enemy_ready_move_triggers_when_player_moves(
    client, db_session, sample_session, sample_character, combat_state, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import SessionMember
    from services.combat_ready_action_service import build_ready_move_payload
    import api.combat._shared as combat_shared

    broadcasts = []

    async def fake_broadcast(session, event):
        broadcasts.append(event)

    monkeypatch.setattr(combat_shared, "broadcast_to_session", fake_broadcast)

    sample_session.is_multiplayer = True
    sample_session.host_user_id = sample_user.id
    sample_session.room_code = "READY8"
    sample_character.user_id = sample_user.id
    sample_character.hp_current = 20
    sample_character.derived = {
        **dict(sample_character.derived or {}),
        "hp_max": 20,
        "ac": 12,
        "ability_modifiers": {"str": 3, "dex": 1, "con": 2, "int": 0, "wis": 0, "cha": 0},
    }
    db_session.add(SessionMember(
        session_id=sample_session.id,
        user_id=sample_user.id,
        character_id=sample_character.id,
        role="host",
    ))

    ready_enemy = {
        "id": "ready-enemy-skirmisher",
        "name": "Ready Enemy Skirmisher",
        "hp_current": 12,
        "hp_max": 12,
        "ac": 12,
        "conditions": [],
        "condition_durations": {},
        "derived": {
            "name": "Ready Enemy Skirmisher",
            "hp_max": 12,
            "ac": 12,
            "attack_bonus": 5,
            "damage_dice": "1d6+2",
            "ability_modifiers": {"str": 2, "dex": 3},
        },
        "actions": [{"name": "Scimitar", "type": "melee_attack", "damage_dice": "1d6+2", "attack_bonus": 4}],
        "speed": 30,
        "is_enemy": True,
    }
    sample_session.game_state = {**dict(sample_session.game_state or {}), "enemies": [ready_enemy]}
    flag_modified(sample_session, "game_state")

    combat_state.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": ready_enemy["id"],
            "name": ready_enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    combat_state.current_turn_index = 0
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        ready_enemy["id"]: {"x": 5, "y": 6},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
        },
        ready_enemy["id"]: {
            "action_used": True,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
                "ready_action": build_ready_move_payload(
                    actor_id=ready_enemy["id"],
                    actor_name=ready_enemy["name"],
                    target_id=sample_character.id,
                    target_name=sample_character.name,
                move_from={"x": 5, "y": 6},
                move_to={"x": 6, "y": 6},
                move_distance=1,
                condition_text="When the hero moves, shift.",
            ),
        },
    }
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    move_response = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "to_x": 6,
            "to_y": 5,
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )
    assert move_response.status_code == 200, move_response.text
    body = move_response.json()
    result = body["ready_action_results"][0]
    assert result["applied"] is True
    assert result["action_type"] == "move"
    assert result["actor_id"] == ready_enemy["id"]
    assert result["actor_is_enemy"] is True
    assert result["target_id"] == sample_character.id
    assert result["condition_text"] == "When the hero moves, shift."
    assert result["from"] == {"x": 5, "y": 6}
    assert result["to"] == {"x": 6, "y": 6}
    assert result["steps"] == 1
    assert result["distance_ft"] == 5
    assert result["entity_positions"][ready_enemy["id"]] == {"x": 6, "y": 6}
    assert result["turn_state"]["reaction_used"] is True
    assert result["turn_state"]["ready_action_resolved"]["actor_is_enemy"] is True
    assert "ready_action" not in result["turn_state"]
    assert body["opportunity_attacks"] == []

    move_events = [
        event for event in broadcasts
        if event["type"] == "entity_moved"
        and event.get("entity_id") == sample_character.id
        and event.get("ready_action_results")
    ]
    assert move_events
    event_result = move_events[-1]["ready_action_results"][0]
    assert event_result["actor_id"] == ready_enemy["id"]
    assert event_result["actor_is_enemy"] is True
    assert event_result["to"] == {"x": 6, "y": 6}
    assert move_events[-1]["opportunity_attacks"] == []
    assert move_events[-1]["combat"]["entity_positions"][ready_enemy["id"]] == {"x": 6, "y": 6}
    assert move_events[-1]["combat"]["turn_states"][ready_enemy["id"]]["reaction_used"] is True

    await db_session.refresh(combat_state)
    assert combat_state.entity_positions[ready_enemy["id"]] == {"x": 6, "y": 6}
    enemy_turn_state = combat_state.turn_states[ready_enemy["id"]]
    assert enemy_turn_state["reaction_used"] is True
    assert "ready_action" not in enemy_turn_state
    assert enemy_turn_state["ready_action_resolved"]["actor_is_enemy"] is True


async def test_enemy_ready_spell_cantrip_triggers_when_player_moves(
    client, db_session, sample_session, sample_character, combat_state, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import SessionMember
    from services.combat_ready_action_service import (
        build_ready_spell_payload,
        build_ready_spell_concentration_name,
    )
    import api.combat._shared as combat_shared

    broadcasts = []

    async def fake_broadcast(session, event):
        broadcasts.append(event)

    monkeypatch.setattr(combat_shared, "broadcast_to_session", fake_broadcast)

    sample_session.is_multiplayer = True
    sample_session.host_user_id = sample_user.id
    sample_session.room_code = "READY9"
    sample_character.user_id = sample_user.id
    sample_character.hp_current = 20
    sample_character.derived = {
        **dict(sample_character.derived or {}),
        "hp_max": 20,
        "ac": 12,
        "saving_throws": {"dex": 1},
        "ability_modifiers": {"str": 3, "dex": 1, "con": 2, "int": 0, "wis": 0, "cha": 0},
    }
    db_session.add(SessionMember(
        session_id=sample_session.id,
        user_id=sample_user.id,
        character_id=sample_character.id,
        role="host",
    ))

    spell_name = "神圣烈焰"
    ready_enemy = {
        "id": "ready-enemy-acolyte",
        "name": "Ready Enemy Acolyte",
        "hp_current": 12,
        "hp_max": 12,
        "ac": 12,
        "conditions": [],
        "condition_durations": {},
        "derived": {
            "name": "Ready Enemy Acolyte",
            "hp_max": 12,
            "ac": 12,
            "spell_save_dc": 99,
            "spell_attack_bonus": 5,
            "spell_ability": "wis",
            "ability_modifiers": {"str": 0, "dex": 1, "con": 1, "int": 0, "wis": 4, "cha": 1},
        },
        "concentration": build_ready_spell_concentration_name(spell_name),
        "known_spells": [spell_name],
        "prepared_spells": [spell_name],
        "cantrips": [spell_name],
        "spell_slots": {},
        "actions": [],
        "speed": 30,
        "is_enemy": True,
    }
    sample_session.game_state = {**dict(sample_session.game_state or {}), "enemies": [ready_enemy]}
    flag_modified(sample_session, "game_state")

    combat_state.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": ready_enemy["id"],
            "name": ready_enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    combat_state.current_turn_index = 0
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        ready_enemy["id"]: {"x": 5, "y": 6},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
        },
        ready_enemy["id"]: {
            "action_used": True,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
            "ready_action": build_ready_spell_payload(
                actor_id=ready_enemy["id"],
                actor_name=ready_enemy["name"],
                target_id=sample_character.id,
                target_name=sample_character.name,
                spell_name=spell_name,
                spell_level=0,
                condition_text="When the hero moves, cast Sacred Flame.",
            ),
        },
    }
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    move_response = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "to_x": 6,
            "to_y": 5,
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )
    assert move_response.status_code == 200, move_response.text
    body = move_response.json()
    result = body["ready_action_results"][0]
    assert result["applied"] is True
    assert result["action_type"] == "spell"
    assert result["actor_id"] == ready_enemy["id"]
    assert result["actor_is_enemy"] is True
    assert result["target_id"] == sample_character.id
    assert result["target_is_enemy"] is False
    assert result["condition_text"] == "When the hero moves, cast Sacred Flame."
    assert result["spell_name"] == spell_name
    assert result["spell_level"] == 0
    assert result.get("slot_already_consumed") is not True
    assert result["damage"] > 0
    assert result["target_state"]["save"]["success"] is False
    assert result["target_state"]["hp_current"] < 20
    assert result["turn_state"]["reaction_used"] is True
    assert "ready_action" not in result["turn_state"]
    assert result["turn_state"]["ready_action_resolved"]["actor_is_enemy"] is True
    assert result["turn_state"]["ready_action_resolved"]["save_result"]["success"] is False
    assert result["actor_state"]["concentration"] is None
    assert result["concentration_ended"] is True

    move_events = [
        event for event in broadcasts
        if event["type"] == "entity_moved"
        and event.get("entity_id") == sample_character.id
        and event.get("ready_action_results")
    ]
    assert move_events
    event_result = move_events[-1]["ready_action_results"][0]
    assert event_result["actor_id"] == ready_enemy["id"]
    assert event_result["actor_is_enemy"] is True
    assert event_result["action_type"] == "spell"
    assert event_result["spell_name"] == spell_name
    assert event_result["target_state"]["save"]["success"] is False
    assert event_result["turn_state"]["reaction_used"] is True
    assert move_events[-1]["combat"]["entities"][sample_character.id]["hp_current"] == result["target_state"]["hp_current"]
    assert move_events[-1]["combat"]["turn_states"][ready_enemy["id"]]["reaction_used"] is True

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    await db_session.refresh(combat_state)
    assert sample_character.hp_current == result["target_state"]["hp_current"]
    stored_enemy = sample_session.game_state["enemies"][0]
    assert stored_enemy["concentration"] is None
    enemy_turn_state = combat_state.turn_states[ready_enemy["id"]]
    assert enemy_turn_state["reaction_used"] is True
    assert "ready_action" not in enemy_turn_state
    assert enemy_turn_state["ready_action_resolved"]["actor_is_enemy"] is True


async def test_ready_action_reports_reaction_already_used_when_triggered_by_movement(
    client, db_session, sample_session, sample_character, combat_state, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import SessionMember
    from services.combat_ready_action_service import build_ready_attack_payload
    import api.combat._shared as combat_shared

    broadcasts = []

    async def fake_broadcast(session, event):
        broadcasts.append(event)

    monkeypatch.setattr(combat_shared, "broadcast_to_session", fake_broadcast)

    sample_session.is_multiplayer = True
    sample_session.host_user_id = sample_user.id
    sample_session.room_code = "READYA"
    sample_character.user_id = sample_user.id
    sample_character.hp_current = 20
    sample_character.derived = {
        **dict(sample_character.derived or {}),
        "hp_max": 20,
        "ac": 12,
        "ability_modifiers": {"str": 3, "dex": 1, "con": 2, "int": 0, "wis": 0, "cha": 0},
    }
    db_session.add(SessionMember(
        session_id=sample_session.id,
        user_id=sample_user.id,
        character_id=sample_character.id,
        role="host",
    ))

    ready_enemy = {
        "id": "ready-enemy-spent-reaction",
        "name": "Ready Enemy Spent Reaction",
        "hp_current": 12,
        "hp_max": 12,
        "ac": 12,
        "conditions": [],
        "condition_durations": {},
        "derived": {
            "name": "Ready Enemy Spent Reaction",
            "hp_max": 12,
            "ac": 12,
            "attack_bonus": 24,
            "damage_dice": "1d1+4",
            "damage_type": "slashing",
            "ability_modifiers": {"str": 4, "dex": 1},
        },
        "actions": [{"name": "Readied Slash", "type": "melee_attack", "attack_bonus": 24, "damage_dice": "1d1+4"}],
        "speed": 30,
        "is_enemy": True,
    }
    sample_session.game_state = {**dict(sample_session.game_state or {}), "enemies": [ready_enemy]}
    flag_modified(sample_session, "game_state")

    condition_text = "When Ready Smoke Hero crosses the bridge, slash."
    combat_state.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": ready_enemy["id"],
            "name": ready_enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    combat_state.current_turn_index = 0
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        ready_enemy["id"]: {"x": 5, "y": 6},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
        },
        ready_enemy["id"]: {
            "action_used": True,
            "bonus_action_used": False,
            "reaction_used": True,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
            "ready_action": build_ready_attack_payload(
                actor_id=ready_enemy["id"],
                actor_name=ready_enemy["name"],
                target_id=sample_character.id,
                target_name=sample_character.name,
                condition_text=condition_text,
            ),
        },
    }
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    move_response = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "to_x": 6,
            "to_y": 5,
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )
    assert move_response.status_code == 200, move_response.text
    body = move_response.json()
    result = body["ready_action_results"][0]
    assert result["applied"] is False
    assert result["action_type"] == "attack"
    assert result["reason"] == "reaction_already_used"
    assert result["reaction_already_used"] is True
    assert result["actor_id"] == ready_enemy["id"]
    assert result["actor_is_enemy"] is True
    assert result["target_id"] == sample_character.id
    assert result["condition_text"] == condition_text
    assert result["turn_state"]["reaction_used"] is True
    assert result["turn_state"]["ready_action_failed"]["reason"] == "reaction_already_used"
    assert result["turn_state"]["ready_action_failed"]["condition_text"] == condition_text
    assert "ready_action" not in result["turn_state"]
    assert sample_character.hp_current == 20

    move_events = [
        event for event in broadcasts
        if event["type"] == "entity_moved"
        and event.get("entity_id") == sample_character.id
        and event.get("ready_action_results")
    ]
    assert move_events
    event_result = move_events[-1]["ready_action_results"][0]
    assert event_result["applied"] is False
    assert event_result["reason"] == "reaction_already_used"
    assert event_result["condition_text"] == condition_text
    assert event_result["actor_is_enemy"] is True
    assert move_events[-1]["combat"]["entities"][sample_character.id]["hp_current"] == 20
    assert move_events[-1]["combat"]["turn_states"][ready_enemy["id"]]["reaction_used"] is True
    assert "ready_action" not in move_events[-1]["combat"]["turn_states"][ready_enemy["id"]]

    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    assert sample_character.hp_current == 20
    enemy_turn_state = combat_state.turn_states[ready_enemy["id"]]
    assert enemy_turn_state["reaction_used"] is True
    assert "ready_action" not in enemy_turn_state
    assert enemy_turn_state["ready_action_failed"]["reason"] == "reaction_already_used"


async def test_ready_action_enters_reach_match_waits_until_target_moves_into_reach(
    client, db_session, sample_session, sample_character, combat_state, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import SessionMember
    from services.combat_ready_action_service import build_ready_attack_payload
    from services.combat_service import AttackResult
    import api.combat._shared as combat_shared
    import api.combat.movement as movement_api

    broadcasts = []

    async def fake_broadcast(session, event):
        broadcasts.append(event)

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 31,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 12),
            },
            damage=5,
            damage_roll={"formula": "1d1+4", "rolls": [1], "total": 5},
            narration="enemy ready enters reach hit",
        )

    monkeypatch.setattr(combat_shared, "broadcast_to_session", fake_broadcast)
    monkeypatch.setattr(movement_api.svc, "resolve_melee_attack", fake_resolve_melee_attack)

    sample_session.is_multiplayer = True
    sample_session.host_user_id = sample_user.id
    sample_session.room_code = "READYB"
    sample_character.user_id = sample_user.id
    sample_character.hp_current = 20
    sample_character.derived = {
        **dict(sample_character.derived or {}),
        "hp_max": 20,
        "ac": 12,
        "ability_modifiers": {"str": 3, "dex": 1, "con": 2, "int": 0, "wis": 0, "cha": 0},
    }
    db_session.add(SessionMember(
        session_id=sample_session.id,
        user_id=sample_user.id,
        character_id=sample_character.id,
        role="host",
    ))

    ready_enemy = {
        "id": "ready-enemy-reach-guard",
        "name": "Ready Enemy Reach Guard",
        "hp_current": 12,
        "hp_max": 12,
        "ac": 12,
        "conditions": [],
        "condition_durations": {},
        "derived": {
            "name": "Ready Enemy Reach Guard",
            "hp_max": 12,
            "ac": 12,
            "attack_bonus": 24,
            "damage_dice": "1d1+4",
            "damage_type": "slashing",
            "ability_modifiers": {"str": 4, "dex": 1},
        },
        "actions": [{"name": "Readied Slash", "type": "melee_attack", "attack_bonus": 24, "damage_dice": "1d1+4"}],
        "speed": 30,
        "is_enemy": True,
    }
    sample_session.game_state = {**dict(sample_session.game_state or {}), "enemies": [ready_enemy]}
    flag_modified(sample_session, "game_state")

    condition_text = "When Ready Smoke Hero enters reach, slash."
    combat_state.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": ready_enemy["id"],
            "name": ready_enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    combat_state.current_turn_index = 0
    combat_state.entity_positions = {
        sample_character.id: {"x": 8, "y": 6},
        ready_enemy["id"]: {"x": 5, "y": 6},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
        },
        ready_enemy["id"]: {
            "action_used": True,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
            "ready_action": build_ready_attack_payload(
                actor_id=ready_enemy["id"],
                actor_name=ready_enemy["name"],
                target_id=sample_character.id,
                target_name=sample_character.name,
                condition_text=condition_text,
                trigger_match="enters_reach",
            ),
        },
    }
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    first_move = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "to_x": 7,
            "to_y": 6,
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )
    assert first_move.status_code == 200, first_move.text
    first_body = first_move.json()
    assert first_body["ready_action_results"] == []
    assert first_body["combat"]["turn_states"][ready_enemy["id"]]["ready_action"]["trigger_match"] == "enters_reach"
    assert first_body["combat"]["entities"][sample_character.id]["hp_current"] == 20

    second_move = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "to_x": 6,
            "to_y": 6,
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )
    assert second_move.status_code == 200, second_move.text
    body = second_move.json()
    result = body["ready_action_results"][0]
    assert result["applied"] is True
    assert result["action_type"] == "attack"
    assert result["trigger_match"] == "enters_reach"
    assert result["actor_id"] == ready_enemy["id"]
    assert result["actor_is_enemy"] is True
    assert result["condition_text"] == condition_text
    assert result["attack_result"]["hit"] is True
    assert result["damage"] == 5
    assert result["target_state"]["hp_current"] == 15
    assert result["turn_state"]["reaction_used"] is True
    assert result["turn_state"]["ready_action_resolved"]["trigger_match"] == "enters_reach"
    assert "ready_action" not in result["turn_state"]

    move_events = [
        event for event in broadcasts
        if event["type"] == "entity_moved"
        and event.get("entity_id") == sample_character.id
    ]
    assert move_events[0]["ready_action_results"] == []
    assert move_events[-1]["ready_action_results"][0]["trigger_match"] == "enters_reach"
    assert move_events[-1]["combat"]["entities"][sample_character.id]["hp_current"] == 15

    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    assert sample_character.hp_current == 15
    enemy_turn_state = combat_state.turn_states[ready_enemy["id"]]
    assert enemy_turn_state["reaction_used"] is True
    assert "ready_action" not in enemy_turn_state
    assert enemy_turn_state["ready_action_resolved"]["trigger_match"] == "enters_reach"


async def test_ready_action_leaves_reach_match_waits_until_target_moves_out_of_reach(
    client, db_session, sample_session, sample_character, combat_state, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import SessionMember
    from services.combat_ready_action_service import build_ready_attack_payload
    from services.combat_service import AttackResult
    import api.combat._shared as combat_shared
    import api.combat.movement as movement_api

    broadcasts = []

    async def fake_broadcast(session, event):
        broadcasts.append(event)

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 32,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 12),
            },
            damage=5,
            damage_roll={"formula": "1d1+4", "rolls": [1], "total": 5},
            narration="enemy ready leaves reach hit",
        )

    monkeypatch.setattr(combat_shared, "broadcast_to_session", fake_broadcast)
    monkeypatch.setattr(movement_api.svc, "resolve_melee_attack", fake_resolve_melee_attack)

    sample_session.is_multiplayer = True
    sample_session.host_user_id = sample_user.id
    sample_session.room_code = "READYL"
    sample_character.user_id = sample_user.id
    sample_character.hp_current = 20
    sample_character.derived = {
        **dict(sample_character.derived or {}),
        "hp_max": 20,
        "ac": 12,
        "ability_modifiers": {"str": 3, "dex": 1, "con": 2, "int": 0, "wis": 0, "cha": 0},
    }
    db_session.add(SessionMember(
        session_id=sample_session.id,
        user_id=sample_user.id,
        character_id=sample_character.id,
        role="host",
    ))

    ready_enemy = {
        "id": "ready-enemy-leave-guard",
        "name": "Ready Enemy Leave Guard",
        "hp_current": 12,
        "hp_max": 12,
        "ac": 12,
        "conditions": [],
        "condition_durations": {},
        "derived": {
            "name": "Ready Enemy Leave Guard",
            "hp_max": 12,
            "ac": 12,
            "attack_bonus": 24,
            "damage_dice": "1d1+4",
            "damage_type": "slashing",
            "ability_modifiers": {"str": 4, "dex": 1},
        },
        "actions": [{"name": "Readied Slash", "type": "melee_attack", "attack_bonus": 24, "damage_dice": "1d1+4"}],
        "speed": 30,
        "is_enemy": True,
    }
    sample_session.game_state = {**dict(sample_session.game_state or {}), "enemies": [ready_enemy]}
    flag_modified(sample_session, "game_state")

    condition_text = "When Ready Smoke Hero leaves reach, slash."
    combat_state.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": ready_enemy["id"],
            "name": ready_enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    combat_state.current_turn_index = 0
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        ready_enemy["id"]: {"x": 5, "y": 6},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "disengaged": True,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
        },
        ready_enemy["id"]: {
            "action_used": True,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
            "ready_action": build_ready_attack_payload(
                actor_id=ready_enemy["id"],
                actor_name=ready_enemy["name"],
                target_id=sample_character.id,
                target_name=sample_character.name,
                condition_text=condition_text,
                trigger_match="leaves_reach",
            ),
        },
    }
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    first_move = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "to_x": 6,
            "to_y": 6,
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )
    assert first_move.status_code == 200, first_move.text
    first_body = first_move.json()
    assert first_body["ready_action_results"] == []
    assert first_body["combat"]["turn_states"][ready_enemy["id"]]["ready_action"]["trigger_match"] == "leaves_reach"
    assert first_body["combat"]["turn_states"][ready_enemy["id"]]["reaction_used"] is False
    assert first_body["combat"]["entities"][sample_character.id]["hp_current"] == 20

    second_move = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "to_x": 7,
            "to_y": 6,
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )
    assert second_move.status_code == 200, second_move.text
    body = second_move.json()
    result = body["ready_action_results"][0]
    assert result["applied"] is True
    assert result["action_type"] == "attack"
    assert result["trigger_match"] == "leaves_reach"
    assert result["actor_id"] == ready_enemy["id"]
    assert result["actor_is_enemy"] is True
    assert result["condition_text"] == condition_text
    assert result["attack_result"]["hit"] is True
    assert result["damage"] == 5
    assert result["target_state"]["hp_current"] == 15
    assert result["turn_state"]["reaction_used"] is True
    assert result["turn_state"]["ready_action_resolved"]["trigger_match"] == "leaves_reach"
    assert "ready_action" not in result["turn_state"]

    move_events = [
        event for event in broadcasts
        if event["type"] == "entity_moved"
        and event.get("entity_id") == sample_character.id
    ]
    assert move_events[0]["ready_action_results"] == []
    assert move_events[-1]["ready_action_results"][0]["trigger_match"] == "leaves_reach"
    assert move_events[-1]["combat"]["entities"][sample_character.id]["hp_current"] == 15

    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    assert sample_character.hp_current == 15
    enemy_turn_state = combat_state.turn_states[ready_enemy["id"]]
    assert enemy_turn_state["reaction_used"] is True
    assert "ready_action" not in enemy_turn_state
    assert enemy_turn_state["ready_action_resolved"]["trigger_match"] == "leaves_reach"


async def test_ready_move_trigger_broadcasts_multiplayer_entity_moved_resolution(
    client, db_session, sample_session, sample_character, combat_state, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import Character, SessionMember
    import api.combat._shared as combat_shared

    broadcasts = []

    async def fake_broadcast(session, event):
        broadcasts.append(event)

    monkeypatch.setattr(combat_shared, "broadcast_to_session", fake_broadcast)

    guest = Character(
        id=str(_uuid.uuid4()),
        user_id=sample_user.id,
        session_id=sample_session.id,
        is_player=True,
        name="Ready Move Guest",
        race="Elf",
        char_class="Wizard",
        level=3,
        ability_scores={"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 10},
        derived={
            "hp_max": 16,
            "ac": 12,
            "initiative": 1,
            "ability_modifiers": {"str": -1, "dex": 2, "con": 1, "int": 3, "wis": 0, "cha": 0},
            "spell_slots_max": {"1st": 4},
        },
        hp_current=16,
        spell_slots={"1st": 4},
    )

    sample_session.is_multiplayer = True
    sample_session.host_user_id = sample_user.id
    sample_session.room_code = "READY3"
    sample_character.user_id = sample_user.id
    db_session.add_all([
        guest,
        SessionMember(
            session_id=sample_session.id,
            user_id=sample_user.id,
            character_id=sample_character.id,
            role="host",
        ),
    ])

    combat_state.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": guest.id,
            "name": guest.name,
            "initiative": 12,
            "is_player": True,
            "is_enemy": False,
        },
    ]
    combat_state.current_turn_index = 0
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        guest.id: {"x": 8, "y": 5},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
        },
    }
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "move",
            "trigger": "target_moves",
            "target_id": guest.id,
            "move_to_x": 5,
            "move_to_y": 6,
            "condition_text": "When Ready Move Guest moves, reposition.",
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )
    assert ready_response.status_code == 200, ready_response.text

    end_response = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_character.id}"},
    )
    assert end_response.status_code == 200, end_response.text

    move_response = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": guest.id,
            "to_x": 6,
            "to_y": 5,
            "expected_turn_token": f"1:1:{guest.id}",
        },
    )
    assert move_response.status_code == 200, move_response.text
    body = move_response.json()
    assert body["ready_action_results"][0]["applied"] is True
    assert body["ready_action_results"][0]["action_type"] == "move"
    assert body["ready_action_results"][0]["actor_id"] == sample_character.id
    assert body["ready_action_results"][0]["target_id"] == guest.id
    assert body["ready_action_results"][0]["to"] == {"x": 5, "y": 6}

    move_events = [
        event for event in broadcasts
        if event["type"] == "entity_moved"
        and event.get("entity_id") == guest.id
        and event.get("ready_action_results")
    ]
    assert move_events
    event = move_events[-1]
    result = event["ready_action_results"][0]
    assert result["applied"] is True
    assert result["action_type"] == "move"
    assert result["actor_id"] == sample_character.id
    assert result["target_id"] == guest.id
    assert result["to"] == {"x": 5, "y": 6}
    assert result["turn_state"]["reaction_used"] is True
    assert event["combat"]["entity_positions"][sample_character.id] == {"x": 5, "y": 6}
    assert event["combat"]["entity_positions"][guest.id] == {"x": 6, "y": 5}


async def test_ready_spell_trigger_broadcasts_multiplayer_entity_moved_resolution(
    client, db_session, sample_session, sample_character, combat_state, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import Character, SessionMember
    import api.combat._shared as combat_shared

    broadcasts = []

    async def fake_broadcast(session, event):
        broadcasts.append(event)

    monkeypatch.setattr(combat_shared, "broadcast_to_session", fake_broadcast)

    guest = Character(
        id=str(_uuid.uuid4()),
        user_id=sample_user.id,
        session_id=sample_session.id,
        is_player=True,
        name="Ready Spell Guest",
        race="Elf",
        char_class="Wizard",
        level=3,
        ability_scores={"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 10},
        derived={
            "hp_max": 16,
            "ac": 12,
            "initiative": 1,
            "ability_modifiers": {"str": -1, "dex": 2, "con": 1, "int": 3, "wis": 0, "cha": 0},
            "spell_slots_max": {"1st": 4},
        },
        hp_current=16,
        spell_slots={"1st": 4},
    )

    sample_session.is_multiplayer = True
    sample_session.host_user_id = sample_user.id
    sample_session.room_code = "READY4"
    sample_character.user_id = sample_user.id
    sample_character.char_class = "Wizard"
    sample_character.derived = {
        **dict(sample_character.derived or {}),
        "spell_save_dc": 15,
        "spell_attack_bonus": 7,
        "spell_ability": "int",
        "ability_modifiers": {"str": 0, "dex": 2, "con": 2, "int": 4, "wis": 0, "cha": 0},
        "spell_slots_max": {"1st": 1},
    }
    sample_character.spell_slots = {"1st": 1}
    db_session.add_all([
        guest,
        SessionMember(
            session_id=sample_session.id,
            user_id=sample_user.id,
            character_id=sample_character.id,
            role="host",
        ),
    ])

    combat_state.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": guest.id,
            "name": guest.name,
            "initiative": 12,
            "is_player": True,
            "is_enemy": False,
        },
    ]
    combat_state.current_turn_index = 0
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        guest.id: {"x": 8, "y": 5},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
        },
    }
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "spell",
            "trigger": "target_moves",
            "target_id": guest.id,
            "spell_name": "魔法飞弹",
            "spell_level": 1,
            "condition_text": "When Ready Spell Guest moves, cast Magic Missile.",
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )
    assert ready_response.status_code == 200, ready_response.text
    assert ready_response.json()["remaining_slots"] == {"1st": 0}

    end_response = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_character.id}"},
    )
    assert end_response.status_code == 200, end_response.text

    move_response = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": guest.id,
            "to_x": 6,
            "to_y": 5,
            "expected_turn_token": f"1:1:{guest.id}",
        },
    )
    assert move_response.status_code == 200, move_response.text
    body = move_response.json()
    ready_result = body["ready_action_results"][0]
    assert ready_result["applied"] is True
    assert ready_result["action_type"] == "spell"
    assert ready_result["actor_id"] == sample_character.id
    assert ready_result["target_id"] == guest.id
    assert ready_result["spell_name"] == "魔法飞弹"
    assert ready_result["slot_already_consumed"] is True
    assert ready_result["slot_key"] == "1st"
    assert ready_result["slots_remaining"] == 0
    assert ready_result["damage"] > 0
    assert ready_result["target_state"]["hp_current"] < 16

    move_events = [
        event for event in broadcasts
        if event["type"] == "entity_moved"
        and event.get("entity_id") == guest.id
        and event.get("ready_action_results")
    ]
    assert move_events
    event = move_events[-1]
    result = event["ready_action_results"][0]
    assert result["applied"] is True
    assert result["action_type"] == "spell"
    assert result["actor_id"] == sample_character.id
    assert result["target_id"] == guest.id
    assert result["spell_name"] == "魔法飞弹"
    assert result["slot_already_consumed"] is True
    assert result["slot_key"] == "1st"
    assert result["slots_remaining"] == 0
    assert result["turn_state"]["reaction_used"] is True
    assert result["turn_state"]["ready_action_resolved"]["spell_name"] == "魔法飞弹"
    assert event["combat"]["entities"][guest.id]["hp_current"] == result["target_state"]["hp_current"]


async def test_ready_cantrip_trigger_broadcasts_multiplayer_entity_moved_resolution(
    client, db_session, sample_session, sample_character, combat_state, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import Character, SessionMember
    import api.combat._shared as combat_shared

    broadcasts = []

    async def fake_broadcast(session, event):
        broadcasts.append(event)

    monkeypatch.setattr(combat_shared, "broadcast_to_session", fake_broadcast)

    guest = Character(
        id=str(_uuid.uuid4()),
        user_id=sample_user.id,
        session_id=sample_session.id,
        is_player=True,
        name="Ready Cantrip Guest",
        race="Elf",
        char_class="Wizard",
        level=3,
        ability_scores={"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 10},
        derived={
            "hp_max": 16,
            "ac": 12,
            "initiative": 1,
            "saving_throws": {"dex": 0},
            "ability_modifiers": {"str": -1, "dex": 2, "con": 1, "int": 3, "wis": 0, "cha": 0},
            "spell_slots_max": {"1st": 4},
        },
        hp_current=16,
        spell_slots={"1st": 4},
    )

    sample_session.is_multiplayer = True
    sample_session.host_user_id = sample_user.id
    sample_session.room_code = "READY5"
    sample_character.user_id = sample_user.id
    sample_character.char_class = "Cleric"
    sample_character.derived = {
        **dict(sample_character.derived or {}),
        "spell_save_dc": 99,
        "spell_attack_bonus": 7,
        "spell_ability": "wis",
        "ability_modifiers": {"str": 0, "dex": 2, "con": 2, "int": 0, "wis": 4, "cha": 0},
        "spell_slots_max": {},
    }
    sample_character.spell_slots = {}
    sample_character.cantrips = ["神圣烈焰"]
    db_session.add_all([
        guest,
        SessionMember(
            session_id=sample_session.id,
            user_id=sample_user.id,
            character_id=sample_character.id,
            role="host",
        ),
    ])

    combat_state.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": guest.id,
            "name": guest.name,
            "initiative": 12,
            "is_player": True,
            "is_enemy": False,
        },
    ]
    combat_state.current_turn_index = 0
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        guest.id: {"x": 8, "y": 5},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
        },
    }
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "spell",
            "trigger": "target_moves",
            "target_id": guest.id,
            "spell_name": "神圣烈焰",
            "spell_level": 0,
            "condition_text": "When Ready Cantrip Guest moves, cast Sacred Flame.",
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )
    assert ready_response.status_code == 200, ready_response.text
    assert ready_response.json()["remaining_slots"] is None
    assert ready_response.json()["ready_action"].get("slot_already_consumed") is not True

    end_response = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_character.id}"},
    )
    assert end_response.status_code == 200, end_response.text

    move_response = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": guest.id,
            "to_x": 6,
            "to_y": 5,
            "expected_turn_token": f"1:1:{guest.id}",
        },
    )
    assert move_response.status_code == 200, move_response.text
    body = move_response.json()
    ready_result = body["ready_action_results"][0]
    assert ready_result["applied"] is True
    assert ready_result["action_type"] == "spell"
    assert ready_result["actor_id"] == sample_character.id
    assert ready_result["target_id"] == guest.id
    assert ready_result["spell_name"] == "神圣烈焰"
    assert ready_result.get("slot_already_consumed") is not True
    assert ready_result["damage"] > 0
    assert ready_result["target_state"]["save"]["success"] is False
    assert ready_result["target_state"]["hp_current"] < 16

    move_events = [
        event for event in broadcasts
        if event["type"] == "entity_moved"
        and event.get("entity_id") == guest.id
        and event.get("ready_action_results")
    ]
    assert move_events
    event = move_events[-1]
    result = event["ready_action_results"][0]
    assert result["applied"] is True
    assert result["action_type"] == "spell"
    assert result["actor_id"] == sample_character.id
    assert result["target_id"] == guest.id
    assert result["spell_name"] == "神圣烈焰"
    assert result.get("slot_already_consumed") is not True
    assert result["target_state"]["save"]["success"] is False
    assert result["turn_state"]["reaction_used"] is True
    assert result["turn_state"]["ready_action_resolved"]["spell_name"] == "神圣烈焰"
    assert event["combat"]["entities"][guest.id]["hp_current"] == result["target_state"]["hp_current"]


async def test_ready_spell_attack_trigger_broadcasts_multiplayer_entity_moved_resolution(
    client, db_session, sample_session, sample_character, combat_state, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import Character, SessionMember
    import api.combat._shared as combat_shared
    import services.combat_spell_prepare_service as spell_prepare
    import services.spell_service as spell_service_module

    broadcasts = []

    async def fake_broadcast(session, event):
        broadcasts.append(event)

    def fake_spell_attack_roll(*args, **kwargs):
        target = kwargs.get("target") or {}
        target_ac = dict(target.get("derived") or {}).get("ac", 12)
        return {
            "d20": 12,
            "attack_bonus": 25,
            "condition_modifier": 0,
            "attack_total": 37,
            "target_ac": target_ac,
            "hit": True,
            "is_crit": False,
            "is_fumble": False,
        }

    monkeypatch.setattr(combat_shared, "broadcast_to_session", fake_broadcast)
    monkeypatch.setattr(spell_prepare, "roll_attack", fake_spell_attack_roll)
    monkeypatch.setattr(
        spell_service_module.spell_service,
        "resolve_damage",
        lambda *_args, **_kwargs: (7, {"formula": "1d10", "rolls": [7], "total": 7}),
    )

    guest = Character(
        id=str(_uuid.uuid4()),
        user_id=sample_user.id,
        session_id=sample_session.id,
        is_player=True,
        name="Ready Spell Attack Guest",
        race="Elf",
        char_class="Wizard",
        level=3,
        ability_scores={"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 10},
        derived={
            "hp_max": 16,
            "ac": 12,
            "initiative": 1,
            "ability_modifiers": {"str": -1, "dex": 2, "con": 1, "int": 3, "wis": 0, "cha": 0},
            "spell_slots_max": {"1st": 4},
        },
        hp_current=16,
        spell_slots={"1st": 4},
    )

    sample_session.is_multiplayer = True
    sample_session.host_user_id = sample_user.id
    sample_session.room_code = "READY6"
    sample_character.user_id = sample_user.id
    sample_character.char_class = "Wizard"
    sample_character.cantrips = ["Fire Bolt"]
    sample_character.known_spells = ["Fire Bolt"]
    sample_character.derived = {
        **dict(sample_character.derived or {}),
        "spell_save_dc": 15,
        "spell_attack_bonus": 25,
        "spell_ability": "int",
        "ability_modifiers": {"str": 0, "dex": 2, "con": 2, "int": 5, "wis": 0, "cha": 0},
        "spell_slots_max": {},
    }
    sample_character.spell_slots = {}
    db_session.add_all([
        guest,
        SessionMember(
            session_id=sample_session.id,
            user_id=sample_user.id,
            character_id=sample_character.id,
            role="host",
        ),
    ])

    combat_state.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": guest.id,
            "name": guest.name,
            "initiative": 12,
            "is_player": True,
            "is_enemy": False,
        },
    ]
    combat_state.current_turn_index = 0
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        guest.id: {"x": 8, "y": 5},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "base_movement_max": 6,
        },
    }
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "spell",
            "trigger": "target_moves",
            "target_id": guest.id,
            "spell_name": "火焰射线",
            "spell_level": 0,
            "condition_text": "When Ready Spell Attack Guest moves, cast Fire Bolt.",
            "expected_turn_token": f"1:0:{sample_character.id}",
        },
    )
    assert ready_response.status_code == 200, ready_response.text
    assert ready_response.json()["remaining_slots"] is None
    assert ready_response.json()["ready_action"].get("slot_already_consumed") is not True

    end_response = await client.post(
        f"/game/combat/{sample_session.id}/end-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{sample_character.id}"},
    )
    assert end_response.status_code == 200, end_response.text

    move_response = await client.post(
        f"/game/combat/{sample_session.id}/move",
        headers=headers,
        json={
            "entity_id": guest.id,
            "to_x": 6,
            "to_y": 5,
            "expected_turn_token": f"1:1:{guest.id}",
        },
    )
    assert move_response.status_code == 200, move_response.text
    body = move_response.json()
    ready_result = body["ready_action_results"][0]
    assert ready_result["applied"] is True
    assert ready_result["action_type"] == "spell"
    assert ready_result["actor_id"] == sample_character.id
    assert ready_result["target_id"] == guest.id
    assert ready_result["spell_name"] == "火焰射线"
    assert ready_result.get("slot_already_consumed") is not True
    assert ready_result["hit"] is True
    assert ready_result["attack_result"]["spell_attack"] is True
    assert ready_result["attack_result"]["hit"] is True
    assert ready_result["attack_result"]["attack_total"] == 37
    assert ready_result["attack_result"]["target_ac"] == 12
    assert ready_result["damage"] == 7
    assert ready_result["target_state"]["hp_current"] == 9

    move_events = [
        event for event in broadcasts
        if event["type"] == "entity_moved"
        and event.get("entity_id") == guest.id
        and event.get("ready_action_results")
    ]
    assert move_events
    event = move_events[-1]
    result = event["ready_action_results"][0]
    assert result["applied"] is True
    assert result["action_type"] == "spell"
    assert result["actor_id"] == sample_character.id
    assert result["target_id"] == guest.id
    assert result["spell_name"] == "火焰射线"
    assert result.get("slot_already_consumed") is not True
    assert result["hit"] is True
    assert result["attack_result"]["spell_attack"] is True
    assert result["attack_result"]["attack_total"] == 37
    assert result["attack_result"]["target_ac"] == 12
    assert result["turn_state"]["reaction_used"] is True
    assert result["turn_state"]["ready_action_resolved"]["spell_name"] == "火焰射线"
    assert result["turn_state"]["ready_action_resolved"]["hit"] is True
    assert event["combat"]["entities"][guest.id]["hp_current"] == result["target_state"]["hp_current"]


async def test_ready_attack_triggers_when_target_moves_on_ai_turn(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    guard = {
        "id": "orc-guard",
        "name": "Orc Guard",
        "hp_current": 9,
        "max_hp": 9,
        "derived": {
            "hp_max": 9,
            "ac": 13,
            "attack_bonus": 5,
            "hit_die": 8,
            "ability_modifiers": {"str": 3, "dex": 1},
        },
        "actions": [{"name": "Club", "type": "melee_attack", "damage_dice": "1d6", "attack_bonus": 4}],
        "speed": 30,
    }
    enemy["hp_current"] = 9
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "name": enemy.get("name", "Orc"),
        "hp_max": 9,
        "ac": 13,
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }
    state["enemies"] = [enemy, guard]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    ai_turn_combat.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": enemy["id"],
            "name": enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    ai_turn_combat.current_turn_index = 0
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 10, "y": 5},
        guard["id"]: {"x": 18, "y": 5},
    }
    ai_turn_combat.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_states")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "reason": "test ready attack trigger while closing distance",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 18,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 13),
            },
            damage=3,
            damage_roll={"formula": "1d8", "rolls": [3], "total": 3},
            narration="hit",
        )

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "attack",
            "trigger": "target_moves",
            "target_id": enemy["id"],
            "condition_text": "当 Orc 离开桥头时发动一次攻击",
        },
    )
    assert ready_response.status_code == 200, ready_response.text

    end_response = await client.post(f"/game/combat/{sample_session.id}/end-turn", headers=headers)
    assert end_response.status_code == 200, end_response.text

    ai_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert ai_response.status_code == 200, ai_response.text
    body = ai_response.json()
    assert body["entity_positions"][enemy["id"]] == {"x": 6, "y": 5}
    assert body["ready_action_results"][0]["applied"] is True
    assert body["ready_action_results"][0]["trigger"] == "target_moves"
    assert body["ready_action_results"][0]["actor_id"] == sample_character.id
    assert body["ready_action_results"][0]["target_id"] == enemy["id"]
    assert body["ready_action_results"][0]["condition_text"] == "当 Orc 离开桥头时发动一次攻击"
    assert body["ready_action_results"][0]["damage"] == 3
    resolved_turn_state = body["ready_action_results"][0]["turn_state"]
    assert resolved_turn_state["reaction_used"] is True
    assert "ready_action" not in resolved_turn_state
    assert resolved_turn_state["ready_action_resolved"]["trigger"] == "target_moves"
    assert resolved_turn_state["ready_action_resolved"]["condition_text"] == "当 Orc 离开桥头时发动一次攻击"

    await db_session.refresh(ai_turn_combat)
    await db_session.refresh(sample_session)
    turn_state = ai_turn_combat.turn_states[sample_character.id]
    assert turn_state["reaction_used"] is False
    assert "ready_action" not in turn_state
    refreshed_enemy = next(e for e in sample_session.game_state["enemies"] if e["id"] == enemy["id"])
    assert refreshed_enemy["hp_current"] == 6


async def test_ready_action_expires_when_next_turn_starts_without_trigger(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import GameLog
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["hp_current"] = 9
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "name": enemy.get("name", "Orc"),
        "hp_max": 9,
        "ac": 13,
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }
    state["enemies"] = [enemy]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    ai_turn_combat.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": enemy["id"],
            "name": enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    ai_turn_combat.current_turn_index = 0
    ai_turn_combat.round_number = 1
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 6, "y": 5},
    }
    ai_turn_combat.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_states")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "reason": "test ready action expiry without movement",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": False,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 8,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 13),
            },
            damage=0,
            damage_roll={"formula": "1d8", "rolls": [0], "total": 0},
            narration="miss",
        )

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "attack",
            "trigger": "target_moves",
            "target_id": enemy["id"],
            "condition_text": "当 Orc 离开桥头时发动一次攻击",
        },
    )
    assert ready_response.status_code == 200, ready_response.text

    end_response = await client.post(f"/game/combat/{sample_session.id}/end-turn", headers=headers)
    assert end_response.status_code == 200, end_response.text

    ai_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert ai_response.status_code == 200, ai_response.text
    body = ai_response.json()
    assert body["next_turn_index"] == 0
    assert body["round_number"] == 2
    assert not body.get("ready_action_results")
    assert body["expired_ready_action"]["type"] == "ready_action_expired"
    assert body["expired_ready_action"]["reason"] == "next_turn_started"
    assert body["expired_ready_action"]["actor_id"] == sample_character.id
    assert body["expired_ready_action"]["target_id"] == enemy["id"]
    assert body["expired_ready_action"]["action_type"] == "attack"
    assert body["expired_ready_action"]["condition_text"] == "当 Orc 离开桥头时发动一次攻击"
    assert "当 Orc 离开桥头时发动一次攻击" in body["ready_action_expired_log"]
    assert "失效" in body["ready_action_expired_log"]

    await db_session.refresh(ai_turn_combat)
    turn_state = ai_turn_combat.turn_states[sample_character.id]
    assert turn_state["action_used"] is False
    assert turn_state["reaction_used"] is False
    assert "ready_action" not in turn_state
    assert turn_state["ready_action_expired"]["type"] == "ready_action_expired"
    assert turn_state["ready_action_expired"]["target_id"] == enemy["id"]
    assert turn_state["ready_action_expired"]["condition_text"] == "当 Orc 离开桥头时发动一次攻击"

    log_result = await db_session.execute(select(GameLog).where(GameLog.session_id == sample_session.id))
    logs = list(log_result.scalars().all())
    assert any((log.dice_result or {}).get("type") == "ready_action_expired" for log in logs)


async def test_ready_spell_declaration_starts_concentration_hold_and_replaces_previous(
    client, db_session, sample_session, sample_character, combat_state, sample_user,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_concentration_effect_service import track_concentration_condition

    sample_character.char_class = "Wizard"
    sample_character.known_spells = ["魔法飞弹"]
    sample_character.prepared_spells = ["魔法飞弹"]
    sample_character.spell_slots = {"1st": 1}
    sample_character.concentration = "Web"

    enemy = (sample_session.game_state or {})["enemies"][0]
    enemy["conditions"] = ["restrained"]
    enemy["condition_durations"] = {"restrained": 600}
    track_concentration_condition(
        enemy,
        "restrained",
        caster_id=sample_character.id,
        spell_name="Web",
        condition_preexisting=False,
    )
    state = dict(sample_session.game_state or {})
    state["enemies"] = [enemy]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    combat_state.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": enemy["id"],
            "name": enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    combat_state.current_turn_index = 0
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "spell",
            "trigger": "target_moves",
            "target_id": enemy["id"],
            "spell_name": "魔法飞弹",
            "spell_level": 1,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    hold_name = data["ready_action"]["concentration_spell_name"]
    expected_updates = [{
        "target_id": enemy["id"],
        "target_name": enemy["name"],
        "is_enemy": True,
        "removed_conditions": ["restrained"],
        "conditions": [],
        "condition_durations": {},
    }]

    assert hold_name.startswith("准备法术: ")
    assert data["ready_action"]["requires_concentration"] is True
    assert data["actor_state"]["concentration"] == hold_name
    assert data["actor_state"]["concentration_effect_updates"] == expected_updates
    assert data["concentration_started"] is True
    assert data["concentration_effect_updates"] == expected_updates
    assert data["remaining_slots"]["1st"] == 0

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    await db_session.refresh(combat_state)
    assert sample_character.concentration == hold_name
    assert sample_character.spell_slots["1st"] == 0
    turn_state = combat_state.turn_states[sample_character.id]
    assert turn_state["ready_action"]["concentration_spell_name"] == hold_name
    cleaned_enemy = sample_session.game_state["enemies"][0]
    assert cleaned_enemy["conditions"] == []
    assert cleaned_enemy["condition_durations"] == {}
    assert "condition_sources" not in cleaned_enemy


async def test_ready_spell_dissipates_if_concentration_was_lost_before_trigger(
    db_session, sample_session, sample_character, combat_state,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_ready_action_service import (
        build_ready_spell_payload,
        resolve_ready_actions_for_movement,
    )
    from services.combat_service import CombatService

    enemy = (sample_session.game_state or {})["enemies"][0]
    enemy["hp_current"] = 9
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "hp_max": 9,
        "ac": 12,
    }
    state = dict(sample_session.game_state or {})
    state["enemies"] = [enemy]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    hold_name = "准备法术: 魔法飞弹"
    sample_character.char_class = "Wizard"
    sample_character.hp_current = 20
    sample_character.known_spells = ["魔法飞弹"]
    sample_character.prepared_spells = ["魔法飞弹"]
    sample_character.spell_slots = {"1st": 0}
    sample_character.concentration = None
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 10, "y": 5},
    }
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": True,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "ready_action": build_ready_spell_payload(
                actor_id=sample_character.id,
                actor_name=sample_character.name,
                target_id=enemy["id"],
                target_name=enemy["name"],
                spell_name="魔法飞弹",
                spell_level=1,
                slot_already_consumed=True,
                slot_key="1st",
                slots_remaining=0,
                concentration_spell_name=hold_name,
            ),
        },
    }
    flag_modified(combat_state, "entity_positions")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    results = await resolve_ready_actions_for_movement(
        db=db_session,
        session=sample_session,
        combat=combat_state,
        moving_id=enemy["id"],
        old_pos={"x": 10, "y": 5},
        new_pos={"x": 6, "y": 5},
        combat_service=CombatService(),
        has_ally_adjacent_to=lambda *_args, **_kwargs: False,
    )

    assert len(results) == 1
    result = results[0]
    assert result["applied"] is False
    assert result["reason"] == "concentration_lost"
    assert result["concentration_lost"] is True
    assert result["reaction_used"] is False
    assert result["actor_state"]["concentration"] is None

    await db_session.flush()
    turn_state = combat_state.turn_states[sample_character.id]
    assert turn_state["reaction_used"] is False
    assert "ready_action" not in turn_state
    assert turn_state["ready_action_failed"]["reason"] == "concentration_lost"
    assert sample_session.game_state["enemies"][0]["hp_current"] == 9


async def test_ready_spell_expiry_clears_concentration_hold(
    db_session, sample_session, sample_character, combat_state,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_ready_action_service import (
        apply_ready_action_expiry_to_turn_state,
        build_ready_action_expiry,
        build_ready_spell_payload,
        clear_expired_ready_spell_concentration_hold,
    )

    enemy = (sample_session.game_state or {})["enemies"][0]
    hold_name = "准备法术: 魔法飞弹"
    sample_character.concentration = hold_name
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": True,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "ready_action": build_ready_spell_payload(
                actor_id=sample_character.id,
                actor_name=sample_character.name,
                target_id=enemy["id"],
                target_name=enemy["name"],
                spell_name="魔法飞弹",
                spell_level=1,
                slot_already_consumed=True,
                slot_key="1st",
                slots_remaining=0,
                concentration_spell_name=hold_name,
            ),
        },
    }
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    expiry = build_ready_action_expiry(combat_state, sample_character.id)
    assert expiry["action_type"] == "spell"
    assert expiry["concentration_spell_name"] == hold_name

    actor_state = await clear_expired_ready_spell_concentration_hold(
        db_session,
        sample_character.id,
        expiry,
    )
    apply_ready_action_expiry_to_turn_state(combat_state, sample_character.id, expiry)

    assert actor_state["concentration"] is None
    assert expiry["actor_state"]["concentration"] is None
    assert expiry["concentration_ended"] is True

    await db_session.flush()
    assert sample_character.concentration is None
    turn_state = combat_state.turn_states[sample_character.id]
    assert "ready_action" not in turn_state
    assert turn_state["ready_action_expired"]["actor_state"]["concentration"] is None
    assert turn_state["ready_action_expired"]["slot_already_consumed"] is True


async def test_ready_spell_cantrip_triggers_when_target_moves_on_ai_turn(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import services.combat_spell_application_service as spell_application
    import services.spell_service as spell_service_module
    import api.combat.ai_turn_attack as ai_turn_attack

    sample_character.char_class = "Cleric"
    sample_character.cantrips = ["Sacred Flame"]
    sample_character.spell_slots = {}
    sample_character.derived = {
        **dict(sample_character.derived or {}),
        "spell_ability": "wis",
        "spell_save_dc": 14,
        "ability_modifiers": {
            **dict((sample_character.derived or {}).get("ability_modifiers") or {}),
            "wis": 3,
        },
    }

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    guard = {
        "id": "orc-guard",
        "name": "Orc Guard",
        "hp_current": 9,
        "max_hp": 9,
        "derived": {
            "hp_max": 9,
            "ac": 13,
            "attack_bonus": 5,
            "hit_die": 8,
            "ability_modifiers": {"str": 3, "dex": 1},
        },
        "actions": [{"name": "Club", "type": "melee_attack", "damage_dice": "1d6", "attack_bonus": 4}],
        "speed": 30,
    }
    enemy["hp_current"] = 9
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "name": enemy.get("name", "Orc"),
        "hp_max": 9,
        "ac": 13,
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
        "saving_throws": {"dex": 1},
    }
    state["enemies"] = [enemy, guard]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    ai_turn_combat.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": enemy["id"],
            "name": enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    ai_turn_combat.current_turn_index = 0
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 10, "y": 5},
        guard["id"]: {"x": 18, "y": 5},
    }
    ai_turn_combat.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_states")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "reason": "test ready spell trigger while closing distance",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 18,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 13),
            },
            damage=0,
            damage_roll={"formula": "1d8", "rolls": [0], "total": 0},
            narration="hit",
        )

    async def fake_roll_spell_save(*args, **kwargs):
        return {
            "ability": kwargs.get("save_ability"),
            "d20": 3,
            "modifier": 1,
            "total": 4,
            "dc": kwargs.get("spell_save_dc"),
            "success": False,
        }

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(spell_application, "roll_spell_save", fake_roll_spell_save)
    monkeypatch.setattr(
        spell_service_module.spell_service,
        "resolve_damage",
        lambda *_args, **_kwargs: (6, {"formula": "1d8", "rolls": [6], "total": 6}),
    )

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "spell",
            "trigger": "target_moves",
            "target_id": enemy["id"],
            "spell_name": "神圣烈焰",
            "spell_level": 0,
        },
    )
    assert ready_response.status_code == 200, ready_response.text
    assert ready_response.json()["ready_action"]["action_type"] == "spell"
    assert ready_response.json()["ready_action"]["spell_name"] == "神圣烈焰"

    end_response = await client.post(f"/game/combat/{sample_session.id}/end-turn", headers=headers)
    assert end_response.status_code == 200, end_response.text

    ai_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert ai_response.status_code == 200, ai_response.text
    body = ai_response.json()
    result = body["ready_action_results"][0]
    assert body["entity_positions"][enemy["id"]] == {"x": 6, "y": 5}
    assert result["applied"] is True
    assert result["action_type"] == "spell"
    assert result["trigger"] == "target_moves"
    assert result["actor_id"] == sample_character.id
    assert result["target_id"] == enemy["id"]
    assert result["spell_name"] == "神圣烈焰"
    assert result["damage"] == 6
    assert result["target_new_hp"] == 3
    assert result["target_state"]["save"]["success"] is False

    await db_session.refresh(ai_turn_combat)
    await db_session.refresh(sample_session)
    turn_state = ai_turn_combat.turn_states[sample_character.id]
    assert turn_state["reaction_used"] is True
    assert "ready_action" not in turn_state
    assert turn_state["ready_action_resolved"]["action_type"] == "spell"
    assert turn_state["ready_action_resolved"]["actor_state"]["concentration"] is None
    assert turn_state["ready_action_resolved"]["spell_name"] == "神圣烈焰"
    refreshed_enemy = next(e for e in sample_session.game_state["enemies"] if e["id"] == enemy["id"])
    assert refreshed_enemy["hp_current"] == 3


async def test_ready_leveled_spell_consumes_slot_at_declaration_and_not_on_trigger(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import services.spell_service as spell_service_module
    import api.combat.ai_turn_attack as ai_turn_attack

    sample_character.char_class = "Wizard"
    sample_character.known_spells = ["Magic Missile", "魔法飞弹"]
    sample_character.prepared_spells = ["Magic Missile", "魔法飞弹"]
    sample_character.cantrips = ["Fire Bolt"]
    sample_character.spell_slots = {"1st": 1}
    sample_character.derived = {
        **dict(sample_character.derived or {}),
        "spell_ability": "int",
        "spell_attack_bonus": 5,
        "spell_save_dc": 15,
        "ability_modifiers": {
            **dict((sample_character.derived or {}).get("ability_modifiers") or {}),
            "int": 5,
        },
    }

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    guard = {
        "id": "orc-guard",
        "name": "Orc Guard",
        "hp_current": 9,
        "max_hp": 9,
        "derived": {
            "hp_max": 9,
            "ac": 13,
            "attack_bonus": 5,
            "hit_die": 8,
            "ability_modifiers": {"str": 3, "dex": 1},
        },
        "actions": [{"name": "Club", "type": "melee_attack", "damage_dice": "1d6", "attack_bonus": 4}],
        "speed": 30,
    }
    enemy["hp_current"] = 9
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "name": enemy.get("name", "Orc"),
        "hp_max": 9,
        "ac": 13,
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }
    state["enemies"] = [enemy, guard]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    ai_turn_combat.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": enemy["id"],
            "name": enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
        {
            "character_id": guard["id"],
            "name": guard["name"],
            "initiative": 8,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    ai_turn_combat.current_turn_index = 0
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 10, "y": 5},
        guard["id"]: {"x": 18, "y": 5},
    }
    ai_turn_combat.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_states")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "reason": "test ready leveled spell trigger while closing distance",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": False,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 8,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 13),
            },
            damage=0,
            damage_roll={"formula": "1d8", "rolls": [0], "total": 0},
            narration="miss",
        )

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(
        spell_service_module.spell_service,
        "resolve_damage",
        lambda *_args, **_kwargs: (6, {"formula": "3d4+3", "rolls": [1, 1, 1], "total": 6}),
    )

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "spell",
            "trigger": "target_moves",
            "target_id": enemy["id"],
            "spell_name": "魔法飞弹",
            "spell_level": 1,
        },
    )
    assert ready_response.status_code == 200, ready_response.text
    ready_body = ready_response.json()
    assert ready_body["ready_action"]["action_type"] == "spell"
    assert ready_body["ready_action"]["spell_name"] == "魔法飞弹"
    assert ready_body["ready_action"]["slot_already_consumed"] is True
    assert ready_body["ready_action"]["slot_key"] == "1st"
    assert ready_body["ready_action"]["slots_remaining"] == 0
    assert ready_body["ready_action"]["requires_concentration"] is True
    assert ready_body["ready_action"]["concentration_spell_name"].startswith("准备法术: ")
    assert ready_body["actor_state"]["concentration"] == ready_body["ready_action"]["concentration_spell_name"]
    assert ready_body["concentration_started"] is True
    assert ready_body["remaining_slots"]["1st"] == 0

    await db_session.refresh(sample_character)
    await db_session.refresh(ai_turn_combat)
    assert sample_character.spell_slots["1st"] == 0
    assert sample_character.concentration == ready_body["ready_action"]["concentration_spell_name"]
    declared_turn_state = ai_turn_combat.turn_states[sample_character.id]
    assert declared_turn_state["action_used"] is True
    assert declared_turn_state["reaction_used"] is False
    assert declared_turn_state["ready_action"]["slot_already_consumed"] is True
    assert declared_turn_state["ready_action"]["concentration_spell_name"] == sample_character.concentration

    end_response = await client.post(f"/game/combat/{sample_session.id}/end-turn", headers=headers)
    assert end_response.status_code == 200, end_response.text

    ai_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert ai_response.status_code == 200, ai_response.text
    body = ai_response.json()
    result = body["ready_action_results"][0]
    assert body["entity_positions"][enemy["id"]] == {"x": 6, "y": 5}
    assert result["applied"] is True
    assert result["action_type"] == "spell"
    assert result["trigger"] == "target_moves"
    assert result["actor_id"] == sample_character.id
    assert result["target_id"] == enemy["id"]
    assert result["spell_name"] == "魔法飞弹"
    assert result["slot_already_consumed"] is True
    assert result["slot_key"] == "1st"
    assert result["slots_remaining"] == 0
    assert result["damage"] == 6
    assert result["target_new_hp"] == 3
    assert result["actor_state"]["concentration"] is None
    assert result["concentration_ended"] is True

    await db_session.refresh(sample_character)
    await db_session.refresh(ai_turn_combat)
    await db_session.refresh(sample_session)
    assert sample_character.spell_slots["1st"] == 0
    assert sample_character.concentration is None
    turn_state = ai_turn_combat.turn_states[sample_character.id]
    assert turn_state["reaction_used"] is True
    assert "ready_action" not in turn_state
    assert turn_state["ready_action_resolved"]["action_type"] == "spell"
    assert turn_state["ready_action_resolved"]["spell_name"] == "魔法飞弹"
    assert turn_state["ready_action_resolved"]["slot_already_consumed"] is True
    assert turn_state["ready_action_resolved"]["slot_key"] == "1st"
    assert turn_state["ready_action_resolved"]["slots_remaining"] == 0
    refreshed_enemy = next(e for e in sample_session.game_state["enemies"] if e["id"] == enemy["id"])
    assert refreshed_enemy["hp_current"] == 3


async def test_ready_leveled_spell_rejects_when_declaration_slot_missing(
    client, db_session, sample_session, sample_character, combat_state, sample_user,
):
    from sqlalchemy.orm.attributes import flag_modified

    sample_character.char_class = "Wizard"
    sample_character.known_spells = ["Magic Missile", "魔法飞弹"]
    sample_character.prepared_spells = ["Magic Missile", "魔法飞弹"]
    sample_character.cantrips = ["Fire Bolt"]
    sample_character.spell_slots = {"1st": 0}

    enemy = (sample_session.game_state or {})["enemies"][0]
    combat_state.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": enemy["id"],
            "name": enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    combat_state.current_turn_index = 0
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(combat_state, "turn_order")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "spell",
            "trigger": "target_moves",
            "target_id": enemy["id"],
            "spell_name": "魔法飞弹",
            "spell_level": 1,
        },
    )

    assert response.status_code == 400, response.text
    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    assert sample_character.spell_slots["1st"] == 0
    turn_state = combat_state.turn_states[sample_character.id]
    assert turn_state["action_used"] is False
    assert "ready_action" not in turn_state


async def test_ready_spell_attack_cantrip_triggers_when_target_moves_on_ai_turn(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import services.combat_spell_prepare_service as spell_prepare
    import services.spell_service as spell_service_module
    import api.combat.ai_turn_attack as ai_turn_attack

    sample_character.char_class = "Wizard"
    sample_character.cantrips = ["Fire Bolt"]
    sample_character.known_spells = ["Fire Bolt"]
    sample_character.spell_slots = {}
    sample_character.derived = {
        **dict(sample_character.derived or {}),
        "spell_ability": "int",
        "spell_attack_bonus": 25,
        "spell_save_dc": 15,
        "ability_modifiers": {
            **dict((sample_character.derived or {}).get("ability_modifiers") or {}),
            "int": 5,
        },
    }

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    guard = {
        "id": "orc-guard",
        "name": "Orc Guard",
        "hp_current": 9,
        "max_hp": 9,
        "derived": {
            "hp_max": 9,
            "ac": 13,
            "attack_bonus": 5,
            "hit_die": 8,
            "ability_modifiers": {"str": 3, "dex": 1},
        },
        "actions": [{"name": "Club", "type": "melee_attack", "damage_dice": "1d6", "attack_bonus": 4}],
        "speed": 30,
    }
    enemy["hp_current"] = 9
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "name": enemy.get("name", "Orc"),
        "hp_max": 9,
        "ac": 13,
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }
    state["enemies"] = [enemy, guard]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    ai_turn_combat.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": enemy["id"],
            "name": enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
        {
            "character_id": guard["id"],
            "name": guard["name"],
            "initiative": 8,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    ai_turn_combat.current_turn_index = 0
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 10, "y": 5},
        guard["id"]: {"x": 18, "y": 5},
    }
    ai_turn_combat.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_states")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "reason": "test ready spell attack trigger while closing distance",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": False,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 8,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 13),
            },
            damage=0,
            damage_roll={"formula": "1d8", "rolls": [0], "total": 0},
            narration="miss",
        )

    def fake_spell_attack_roll(*args, **kwargs):
        return {
            "d20": 12,
            "attack_bonus": 25,
            "condition_modifier": 0,
            "attack_total": 37,
            "target_ac": 13,
            "hit": True,
            "is_crit": False,
            "is_fumble": False,
        }

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(spell_prepare, "roll_attack", fake_spell_attack_roll)
    monkeypatch.setattr(
        spell_service_module.spell_service,
        "resolve_damage",
        lambda *_args, **_kwargs: (7, {"formula": "1d10", "rolls": [7], "total": 7}),
    )

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "spell",
            "trigger": "target_moves",
            "target_id": enemy["id"],
            "spell_name": "火焰射线",
            "spell_level": 0,
        },
    )
    assert ready_response.status_code == 200, ready_response.text
    assert ready_response.json()["ready_action"]["action_type"] == "spell"
    assert ready_response.json()["ready_action"]["spell_name"] == "火焰射线"

    end_response = await client.post(f"/game/combat/{sample_session.id}/end-turn", headers=headers)
    assert end_response.status_code == 200, end_response.text

    ai_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert ai_response.status_code == 200, ai_response.text
    body = ai_response.json()
    result = body["ready_action_results"][0]
    assert body["entity_positions"][enemy["id"]] == {"x": 6, "y": 5}
    assert result["applied"] is True
    assert result["action_type"] == "spell"
    assert result["trigger"] == "target_moves"
    assert result["actor_id"] == sample_character.id
    assert result["target_id"] == enemy["id"]
    assert result["spell_name"] == "火焰射线"
    assert result["damage"] == 7
    assert result["target_new_hp"] == 2
    assert result["hit"] is True
    assert result["attack_result"]["spell_attack"] is True
    assert result["attack_result"]["hit"] is True
    assert result["attack_result"]["attack_total"] == 37

    await db_session.refresh(ai_turn_combat)
    await db_session.refresh(sample_session)
    turn_state = ai_turn_combat.turn_states[sample_character.id]
    assert turn_state["reaction_used"] is True
    assert "ready_action" not in turn_state
    assert turn_state["ready_action_resolved"]["action_type"] == "spell"
    assert turn_state["ready_action_resolved"]["spell_name"] == "火焰射线"
    assert turn_state["ready_action_resolved"]["hit"] is True
    refreshed_enemy = next(e for e in sample_session.game_state["enemies"] if e["id"] == enemy["id"])
    assert refreshed_enemy["hp_current"] == 2


async def test_ready_move_triggers_when_target_moves_on_ai_turn(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    guard = {
        "id": "orc-guard",
        "name": "Orc Guard",
        "hp_current": 9,
        "max_hp": 9,
        "derived": {
            "hp_max": 9,
            "ac": 13,
            "attack_bonus": 5,
            "hit_die": 8,
            "ability_modifiers": {"str": 3, "dex": 1},
        },
        "actions": [{"name": "Club", "type": "melee_attack", "damage_dice": "1d6", "attack_bonus": 4}],
        "speed": 30,
    }
    enemy["hp_current"] = 9
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "name": enemy.get("name", "Orc"),
        "hp_max": 9,
        "ac": 13,
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }
    state["enemies"] = [enemy, guard]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    ai_turn_combat.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": enemy["id"],
            "name": enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
        {
            "character_id": guard["id"],
            "name": guard["name"],
            "initiative": 8,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    ai_turn_combat.current_turn_index = 0
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 10, "y": 5},
        guard["id"]: {"x": 18, "y": 5},
    }
    ai_turn_combat.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_states")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "reason": "test ready move trigger while closing distance",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": False,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 8,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 13),
            },
            damage=0,
            damage_roll={"formula": "1d8", "rolls": [0], "total": 0},
            narration="miss",
        )

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "move",
            "trigger": "target_moves",
            "target_id": enemy["id"],
            "move_to_x": 5,
            "move_to_y": 6,
        },
    )
    assert ready_response.status_code == 200, ready_response.text
    ready_body = ready_response.json()
    assert ready_body["ready_action"]["action_type"] == "move"
    assert ready_body["ready_action"]["move_to"] == {"x": 5, "y": 6}
    assert ready_body["ready_action"]["move_distance"] == 1

    end_response = await client.post(f"/game/combat/{sample_session.id}/end-turn", headers=headers)
    assert end_response.status_code == 200, end_response.text

    ai_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert ai_response.status_code == 200, ai_response.text
    body = ai_response.json()
    result = body["ready_action_results"][0]
    assert body["entity_positions"][enemy["id"]] == {"x": 6, "y": 5}
    assert body["entity_positions"][sample_character.id] == {"x": 5, "y": 6}
    assert result["applied"] is True
    assert result["action_type"] == "move"
    assert result["trigger"] == "target_moves"
    assert result["actor_id"] == sample_character.id
    assert result["target_id"] == enemy["id"]
    assert result["from"] == {"x": 5, "y": 5}
    assert result["to"] == {"x": 5, "y": 6}
    assert result["steps"] == 1
    assert result["distance_ft"] == 5

    await db_session.refresh(ai_turn_combat)
    turn_state = ai_turn_combat.turn_states[sample_character.id]
    assert turn_state["reaction_used"] is True
    assert turn_state["movement_used"] == 1
    assert "ready_action" not in turn_state
    assert turn_state["ready_action_resolved"]["action_type"] == "move"
    assert turn_state["ready_action_resolved"]["to"] == {"x": 5, "y": 6}
    assert ai_turn_combat.entity_positions[sample_character.id] == {"x": 5, "y": 6}


async def test_ready_move_into_hazard_triggers_environment_damage_on_ai_turn(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import GameLog
    from services import combat_hazard_service
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    guard = {
        "id": "orc-guard",
        "name": "Orc Guard",
        "hp_current": 9,
        "max_hp": 9,
        "derived": {
            "hp_max": 9,
            "ac": 13,
            "attack_bonus": 5,
            "hit_die": 8,
            "ability_modifiers": {"str": 3, "dex": 1},
        },
        "actions": [{"name": "Club", "type": "melee_attack", "damage_dice": "1d6", "attack_bonus": 4}],
        "speed": 30,
    }
    enemy["hp_current"] = 9
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "name": enemy.get("name", "Orc"),
        "hp_max": 9,
        "ac": 13,
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }
    state["enemies"] = [enemy, guard]
    sample_session.game_state = state
    sample_character.hp_current = 20
    flag_modified(sample_session, "game_state")

    hazard = {
        "name": "Sparking Conduit",
        "label": "Sparking Conduit",
        "damage_dice": "2d6",
        "damage_type": "lightning",
        "save_dc": 99,
        "save_ability": "dex",
        "half_on_save": True,
        "cells": ["5_6"],
    }
    ai_turn_combat.grid_data = {
        "_encounter_template": {"hazards": [hazard]},
        "5_6": {"terrain": "hazard", **hazard},
    }
    ai_turn_combat.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": enemy["id"],
            "name": enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
        {
            "character_id": guard["id"],
            "name": guard["name"],
            "initiative": 8,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    ai_turn_combat.current_turn_index = 0
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 10, "y": 5},
        guard["id"]: {"x": 18, "y": 5},
    }
    ai_turn_combat.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(ai_turn_combat, "grid_data")
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_states")

    monkeypatch.setattr(combat_hazard_service, "roll_dice", lambda notation: {
        "notation": notation,
        "rolls": [3, 3],
        "bonus": 0,
        "total": 6,
    })
    monkeypatch.setattr(combat_hazard_service, "roll_saving_throw", lambda target, ability, dc: {
        "ability": ability,
        "d20": 5,
        "modifier": 1,
        "total": 6,
        "dc": dc,
        "success": False,
    })

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "reason": "test ready move hazard trigger while closing distance",
        }

    def fake_resolve_melee_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": False,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 8,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 13),
            },
            damage=0,
            damage_roll={"formula": "1d8", "rolls": [0], "total": 0},
            narration="miss",
        )

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "move",
            "trigger": "target_moves",
            "target_id": enemy["id"],
            "move_to_x": 5,
            "move_to_y": 6,
        },
    )
    assert ready_response.status_code == 200, ready_response.text

    end_response = await client.post(f"/game/combat/{sample_session.id}/end-turn", headers=headers)
    assert end_response.status_code == 200, end_response.text

    ai_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert ai_response.status_code == 200, ai_response.text
    body = ai_response.json()
    result = body["ready_action_results"][0]
    hazard_result = result["hazard_result"]

    assert body["entity_positions"][enemy["id"]] == {"x": 6, "y": 5}
    assert body["entity_positions"][sample_character.id] == {"x": 5, "y": 6}
    assert result["applied"] is True
    assert result["action_type"] == "move"
    assert result["actor_id"] == sample_character.id
    assert result["target_id"] == enemy["id"]
    assert hazard_result["triggered"] is True
    assert hazard_result["trigger"] == "movement_hazard"
    assert hazard_result["ready_action"] is True
    assert hazard_result["ready_actor_id"] == sample_character.id
    assert hazard_result["ready_target_id"] == enemy["id"]
    assert hazard_result["cell"] == "5_6"
    assert hazard_result["target_id"] == sample_character.id
    assert hazard_result["target_type"] == "character"
    assert hazard_result["damage_type"] == "lightning"
    assert hazard_result["saving_throw"]["dc"] == 99
    assert hazard_result["saving_throw"]["success"] is False
    assert hazard_result["final_damage"] == 6
    assert hazard_result["hp_before"] == 20
    assert hazard_result["hp_after"] == 14
    assert result["actor_state"]["target_id"] == sample_character.id
    assert result["actor_state"]["hp_current"] == 14

    await db_session.refresh(sample_character)
    await db_session.refresh(ai_turn_combat)
    assert sample_character.hp_current == 14
    turn_state = ai_turn_combat.turn_states[sample_character.id]
    assert turn_state["reaction_used"] is True
    assert turn_state["movement_used"] == 1
    assert turn_state["ready_action_resolved"]["action_type"] == "move"
    assert turn_state["ready_action_resolved"]["hazard_result"]["cell"] == "5_6"
    assert turn_state["ready_action_resolved"]["actor_state"]["hp_current"] == 14

    log_result = await db_session.execute(select(GameLog).where(GameLog.session_id == sample_session.id))
    logs = list(log_result.scalars())
    assert any(
        isinstance(log.dice_result, dict)
        and (log.dice_result.get("hazard") or {}).get("ready_action") is True
        and (log.dice_result.get("hazard") or {}).get("cell") == "5_6"
        for log in logs
    )


async def test_ready_move_provokes_opportunity_attack_on_ai_turn(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import GameLog
    from services.combat_service import AttackResult
    from services import combat_opportunity_attack_service as opportunity
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    guard = {
        "id": "ready-move-opportunity-guard",
        "name": "Ready Move Opportunity Guard",
        "hp_current": 18,
        "max_hp": 18,
        "derived": {
            "hp_max": 18,
            "ac": 13,
            "attack_bonus": 30,
            "hit_die": 4,
            "ability_modifiers": {"str": 3, "dex": 1},
            "damage_type": "slashing",
        },
        "actions": [{"name": "Reaction Blade", "type": "melee_attack", "damage_dice": "1d4", "attack_bonus": 30}],
        "speed": 30,
    }
    enemy["hp_current"] = 9
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "name": enemy.get("name", "Orc"),
        "hp_max": 9,
        "ac": 13,
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }
    state["enemies"] = [enemy, guard]
    sample_session.game_state = state
    sample_character.hp_current = 20
    flag_modified(sample_session, "game_state")

    ai_turn_combat.turn_order = [
        {
            "character_id": sample_character.id,
            "name": sample_character.name,
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": enemy["id"],
            "name": enemy["name"],
            "initiative": 12,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    ai_turn_combat.current_turn_index = 0
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        enemy["id"]: {"x": 10, "y": 5},
        guard["id"]: {"x": 5, "y": 4},
    }
    ai_turn_combat.turn_states = {
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
        guard["id"]: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_states")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "reason": "test ready move opportunity trigger while closing distance",
        }

    def fake_ai_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": False,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 8,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 13),
            },
            damage=0,
            damage_roll={"formula": "1d8", "rolls": [0], "total": 0},
            narration="miss",
        )

    def fake_opportunity_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 35,
                "target_ac": kwargs.get("target_derived", {}).get("ac", 13),
            },
            damage=4,
            damage_roll={"formula": "1d4", "rolls": [4], "total": 4},
            narration="opportunity hit",
        )

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_ai_attack)
    monkeypatch.setattr(opportunity.svc, "resolve_melee_attack", fake_opportunity_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)

    headers = await _auth_headers(client, sample_user)
    ready_response = await client.post(
        f"/game/combat/{sample_session.id}/ready-action",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "action_type": "move",
            "trigger": "target_moves",
            "target_id": enemy["id"],
            "move_to_x": 5,
            "move_to_y": 6,
        },
    )
    assert ready_response.status_code == 200, ready_response.text

    end_response = await client.post(f"/game/combat/{sample_session.id}/end-turn", headers=headers)
    assert end_response.status_code == 200, end_response.text

    ai_response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)
    assert ai_response.status_code == 200, ai_response.text
    body = ai_response.json()
    result = body["ready_action_results"][0]
    ready_opportunity = result["opportunity_attacks"][0]

    assert body["entity_positions"][enemy["id"]] == {"x": 6, "y": 5}
    assert body["entity_positions"][sample_character.id] == {"x": 5, "y": 6}
    assert result["applied"] is True
    assert result["action_type"] == "move"
    assert result["actor_id"] == sample_character.id
    assert result["target_id"] == enemy["id"]
    assert ready_opportunity["attacker"] == guard["name"]
    assert ready_opportunity["target"] == sample_character.name
    assert ready_opportunity["damage"] == 4
    assert ready_opportunity["attack_result"]["hit"] is True
    assert ready_opportunity["attack_result"]["attack_total"] == 35
    assert result["actor_state"]["target_id"] == sample_character.id
    assert result["actor_state"]["hp_current"] == 16

    await db_session.refresh(sample_character)
    await db_session.refresh(ai_turn_combat)
    assert sample_character.hp_current == 16
    guard_turn_state = ai_turn_combat.turn_states[guard["id"]]
    assert result["turn_state"]["reaction_used"] is True
    assert result["turn_state"]["movement_used"] == 1
    assert result["turn_state"]["ready_action_resolved"]["action_type"] == "move"
    assert result["turn_state"]["ready_action_resolved"]["opportunity_attacks"][0]["attacker"] == guard["name"]
    assert result["turn_state"]["ready_action_resolved"]["actor_state"]["hp_current"] == 16
    assert guard_turn_state["reaction_used"] is True

    log_result = await db_session.execute(select(GameLog).where(GameLog.session_id == sample_session.id))
    logs = list(log_result.scalars())
    assert any(
        isinstance(log.dice_result, dict)
        and log.dice_result.get("opportunity") is True
        and (log.dice_result.get("attack") or {}).get("attack_total") == 35
        for log in logs
    )
    assert any(
        isinstance(log.dice_result, dict)
        and log.dice_result.get("type") == "ready_action"
        and (log.dice_result.get("opportunity_attacks") or [{}])[0].get("attacker") == guard["name"]
        for log in logs
    )


async def test_ai_movement_out_of_companion_reach_triggers_companion_opportunity_attack(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import Character
    from services.combat_service import AttackResult
    from services import combat_opportunity_attack_service as opportunity
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    companion = Character(
        id=str(_uuid.uuid4()),
        user_id=None,
        session_id=sample_session.id,
        is_player=False,
        name="Melee Companion",
        race="Human",
        char_class="Fighter",
        level=2,
        ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        derived={"hp_max": 22, "ac": 15, "attack_bonus": 6, "hit_die": 8, "ability_modifiers": {"str": 3, "dex": 1}},
        hp_current=22,
    )
    db_session.add(companion)

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["hp_current"] = 9
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "name": enemy.get("name", "Orc"),
        "hp_max": 9,
        "ac": 13,
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }
    state["companion_ids"] = [companion.id]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    ai_turn_combat.entity_positions = {
        enemy["id"]: {"x": 6, "y": 5},
        companion.id: {"x": 5, "y": 5},
        sample_character.id: {"x": 12, "y": 5},
    }
    ai_turn_combat.turn_order = [
        {"character_id": enemy["id"], "name": enemy["name"], "initiative": 18, "is_player": False, "is_enemy": True},
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 12, "is_player": True, "is_enemy": False},
    ]
    ai_turn_combat.turn_states = {
        companion.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "turn_states")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "reason": "test provoke companion opportunity while switching targets",
        }

    def fake_ai_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": False,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 11,
                "target_ac": 14,
            },
            damage=0,
            damage_roll={"formula": "1d8", "rolls": [], "total": 0},
            narration="miss",
        )

    def fake_opportunity_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 18,
                "target_ac": 13,
            },
            damage=4,
            damage_roll={"formula": "1d8", "rolls": [4], "total": 4},
            narration="opportunity hit",
        )

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_ai_attack)
    monkeypatch.setattr(opportunity.svc, "resolve_melee_attack", fake_opportunity_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["target_id"] == sample_character.id
    assert body["entity_positions"][enemy["id"]] == {"x": 11, "y": 5}
    assert body["opportunity_attacks"][0]["attacker"] == companion.name
    assert body["opportunity_attacks"][0]["target"] == enemy["name"]
    assert body["opportunity_attacks"][0]["damage"] == 4
    assert body["opportunity_attacks"][0]["attack_result"]["hit"] is True

    await db_session.refresh(ai_turn_combat)
    await db_session.refresh(sample_session)
    assert ai_turn_combat.turn_states[companion.id]["reaction_used"] is True
    assert ai_turn_combat.turn_states[enemy["id"]]["movement_used"] == 5
    refreshed_enemy = next(e for e in sample_session.game_state["enemies"] if e["id"] == enemy["id"])
    assert refreshed_enemy["hp_current"] == 5


async def test_ai_movement_with_flyby_does_not_trigger_companion_opportunity_attack(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from models import Character
    from services.combat_service import AttackResult
    from services import combat_opportunity_attack_service as opportunity
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    companion = Character(
        id=str(_uuid.uuid4()),
        user_id=None,
        session_id=sample_session.id,
        is_player=False,
        name="Melee Companion",
        race="Human",
        char_class="Fighter",
        level=2,
        ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        derived={"hp_max": 22, "ac": 15, "attack_bonus": 6, "hit_die": 8, "ability_modifiers": {"str": 3, "dex": 1}},
        hp_current=22,
    )
    db_session.add(companion)

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["hp_current"] = 9
    enemy["traits"] = [{"name": "Flyby", "description": "Does not provoke opportunity attacks."}]
    enemy["derived"] = {
        **dict(enemy.get("derived") or {}),
        "name": enemy.get("name", "Orc"),
        "hp_max": 9,
        "ac": 13,
        "attack_bonus": 5,
        "hit_die": 8,
        "ability_modifiers": {"str": 3, "dex": 1},
    }
    state["companion_ids"] = [companion.id]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    ai_turn_combat.entity_positions = {
        enemy["id"]: {"x": 6, "y": 5},
        companion.id: {"x": 5, "y": 5},
        sample_character.id: {"x": 12, "y": 5},
    }
    ai_turn_combat.turn_order = [
        {"character_id": enemy["id"], "name": enemy["name"], "initiative": 18, "is_player": False, "is_enemy": True},
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 12, "is_player": True, "is_enemy": False},
    ]
    ai_turn_combat.turn_states = {
        companion.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
        sample_character.id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
        },
    }
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "turn_states")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "reason": "test flyby movement does not provoke opportunity attacks",
        }

    def fake_ai_attack(*args, **kwargs):
        return AttackResult(
            attack_roll={
                "hit": False,
                "is_crit": False,
                "is_fumble": False,
                "attack_total": 11,
                "target_ac": 14,
            },
            damage=0,
            damage_roll={"formula": "1d8", "rolls": [], "total": 0},
            narration="miss",
        )

    def fail_opportunity_attack(*args, **kwargs):
        raise AssertionError("Flyby movement must not resolve opportunity attacks")

    async def fake_narrate_batch(actions):
        return ["" for _action in actions]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_ai_attack)
    monkeypatch.setattr(opportunity.svc, "resolve_melee_attack", fail_opportunity_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["target_id"] == sample_character.id
    assert body["entity_positions"][enemy["id"]] == {"x": 11, "y": 5}
    assert body["opportunity_attacks"] == []

    await db_session.refresh(ai_turn_combat)
    await db_session.refresh(sample_session)
    assert ai_turn_combat.turn_states[companion.id]["reaction_used"] is False
    assert ai_turn_combat.turn_states[enemy["id"]]["movement_used"] == 5
    refreshed_enemy = next(e for e in sample_session.game_state["enemies"] if e["id"] == enemy["id"])
    assert refreshed_enemy["hp_current"] == 9


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
    assert body["special_action"] == {
        "ability_id": "breath",
        "name": "Fire Breath",
        "recharge": "5",
        "threshold": 5,
        "area": "15 ft cone",
        "targeting": None,
        "damage_dice": "6d6",
        "damage_type": "fire",
        "save": "dex",
        "save_dc": 13,
        "half_on_save": True,
        "available": False,
    }
    assert body["damage"] == 27
    assert [item["target_id"] for item in body["target_results"]] == [sample_character.id, ally.id]
    assert [item["is_enemy"] for item in body["target_results"]] == [False, False]
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
    legendary_enemy = {
        "id": "counterspell-dragon-1",
        "name": "Counterspell Watcher",
        "hp_current": 80,
        "max_hp": 80,
        "derived": {"hp_max": 80, "ac": 18, "ability_modifiers": {"str": 6, "dex": 0}},
        "legendary_actions": [
            {"id": "tail", "name": "Tail Attack", "cost": 1, "description": "Tail sweep."},
        ],
        "legendary_action_uses": 3,
        "legendary_action_uses_remaining": 2,
        "identified": True,
    }
    state["enemies"] = [enemy, legendary_enemy]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    ai_turn_combat.turn_order = [
        {"character_id": enemy["id"], "name": enemy["name"], "initiative": 18, "is_player": False, "is_enemy": True},
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 12, "is_player": True, "is_enemy": False},
        {"character_id": legendary_enemy["id"], "name": legendary_enemy["name"], "initiative": 10, "is_player": False, "is_enemy": True},
    ]
    ai_turn_combat.entity_positions = {
        enemy["id"]: {"x": 1, "y": 1},
        sample_character.id: {"x": 5, "y": 5},
        legendary_enemy["id"]: {"x": 6, "y": 5},
    }
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")
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
    assert reaction_body["dice_result"]["type"] == "reaction"
    assert reaction_body["dice_result"]["reaction_type"] == "counterspell"
    assert reaction_body["dice_result"]["spell_cancelled"] is True
    assert reaction_body["dice_result"]["slot_used"] == "3rd"
    assert reaction_body["special_action"] == reaction_body["dice_result"]
    assert reaction_body["lair_action_prompt"] is None
    prompt = reaction_body["legendary_action_prompt"]
    assert prompt["trigger"] == "legendary_action"
    assert prompt["trigger_entity_id"] == enemy["id"]
    assert prompt["actor_id"] == legendary_enemy["id"]
    assert [action["id"] for action in prompt["actions"]] == ["tail"]

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


async def test_companion_ai_spell_victory_ends_combat(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_spell as ai_turn_spell
    from models import Character

    companion = Character(
        id=str(_uuid.uuid4()),
        session_id=sample_session.id,
        user_id=None,
        is_player=False,
        name="Party Mage",
        race="Elf",
        char_class="Wizard",
        level=3,
        background="Sage",
        ability_scores={"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 10},
        derived={
            "hp_max": 8,
            "ac": 12,
            "spell_ability": "int",
            "ability_modifiers": {"int": 3, "dex": 2},
            "spell_save_dc": 13,
            "spell_attack_bonus": 5,
        },
        hp_current=8,
        known_spells=["魔法飞弹"],
        spell_slots={"1st": 1},
        conditions=[],
        condition_durations={},
    )
    db_session.add(companion)

    state = sample_session.game_state or {}
    state["companion_ids"] = [companion.id]
    state["enemies"][0]["hp_current"] = 1
    state["enemies"][0]["derived"] = {
        **state["enemies"][0].get("derived", {}),
        "hp_max": 9,
        "ac": 13,
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    ai_turn_combat.turn_order = [
        {"character_id": companion.id, "name": companion.name, "initiative": 18, "is_player": False, "is_enemy": False},
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 12, "is_player": True, "is_enemy": False},
    ]
    ai_turn_combat.entity_positions = {
        companion.id: {"x": 1, "y": 1},
        "orc-1": {"x": 2, "y": 1},
    }
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "spell",
            "target_id": "orc-1",
            "action_name": "魔法飞弹",
            "spell_level": 1,
            "reason": "finish the fight",
        }

    async def fake_narrate_action(**_kwargs):
        return ""

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_spell, "narrate_action", fake_narrate_action)

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["combat_over"] is True
    assert body["outcome"] == "victory"
    assert body["target_new_hp"] == 0

    await db_session.refresh(sample_session)
    await db_session.refresh(companion)
    assert sample_session.combat_active is False
    assert companion.spell_slots["1st"] == 0
    deleted = await db_session.execute(
        select(CombatState).where(CombatState.id == ai_turn_combat.id)
    )
    assert deleted.scalar_one_or_none() is None


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


async def test_ai_attack_breaking_concentration_returns_tracked_effect_updates(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    from services.combat_concentration_effect_service import track_concentration_condition
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    state = sample_session.game_state or {}
    attacker = state["enemies"][0]
    attacker["name"] = "Orc Breaker"
    attacker["actions"] = [{"name": "Club", "type": "melee_attack", "damage_dice": "1d6", "attack_bonus": 5}]
    webbed_enemy = {
        "id": "webbed-goblin",
        "name": "Webbed Goblin",
        "hp_current": 7,
        "max_hp": 7,
        "conditions": ["restrained"],
        "condition_durations": {"restrained": 600},
        "derived": {"hp_max": 7, "ac": 12},
    }
    track_concentration_condition(
        webbed_enemy,
        "restrained",
        caster_id=sample_character.id,
        spell_name="Web",
        condition_preexisting=False,
    )
    state["enemies"] = [attacker, webbed_enemy]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.hp_current = 12
    sample_character.concentration = "Web"
    sample_character.conditions = []
    sample_character.condition_durations = {}
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "action_name": "Club",
            "reason": "test concentration cleanup",
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
            damage=4,
            damage_roll={"formula": "1d6", "rolls": [4], "total": 4},
            narration="hit",
        )

    async def fake_narrate_batch(actions):
        return ["Orc Breaker hits."]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(
        "services.combat_concentration_service.svc.check_concentration",
        lambda **_kwargs: {
            "spell_name": "Web",
            "dc": 10,
            "broke": True,
            "roll_result": {"d20": 1, "modifier": 2, "total": 3},
        },
    )

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["concentration_check"]["broke"] is True
    assert body["concentration_check"]["spell_name"] == "Web"
    assert body["target_state"]["concentration"] is None
    assert body["target_state"]["concentration_effect_updates"] == [{
        "target_id": "webbed-goblin",
        "target_name": "Webbed Goblin",
        "is_enemy": True,
        "removed_conditions": ["restrained"],
        "conditions": [],
        "condition_durations": {},
    }]

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    assert sample_character.concentration is None
    cleaned = next(enemy for enemy in sample_session.game_state["enemies"] if enemy["id"] == "webbed-goblin")
    assert cleaned["conditions"] == []
    assert cleaned["condition_durations"] == {}


async def test_ai_attack_breaking_ready_spell_concentration_clears_ready_action_immediately(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_ready_action_service import build_ready_spell_payload
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack

    state = sample_session.game_state or {}
    attacker = state["enemies"][0]
    attacker["name"] = "Orc Breaker"
    attacker["actions"] = [{"name": "Club", "type": "melee_attack", "damage_dice": "1d6", "attack_bonus": 5}]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    hold_name = "准备法术: 魔法飞弹"
    sample_character.char_class = "Wizard"
    sample_character.hp_current = 12
    sample_character.known_spells = ["魔法飞弹"]
    sample_character.prepared_spells = ["魔法飞弹"]
    sample_character.spell_slots = {"1st": 0}
    sample_character.concentration = hold_name
    ai_turn_combat.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        attacker["id"]: {"x": 6, "y": 5},
    }
    ai_turn_combat.turn_states = {
        sample_character.id: {
            "action_used": True,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "ready_action": build_ready_spell_payload(
                actor_id=sample_character.id,
                actor_name=sample_character.name,
                target_id=attacker["id"],
                target_name=attacker["name"],
                spell_name="魔法飞弹",
                spell_level=1,
                slot_already_consumed=True,
                slot_key="1st",
                slots_remaining=0,
                concentration_spell_name=hold_name,
            ),
        },
    }
    flag_modified(ai_turn_combat, "entity_positions")
    flag_modified(ai_turn_combat, "turn_states")
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "action_name": "Club",
            "reason": "test ready spell concentration break",
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
            damage=4,
            damage_roll={"formula": "1d6", "rolls": [4], "total": 4},
            narration="hit",
        )

    async def fake_narrate_batch(actions):
        return ["Orc Breaker hits."]

    monkeypatch.setattr(ai_agent, "get_ai_decision", fake_get_ai_decision)
    monkeypatch.setattr(ai_agent, "calc_difficulty", lambda parsed: "normal")
    monkeypatch.setattr(ai_turn_attack.svc, "resolve_melee_attack", fake_resolve_melee_attack)
    monkeypatch.setattr(ai_turn_attack, "narrate_batch", fake_narrate_batch)
    monkeypatch.setattr(
        "services.combat_concentration_service.svc.check_concentration",
        lambda **_kwargs: {
            "spell_name": hold_name,
            "dc": 10,
            "broke": True,
            "roll_result": {"d20": 1, "modifier": 2, "total": 3},
        },
    )

    headers = await _auth_headers(client, sample_user)
    response = await client.post(f"/game/combat/{sample_session.id}/ai-turn", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["concentration_check"]["broke"] is True
    assert body["concentration_check"]["spell_name"] == hold_name
    assert body["target_state"]["concentration"] is None
    assert body["target_state"]["ready_action_failed"]["reason"] == "concentration_lost"
    assert body["target_state"]["ready_action_failed"]["spell_name"] == "魔法飞弹"
    assert body["target_state"]["ready_action_failed"]["slot_already_consumed"] is True

    await db_session.refresh(sample_character)
    await db_session.refresh(ai_turn_combat)
    assert sample_character.concentration is None
    assert sample_character.spell_slots["1st"] == 0
    assert "ready_action" not in ai_turn_combat.turn_states.get(sample_character.id, {})


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


async def test_ai_attack_offers_uncanny_dodge_and_reaction_restores_half_damage(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack
    import api.combat.reactions as reactions

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]

    sample_character.char_class = "Rogue"
    sample_character.level = 5
    sample_character.hp_current = 12
    sample_character.known_spells = []
    sample_character.spell_slots = {}
    await db_session.commit()

    async def fake_get_ai_decision(**kwargs):
        return {
            "action_type": "attack",
            "target_id": sample_character.id,
            "action_name": "Knife Twist",
            "reason": "test uncanny dodge reaction",
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
            damage_roll={"formula": "1d8+1", "rolls": [8], "total": 9},
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
    dodge = next(
        reaction
        for reaction in prompt_body["reaction_prompt"]["available_reactions"]
        if reaction["type"] == "uncanny_dodge"
    )
    assert dodge["damage_prevented"] == 5
    assert dodge["reduced_damage"] == 4

    reaction = await client.post(
        f"/game/combat/{sample_session.id}/reaction",
        headers=headers,
        json={
            "reaction_type": "uncanny_dodge",
            "target_id": enemy["id"],
            "character_id": sample_character.id,
        },
    )
    assert reaction.status_code == 200, reaction.text
    reaction_body = reaction.json()
    assert reaction_body["reaction_effect"]["damage_halved"] is True
    assert reaction_body["reaction_effect"]["damage_prevented"] == 5
    assert reaction_body["reaction_effect"]["hp_restored"] == 5

    await db_session.refresh(sample_character)
    await db_session.refresh(ai_turn_combat)
    assert sample_character.hp_current == 8
    assert ai_turn_combat.turn_states[sample_character.id]["reaction_used"] is True
    assert "pending_attack_reaction" not in ai_turn_combat.turn_states[sample_character.id]


async def test_attack_reaction_resolution_surfaces_deferred_lair_action_prompt(
    client, db_session, sample_session, sample_character, ai_turn_combat, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_service import AttackResult
    import services.ai_combat_agent as ai_agent
    import api.combat.ai_turn_attack as ai_turn_attack
    import api.combat.reactions as reactions

    state = sample_session.game_state or {}
    enemy = state["enemies"][0]
    enemy["name"] = "Flame Lair Keeper"
    enemy["derived"] = {
        **enemy.get("derived", {}),
        "damage_type": "fire",
    }
    enemy["lair_actions"] = [{
        "id": "seismic-pulse",
        "name": "Seismic Pulse",
        "area": "15 ft radius",
        "targets": "multiple",
        "save": "dex",
        "save_dc": 15,
        "damage_dice": "2d6",
        "damage_type": "bludgeoning",
        "half_on_save": True,
    }]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")

    ai_turn_combat.turn_order = [
        {"character_id": enemy["id"], "name": enemy["name"], "initiative": 24, "is_player": False, "is_enemy": True},
        {"character_id": sample_character.id, "name": sample_character.name, "initiative": 18, "is_player": True, "is_enemy": False},
    ]
    ai_turn_combat.current_turn_index = 0
    ai_turn_combat.round_number = 1
    ai_turn_combat.entity_positions = {
        enemy["id"]: {"x": 6, "y": 5},
        sample_character.id: {"x": 5, "y": 5},
    }
    flag_modified(ai_turn_combat, "turn_order")
    flag_modified(ai_turn_combat, "entity_positions")

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
            "reason": "test deferred lair after reaction",
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
    prompt_response = await client.post(
        f"/game/combat/{sample_session.id}/ai-turn",
        headers=headers,
        json={"expected_turn_token": f"1:0:{enemy['id']}"},
    )
    assert prompt_response.status_code == 200, prompt_response.text
    prompt_body = prompt_response.json()
    assert prompt_body["player_can_react"] is True
    assert prompt_body.get("lair_action_prompt") is None
    absorb = next(
        reaction
        for reaction in prompt_body["reaction_prompt"]["available_reactions"]
        if reaction["type"] == "absorb_elements"
    )
    assert absorb["damage_type"] == "fire"

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
    assert reaction_body["reaction_effect"]["hp_restored"] == 5
    prompt = reaction_body["lair_action_prompt"]
    assert prompt["trigger"] == "lair_action"
    assert prompt["timing"] == "initiative_count_20"
    assert prompt["round_number"] == 1
    assert "initiative count 20" in prompt["context"]
    assert prompt["actions"][0]["id"] == "seismic-pulse"
    assert prompt["actions"][0]["target_ids"] == [sample_character.id]

    await db_session.refresh(sample_session)
    await db_session.refresh(ai_turn_combat)
    assert sample_session.game_state["lair_action_prompted_round"] == 1
    assert ai_turn_combat.current_turn_index == 1
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
    assert data["damage_roll"] == {"formula": "1d6+3", "rolls": [2], "total": 5}
    assert data["damage_type"]
    assert data["total_damage"] == data["damage"]
    assert data["target_name"]
    assert any("暗杀暴击" in note for note in data["extra_damage_notes"])


async def test_attack_roll_then_damage_roll_applies_damage(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
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
    assert attack_data["action"] == "attack_roll"
    assert attack_data["dice_result"]["type"] == "attack_prepare"
    assert attack_data["dice_result"]["actor_id"] == sample_character.id
    assert attack_data["dice_result"]["actor_name"] == sample_character.name
    assert attack_data["dice_result"]["target_id"] == "goblin-1"
    assert attack_data["dice_result"]["target_name"] == attack_data["target_name"]
    assert attack_data["dice_result"]["attack"]["d20"] == 15
    assert attack_data["dice_result"]["attack"]["hit"] is True
    assert attack_data["dice_result"]["attack"]["target_conditions"] == []
    assert attack_data["dice_result"]["damage_dice"] == attack_data["damage_dice"]
    assert attack_data["special_action"] == attack_data["dice_result"]
    assert "turn_state" not in attack_data["dice_result"]
    attack_prepare_log = (
        await db_session.execute(
            select(GameLog).where(GameLog.session_id == sample_session.id)
        )
    ).scalars().all()
    attack_prepare_log = [
        log for log in attack_prepare_log
        if isinstance(log.dice_result, dict) and log.dice_result.get("type") == "attack_prepare"
    ]
    assert len(attack_prepare_log) == 1
    assert attack_prepare_log[0].content == attack_data["narration"]
    assert attack_prepare_log[0].dice_result == attack_data["dice_result"]

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


async def test_paladin_damage_roll_opens_trusted_pending_smite_window(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified

    _patch_smite_narration(monkeypatch)
    headers = await _auth_headers(client, sample_user)
    sample_character.char_class = "Paladin"
    sample_character.spell_slots = {"1st": 1}
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "hp_current": 20,
        "hp_max": 20,
        "derived": {**(enemies[0].get("derived") or {}), "hp_max": 20, "ac": 15},
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    attack = await client.post(
        f"/game/combat/{sample_session.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "target_id": "goblin-1",
            "action_type": "melee",
            "d20_value": 20,
        },
    )
    assert attack.status_code == 200, attack.text
    assert attack.json()["is_crit"] is True

    damage = await client.post(
        f"/game/combat/{sample_session.id}/damage-roll",
        headers=headers,
        json={
            "pending_attack_id": attack.json()["pending_attack_id"],
            "damage_values": [1, 1],
        },
    )
    assert damage.status_code == 200, damage.text
    damage_data = damage.json()
    assert damage_data["can_smite"] is True
    pending_smite = damage_data["turn_state"]["pending_smite"]
    assert pending_smite["target_id"] == "goblin-1"
    assert pending_smite["target_name"]
    assert pending_smite["is_crit"] is True
    assert pending_smite["source"] == "damage_roll"
    assert pending_smite["used"] is False
    assert pending_smite["target_is_undead_or_fiend"] is False

    smite = await client.post(
        f"/game/combat/{sample_session.id}/smite",
        headers=headers,
        json={
            "slot_level": 1,
            "target_id": "goblin-1",
            "is_crit": True,
            "damage_values": [1, 1, 1, 1],
        },
    )
    assert smite.status_code == 200, smite.text
    assert smite.json()["smite_dice"] == "4d8"

    await db_session.refresh(combat_state)
    assert "pending_smite" not in combat_state.turn_states[sample_character.id]


async def test_smite_derives_undead_or_fiend_bonus_from_target_data(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified

    _patch_smite_narration(monkeypatch)
    headers = await _auth_headers(client, sample_user)
    sample_character.char_class = "Paladin"
    sample_character.spell_slots = {"1st": 1}
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "type": "undead",
        "hp_current": 20,
        "hp_max": 20,
        "derived": {**(enemies[0].get("derived") or {}), "hp_max": 20, "ac": 15},
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

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

    damage = await client.post(
        f"/game/combat/{sample_session.id}/damage-roll",
        headers=headers,
        json={
            "pending_attack_id": attack.json()["pending_attack_id"],
            "damage_values": [1],
        },
    )
    assert damage.status_code == 200, damage.text
    pending_smite = damage.json()["turn_state"]["pending_smite"]
    assert pending_smite["target_is_undead_or_fiend"] is True

    smite = await client.post(
        f"/game/combat/{sample_session.id}/smite",
        headers=headers,
        json={
            "slot_level": 1,
            "target_is_undead": False,
            "target_id": "goblin-1",
            "is_crit": False,
            "damage_values": [1, 1, 1],
        },
    )
    assert smite.status_code == 200, smite.text
    data = smite.json()
    assert data["smite_damage"] == 3
    assert data["smite_dice"] == "3d8"
    assert data["target_is_undead_or_fiend"] is True


async def test_direct_attack_pending_smite_marks_undead_or_fiend_target(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified

    _patch_smite_narration(monkeypatch)
    headers = await _auth_headers(client, sample_user)
    sample_character.char_class = "Paladin"
    sample_character.derived = {
        **(sample_character.derived or {}),
        "attack_bonus": 25,
        "hit_die": 10,
        "ability_modifiers": {
            **(sample_character.derived or {}).get("ability_modifiers", {}),
            "str": 3,
        },
    }
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "type": "fiend",
        "hp_current": 20,
        "hp_max": 20,
        "derived": {**(enemies[0].get("derived") or {}), "hp_max": 20, "ac": 15},
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_character, "derived")
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    action = await client.post(
        f"/game/combat/{sample_session.id}/action",
        headers=headers,
        json={
            "action_text": "attack",
            "target_id": "goblin-1",
        },
    )
    assert action.status_code == 200, action.text
    data = action.json()
    pending_smite = data["turn_state"]["pending_smite"]
    assert pending_smite["source"] == "direct_attack"
    assert pending_smite["target_id"] == "goblin-1"
    assert pending_smite["target_is_undead_or_fiend"] is True


async def test_smite_ignores_client_undead_bonus_for_ordinary_target(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified

    _patch_smite_narration(monkeypatch)
    headers = await _auth_headers(client, sample_user)
    sample_character.char_class = "Paladin"
    sample_character.spell_slots = {"1st": 1}
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "type": "humanoid",
        "hp_current": 20,
        "hp_max": 20,
        "derived": {**(enemies[0].get("derived") or {}), "hp_max": 20},
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    combat_state.turn_states = {
        sample_character.id: {
            "pending_smite": {
                "target_id": "goblin-1",
                "target_name": "Goblin",
                "is_crit": False,
                "source": "test",
                "used": False,
                "target_is_undead_or_fiend": True,
            },
        },
    }
    flag_modified(sample_session, "game_state")
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    smite = await client.post(
        f"/game/combat/{sample_session.id}/smite",
        headers=headers,
        json={
            "slot_level": 1,
            "target_is_undead": True,
            "target_id": "goblin-1",
            "is_crit": False,
            "damage_values": [1, 1],
        },
    )
    assert smite.status_code == 200, smite.text
    data = smite.json()
    assert data["smite_damage"] == 2
    assert data["smite_dice"] == "2d8"
    assert data["target_is_undead_or_fiend"] is False


async def test_attack_roll_response_surfaces_cancelled_advantage_sources(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    headers = await _auth_headers(client, sample_user)
    sample_character.conditions = ["poisoned"]
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "conditions": ["restrained"],
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    response = await client.post(
        f"/game/combat/{sample_session.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "target_id": "goblin-1",
            "action_type": "melee",
            "d20_value": 12,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["advantage"] is False
    assert data["disadvantage"] is False
    assert data["roll_state"] == "cancelled"
    assert data["advantage_sources"] == ["target restrained"]
    assert data["disadvantage_sources"] == ["attacker poisoned"]
    assert data["turn_state"]["pending_attack"]["roll_state"] == "cancelled"
    assert data["turn_state"]["pending_attack"]["advantage_sources"] == ["target restrained"]
    assert data["turn_state"]["pending_attack"]["disadvantage_sources"] == ["attacker poisoned"]


async def test_attack_roll_response_cancels_blinded_attacker_and_blinded_target(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    headers = await _auth_headers(client, sample_user)
    sample_character.conditions = ["blinded"]
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "name": "Blinded Goblin",
        "conditions": ["blinded"],
        "derived": {
            **(enemies[0].get("derived") or {}),
            "ac": 99,
        },
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    response = await client.post(
        f"/game/combat/{sample_session.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "target_id": "goblin-1",
            "action_type": "melee",
            "d20_value": 8,
            "second_d20_value": 19,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["advantage"] is False
    assert data["disadvantage"] is False
    assert data["roll_state"] == "cancelled"
    assert data["advantage_sources"] == ["target blinded"]
    assert data["disadvantage_sources"] == ["attacker blinded"]
    assert data["d20"] == 8
    assert data["d20_rolls"] is None
    assert data["turn_state"]["pending_attack"]["roll_state"] == "cancelled"
    assert data["turn_state"]["pending_attack"]["advantage_sources"] == ["target blinded"]
    assert data["turn_state"]["pending_attack"]["disadvantage_sources"] == ["attacker blinded"]


async def test_attack_roll_response_cancels_invisible_attacker_and_invisible_target(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    headers = await _auth_headers(client, sample_user)
    sample_character.conditions = ["invisible"]
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "name": "Invisible Goblin",
        "conditions": ["invisible"],
        "derived": {
            **(enemies[0].get("derived") or {}),
            "ac": 99,
        },
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    response = await client.post(
        f"/game/combat/{sample_session.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "target_id": "goblin-1",
            "action_type": "melee",
            "d20_value": 9,
            "second_d20_value": 18,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["advantage"] is False
    assert data["disadvantage"] is False
    assert data["roll_state"] == "cancelled"
    assert data["advantage_sources"] == ["attacker invisible"]
    assert data["disadvantage_sources"] == ["target invisible"]
    assert data["d20"] == 9
    assert data["d20_rolls"] is None
    assert data["turn_state"]["pending_attack"]["roll_state"] == "cancelled"
    assert data["turn_state"]["pending_attack"]["advantage_sources"] == ["attacker invisible"]
    assert data["turn_state"]["pending_attack"]["disadvantage_sources"] == ["target invisible"]


@pytest.mark.parametrize(
    ("condition", "enemy_name", "advantage_source"),
    [
        ("paralyzed", "Paralyzed Goblin", "target paralyzed"),
        ("unconscious", "Unconscious Goblin", "target unconscious"),
    ],
)
async def test_attack_roll_response_forces_close_incapacitated_target_crit(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
    condition, enemy_name, advantage_source,
):
    from sqlalchemy.orm.attributes import flag_modified

    headers = await _auth_headers(client, sample_user)
    sample_character.derived = {
        **(sample_character.derived or {}),
        "attack_bonus": 25,
        "crit_threshold": 99,
        "ability_modifiers": {
            **(sample_character.derived or {}).get("ability_modifiers", {}),
            "str": 3,
        },
    }
    combat_state.entity_positions = {
        sample_character.id: {"x": 5, "y": 5},
        "goblin-1": {"x": 6, "y": 5},
    }
    state = dict(sample_session.game_state or {})
    enemies = list(state.get("enemies") or [])
    enemies[0] = {
        **enemies[0],
        "name": enemy_name,
        "conditions": [condition],
        "condition_durations": {condition: 2},
        "derived": {
            **(enemies[0].get("derived") or {}),
            "ac": 12,
        },
    }
    state["enemies"] = enemies
    sample_session.game_state = state
    flag_modified(sample_character, "derived")
    flag_modified(combat_state, "entity_positions")
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    response = await client.post(
        f"/game/combat/{sample_session.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "target_id": "goblin-1",
            "action_type": "melee",
            "d20_value": 9,
            "second_d20_value": 14,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["hit"] is True
    assert data["is_crit"] is True
    assert data["forced_crit"] == "incapacitated_target"
    assert data["advantage"] is True
    assert data["advantage_sources"] == [advantage_source]
    assert data["target_conditions"] == [condition]
    assert data["d20"] == 14
    pending = data["turn_state"]["pending_attack"]
    assert pending["is_crit"] is True
    assert pending["target_conditions"] == [condition]
    assert pending["attack_roll"]["forced_crit"] == "incapacitated_target"

    damage = await client.post(
        f"/game/combat/{sample_session.id}/damage-roll",
        headers=headers,
        json={
            "pending_attack_id": data["pending_attack_id"],
            "damage_values": [4],
        },
    )

    assert damage.status_code == 200, damage.text
    damage_data = damage.json()
    assert damage_data["is_crit"] is True
    assert damage_data["damage_total"] == 7
    assert damage_data["crit_extra"] > 0
    assert damage_data["total_damage"] == damage_data["damage_total"] + damage_data["crit_extra"]
    assert "pending_attack" not in damage_data["turn_state"]

    from models import GameLog

    log_result = await db_session.execute(
        select(GameLog)
        .where(GameLog.session_id == sample_session.id, GameLog.log_type == "combat")
        .order_by(GameLog.created_at.desc())
    )
    latest_log = log_result.scalars().first()
    assert latest_log.dice_result["attack"]["forced_crit"] == "incapacitated_target"
    assert latest_log.dice_result["attack"]["target_conditions"] == [condition]
    assert latest_log.dice_result["crit_extra"] == damage_data["crit_extra"]
    assert latest_log.dice_result["total_damage"] == damage_data["total_damage"]


async def test_attack_roll_response_uses_second_d20_for_advantage(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    headers = await _auth_headers(client, sample_user)
    combat_state.turn_states = {
        sample_character.id: {
            "being_helped": True,
            "attacks_made": 0,
            "action_used": False,
            "bonus_action_used": False,
        },
    }
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    response = await client.post(
        f"/game/combat/{sample_session.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "target_id": "goblin-1",
            "action_type": "melee",
            "d20_value": 4,
            "second_d20_value": 18,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["advantage"] is True
    assert data["roll_state"] == "advantage"
    assert data["d20"] == 18
    assert data["d20_rolls"] == [4, 18]
    assert data["selected_d20"] == 18
    assert data["other_roll"] == 4
    assert data["d20_selection"] == "advantage"
    assert data["attack_total"] == 23
    assert data["turn_state"]["pending_attack"]["attack_roll"]["d20"] == 18
    assert data["turn_state"]["pending_attack"]["attack_roll"]["d20_rolls"] == [4, 18]


async def test_attack_roll_response_uses_second_d20_for_disadvantage(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    headers = await _auth_headers(client, sample_user)
    sample_character.conditions = ["poisoned"]
    combat_state.turn_states = {
        sample_character.id: {
            "attacks_made": 0,
            "action_used": False,
            "bonus_action_used": False,
        },
    }
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    response = await client.post(
        f"/game/combat/{sample_session.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": sample_character.id,
            "target_id": "goblin-1",
            "action_type": "melee",
            "d20_value": 18,
            "second_d20_value": 4,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["disadvantage"] is True
    assert data["roll_state"] == "disadvantage"
    assert data["disadvantage_sources"] == ["attacker poisoned"]
    assert data["d20"] == 4
    assert data["d20_rolls"] == [18, 4]
    assert data["selected_d20"] == 4
    assert data["other_roll"] == 18
    assert data["d20_selection"] == "disadvantage"
    assert data["attack_total"] == 9
    assert data["turn_state"]["pending_attack"]["attack_roll"]["d20"] == 4
    assert data["turn_state"]["pending_attack"]["attack_roll"]["d20_rolls"] == [18, 4]


async def test_smite_uses_pending_smite_crit_context_and_consumes_window(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified

    _patch_smite_narration(monkeypatch)
    headers = await _auth_headers(client, sample_user)
    sample_character.char_class = "Paladin"
    sample_character.spell_slots = {"1st": 1}
    combat_state.turn_states = {
        sample_character.id: {
            "pending_smite": {
                "target_id": "goblin-1",
                "target_name": "Goblin",
                "is_crit": True,
                "source": "test",
                "used": False,
            },
            "last_attack_target": "not-goblin-1",
            "last_attack_is_crit": False,
        },
    }
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    response = await client.post(
        f"/game/combat/{sample_session.id}/smite",
        headers=headers,
        json={
            "slot_level": 1,
            "target_id": "goblin-1",
            "is_crit": True,
            "damage_values": [1, 1, 1, 1],
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["smite_damage"] == 4
    assert data["smite_dice"] == "4d8"
    assert data["is_crit"] is True
    assert data["target_id"] == "goblin-1"
    assert data["target_new_hp"] == 3

    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    assert sample_character.spell_slots["1st"] == 0
    assert "pending_smite" not in combat_state.turn_states[sample_character.id]


async def test_smite_rejects_without_pending_smite_window_and_preserves_state(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    _patch_smite_narration(monkeypatch)
    headers = await _auth_headers(client, sample_user)
    sample_character.char_class = "Paladin"
    sample_character.spell_slots = {"1st": 1}
    await db_session.commit()

    response = await client.post(
        f"/game/combat/{sample_session.id}/smite",
        headers=headers,
        json={
            "slot_level": 1,
            "target_id": "goblin-1",
            "damage_values": [8, 8],
        },
    )

    assert response.status_code == 400, response.text
    assert "fresh confirmed weapon hit" in response.text
    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    assert sample_character.spell_slots["1st"] == 1
    assert sample_session.game_state["enemies"][0]["hp_current"] == 7


async def test_smite_rejects_mismatched_pending_smite_payload_without_consuming_slot(
    client, db_session, sample_session, combat_state, sample_user, sample_character, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified

    _patch_smite_narration(monkeypatch)
    headers = await _auth_headers(client, sample_user)
    sample_character.char_class = "Paladin"
    sample_character.spell_slots = {"1st": 1}
    combat_state.turn_states = {
        sample_character.id: {
            "pending_smite": {
                "target_id": "goblin-1",
                "target_name": "Goblin",
                "is_crit": True,
                "source": "test",
                "used": False,
            },
        },
    }
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    wrong_target = await client.post(
        f"/game/combat/{sample_session.id}/smite",
        headers=headers,
        json={
            "slot_level": 1,
            "target_id": "other-target",
            "is_crit": True,
            "damage_values": [8, 8, 8, 8],
        },
    )
    assert wrong_target.status_code == 409, wrong_target.text
    assert "target does not match" in wrong_target.text

    wrong_crit = await client.post(
        f"/game/combat/{sample_session.id}/smite",
        headers=headers,
        json={
            "slot_level": 1,
            "target_id": "goblin-1",
            "is_crit": False,
            "damage_values": [8, 8],
        },
    )
    assert wrong_crit.status_code == 409, wrong_crit.text
    assert "critical state does not match" in wrong_crit.text

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    await db_session.refresh(combat_state)
    assert sample_character.spell_slots["1st"] == 1
    assert sample_session.game_state["enemies"][0]["hp_current"] == 7
    assert combat_state.turn_states[sample_character.id]["pending_smite"]["target_id"] == "goblin-1"


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


async def test_attack_roll_records_recoverable_thrown_weapon_pool_item(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    headers = await _auth_headers(client, sample_user)
    sample_character.equipment = {
        "weapons": [{
            "name": "Javelin",
            "damage": "1d6",
            "type": "simple_melee",
            "properties": ["thrown(30/120)"],
            "equipped": True,
            "quantity": 2,
        }]
    }
    sample_character.derived = {
        **(sample_character.derived or {}),
        "ranged_attack_bonus": 5,
        "hit_die": 6,
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
            "weapon_name": "Javelin",
            "d20_value": 15,
        },
    )

    assert attack.status_code == 200, attack.text
    data = attack.json()
    assert data["weapon_resource"]["resource_type"] == "thrown_weapon"
    assert data["weapon_resource"]["recoverable"] is True
    assert data["weapon_resource"]["quantity_remaining"] == 1
    pool = data["thrown_weapon_recovery_pool"]
    assert pool["items"][0]["status"] == "available"
    assert pool["items"][0]["character_id"] == sample_character.id
    assert pool["items"][0]["weapon"] == "Javelin"

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    assert sample_character.equipment["weapons"][0]["quantity"] == 1
    saved = sample_session.game_state["thrown_weapon_recovery_pool"]["items"][0]
    assert saved["status"] == "available"
    assert saved["weapon"] == "Javelin"


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
    enemy_name = (sample_session.game_state or {})["enemies"][0]["name"]
    assert roll_data["action"] == "spell_roll"
    assert roll_data["narration"] == f"{sample_character.name} prepares 魔法飞弹 toward {enemy_name}."
    assert roll_data["dice_result"] == {
        "type": "spell_prepare",
        "actor_id": sample_character.id,
        "actor_name": sample_character.name,
        "spell_name": "魔法飞弹",
        "spell_level": 1,
        "spell_type": "damage",
        "damage_dice": "3d4+3",
        "heal_dice": "",
        "save_type": None,
        "save_dc": None,
        "is_cantrip": False,
        "is_aoe": False,
        "is_concentration": False,
        "target_count": 1,
        "spell_attack_required": False,
        "attack_roll": None,
        "hit": None,
        "is_crit": None,
    }
    assert roll_data["special_action"] == roll_data["dice_result"]
    assert "turn_state" not in roll_data["dice_result"]
    spell_prepare_log = (
        await db_session.execute(
            select(GameLog).where(GameLog.session_id == sample_session.id)
        )
    ).scalars().all()
    spell_prepare_log = [
        log for log in spell_prepare_log
        if isinstance(log.dice_result, dict) and log.dice_result.get("type") == "spell_prepare"
    ]
    assert len(spell_prepare_log) == 1
    assert spell_prepare_log[0].content == roll_data["narration"]
    assert spell_prepare_log[0].dice_result == roll_data["dice_result"]

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


async def test_spell_confirm_response_keeps_legendary_resistance_save_detail(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified

    state = dict(sample_session.game_state or {})
    enemy = state["enemies"][0]
    enemy["hp_current"] = 30
    enemy["hp_max"] = 30
    enemy["legendary_resistances"] = 1
    enemy["legendary_resistances_remaining"] = 1
    enemy["derived"] = {
        "hp_max": 30,
        "ac": 13,
        "ability_modifiers": {"dex": -20},
        "saving_throws": {"dex": -20},
    }
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.char_class = "Cleric"
    sample_character.cantrips = ["神圣烈焰"]
    sample_character.spell_slots = {}
    sample_character.derived = {
        **(sample_character.derived or {}),
        "spell_ability": "wis",
        "spell_save_dc": 14,
        "ability_modifiers": {"wis": 4},
    }
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    spell_roll = await client.post(
        f"/game/combat/{sample_session.id}/spell-roll",
        headers=headers,
        json={
            "caster_id": sample_character.id,
            "spell_name": "神圣烈焰",
            "spell_level": 0,
            "target_id": enemy["id"],
        },
    )
    assert spell_roll.status_code == 200, spell_roll.text

    confirm = await client.post(
        f"/game/combat/{sample_session.id}/spell-confirm",
        headers=headers,
        json={
            "pending_spell_id": spell_roll.json()["pending_spell_id"],
            "damage_values": [7],
        },
    )
    assert confirm.status_code == 200, confirm.text
    data = confirm.json()
    save = data["dice_result"]["target_state"]["save"]
    assert data["dice_result"]["save_result"] == save
    assert save["success"] is True
    assert save["legendary_resistance_used"] is True
    assert save["legendary_resistance_remaining"] == 0
    assert data["target_state"]["save"] == save
    assert data["target_new_hp"] == 30
    await db_session.refresh(sample_session)
    assert sample_session.game_state["enemies"][0]["legendary_resistances_remaining"] == 0


async def test_spell_attack_roll_critical_hit_doubles_damage_dice(
    client, db_session, sample_session, sample_character, combat_state, sample_user, monkeypatch,
):
    from sqlalchemy.orm.attributes import flag_modified

    state = dict(sample_session.game_state or {})
    state["enemies"][0]["hp_current"] = 30
    state["enemies"][0]["derived"] = {"hp_max": 30, "ac": 15}
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.char_class = "Wizard"
    sample_character.cantrips = ["火焰射线"]
    sample_character.known_spells = []
    sample_character.spell_slots = {}
    sample_character.derived = {
        **(sample_character.derived or {}),
        "spell_ability": "int",
        "spell_attack_bonus": 5,
        "spell_save_dc": 13,
        "ability_modifiers": {"int": 3},
    }
    await db_session.commit()

    base_rolls = iter([{"notation": "1d10", "rolls": [8], "total": 8}])
    crit_rolls = iter([{"notation": "1d10", "rolls": [6], "total": 6}])
    monkeypatch.setattr(
        "services.spell_service.roll_dice",
        lambda _expr: next(base_rolls),
    )
    monkeypatch.setattr(
        "services.dnd_rules.roll_dice",
        lambda _expr: next(crit_rolls),
    )

    headers = await _auth_headers(client, sample_user)
    spell_roll = await client.post(
        f"/game/combat/{sample_session.id}/spell-roll",
        headers=headers,
        json={
            "caster_id": sample_character.id,
            "spell_name": "火焰射线",
            "spell_level": 0,
            "target_id": "goblin-1",
            "d20_value": 20,
        },
    )
    assert spell_roll.status_code == 200, spell_roll.text
    roll_data = spell_roll.json()
    assert roll_data["spell_attack_required"] is True
    assert roll_data["hit"] is True
    assert roll_data["is_crit"] is True

    confirm = await client.post(
        f"/game/combat/{sample_session.id}/spell-confirm",
        headers=headers,
        json={
            "pending_spell_id": roll_data["pending_spell_id"],
        },
    )
    assert confirm.status_code == 200, confirm.text
    data = confirm.json()
    assert data["damage"] == 14
    assert data["dice_detail"]["crit_extra"] == 6
    assert data["target_new_hp"] == 16


async def test_spell_attack_roll_miss_consumes_action_without_damage(
    client, db_session, sample_session, sample_character, combat_state, sample_user,
):
    from sqlalchemy.orm.attributes import flag_modified

    state = dict(sample_session.game_state or {})
    state["enemies"][0]["hp_current"] = 30
    state["enemies"][0]["derived"] = {"hp_max": 30, "ac": 25}
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.char_class = "Wizard"
    sample_character.cantrips = ["火焰射线"]
    sample_character.derived = {
        **(sample_character.derived or {}),
        "spell_ability": "int",
        "spell_attack_bonus": 5,
        "ability_modifiers": {"int": 3},
    }
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    spell_roll = await client.post(
        f"/game/combat/{sample_session.id}/spell-roll",
        headers=headers,
        json={
            "caster_id": sample_character.id,
            "spell_name": "火焰射线",
            "spell_level": 0,
            "target_id": "goblin-1",
            "d20_value": 2,
        },
    )
    assert spell_roll.status_code == 200, spell_roll.text
    roll_data = spell_roll.json()
    assert roll_data["spell_attack_required"] is True
    assert roll_data["hit"] is False

    confirm = await client.post(
        f"/game/combat/{sample_session.id}/spell-confirm",
        headers=headers,
        json={"pending_spell_id": roll_data["pending_spell_id"], "damage_values": [8]},
    )
    assert confirm.status_code == 200, confirm.text
    data = confirm.json()
    assert data["damage"] == 0
    assert data["target_new_hp"] is None
    assert data["turn_state"]["action_used"] is True

    await db_session.refresh(sample_session)
    assert sample_session.game_state["enemies"][0]["hp_current"] == 30


async def test_spell_attack_roll_response_uses_second_d20_for_disadvantage(
    client, db_session, sample_session, sample_character, combat_state, sample_user,
):
    from sqlalchemy.orm.attributes import flag_modified

    state = dict(sample_session.game_state or {})
    state["enemies"][0]["hp_current"] = 30
    state["enemies"][0]["derived"] = {"hp_max": 30, "ac": 15}
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    sample_character.char_class = "Wizard"
    sample_character.cantrips = ["火焰射线"]
    sample_character.conditions = ["poisoned"]
    sample_character.derived = {
        **(sample_character.derived or {}),
        "spell_ability": "int",
        "spell_attack_bonus": 5,
        "ability_modifiers": {"int": 3},
    }
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    spell_roll = await client.post(
        f"/game/combat/{sample_session.id}/spell-roll",
        headers=headers,
        json={
            "caster_id": sample_character.id,
            "spell_name": "火焰射线",
            "spell_level": 0,
            "target_id": "goblin-1",
            "d20_value": 18,
            "second_d20_value": 4,
        },
    )

    assert spell_roll.status_code == 200, spell_roll.text
    roll_data = spell_roll.json()
    attack_roll = roll_data["attack_roll"]
    assert roll_data["spell_attack_required"] is True
    assert roll_data["hit"] is False
    assert attack_roll["d20"] == 4
    assert attack_roll["d20_rolls"] == [18, 4]
    assert attack_roll["selected_d20"] == 4
    assert attack_roll["other_roll"] == 18
    assert attack_roll["d20_selection"] == "disadvantage"
    assert attack_roll["attack_total"] == 9
    assert attack_roll["disadvantage"] is True
    assert attack_roll["roll_state"] == "disadvantage"
    assert attack_roll["disadvantage_sources"] == ["attacker poisoned"]
    pending = roll_data["turn_state"]["pending_spell"]
    assert pending["attack_roll"]["d20_rolls"] == [18, 4]
    assert pending["attack_roll"]["d20_selection"] == "disadvantage"


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


async def test_replacing_player_concentration_spell_returns_cleanup_updates(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_concentration_effect_service import track_concentration_condition

    sample_character.char_class = "Wizard"
    sample_character.spell_slots = {"2nd": 2}
    sample_character.known_spells = ["网", "蜘蛛爬行"]
    sample_character.concentration = "网"
    sample_character.derived = {
        **(sample_character.derived or {}),
        "spell_ability": "int",
        "spell_save_dc": 14,
        "ability_modifiers": {
            **(sample_character.derived or {}).get("ability_modifiers", {}),
            "int": 4,
        },
    }

    webbed_enemy = {
        "id": "webbed-goblin",
        "name": "Webbed Goblin",
        "hp_current": 7,
        "max_hp": 7,
        "conditions": ["restrained"],
        "condition_durations": {"restrained": 600},
        "derived": {"hp_max": 7, "ac": 12},
    }
    track_concentration_condition(
        webbed_enemy,
        "restrained",
        caster_id=sample_character.id,
        spell_name="网",
        condition_preexisting=False,
    )
    state = dict(sample_session.game_state or {})
    state["enemies"] = [webbed_enemy]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    spell_roll = await client.post(
        f"/game/combat/{sample_session.id}/spell-roll",
        headers=headers,
        json={
            "caster_id": sample_character.id,
            "spell_name": "蜘蛛爬行",
            "spell_level": 2,
            "target_ids": [],
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
    expected_updates = [{
        "target_id": "webbed-goblin",
        "target_name": "Webbed Goblin",
        "is_enemy": True,
        "removed_conditions": ["restrained"],
        "conditions": [],
        "condition_durations": {},
    }]
    assert data["is_concentration"] is True
    assert data["actor_state"]["concentration"] == "蜘蛛爬行"
    assert data["caster_state"]["concentration"] == "蜘蛛爬行"
    assert data["concentration_effect_updates"] == expected_updates
    assert data["actor_state"]["concentration_effect_updates"] == expected_updates
    assert data["remaining_slots"]["2nd"] == 1

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    assert sample_character.concentration == "蜘蛛爬行"
    cleaned = sample_session.game_state["enemies"][0]
    assert cleaned["conditions"] == []
    assert cleaned["condition_durations"] == {}
    assert "condition_sources" not in cleaned


async def test_end_player_concentration_returns_cleanup_updates(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_concentration_effect_service import track_concentration_condition

    sample_character.concentration = "网"
    webbed_enemy = {
        "id": "webbed-goblin",
        "name": "Webbed Goblin",
        "hp_current": 7,
        "max_hp": 7,
        "conditions": ["restrained"],
        "condition_durations": {"restrained": 600},
        "derived": {"hp_max": 7, "ac": 12},
    }
    track_concentration_condition(
        webbed_enemy,
        "restrained",
        caster_id=sample_character.id,
        spell_name="网",
        condition_preexisting=False,
    )
    state = dict(sample_session.game_state or {})
    state["enemies"] = [webbed_enemy]
    sample_session.game_state = state
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/concentration/end",
        headers=headers,
        json={"character_id": sample_character.id},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    expected_updates = [{
        "target_id": "webbed-goblin",
        "target_name": "Webbed Goblin",
        "is_enemy": True,
        "removed_conditions": ["restrained"],
        "conditions": [],
        "condition_durations": {},
    }]
    assert data["concentration_ended"] is True
    assert data["concentration_spell_name"] == "网"
    assert data["actor_state"]["concentration"] is None
    assert data["caster_state"]["concentration"] is None
    assert data["concentration_effect_updates"] == expected_updates
    assert data["actor_state"]["concentration_effect_updates"] == expected_updates
    assert data["action"] == "concentration_end"
    assert data["dice_result"]["type"] == "concentration_end"
    assert data["dice_result"]["actor_state"] == data["actor_state"]
    assert data["dice_result"]["concentration_effect_updates"] == expected_updates
    assert data["special_action"] == data["dice_result"]

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    assert sample_character.concentration is None
    cleaned = sample_session.game_state["enemies"][0]
    assert cleaned["conditions"] == []
    assert cleaned["condition_durations"] == {}
    assert "condition_sources" not in cleaned


async def test_ending_ready_spell_concentration_clears_ready_action(
    client, db_session, sample_session, combat_state, sample_user, sample_character,
):
    from sqlalchemy.orm.attributes import flag_modified
    from services.combat_ready_action_service import build_ready_spell_payload

    enemy = (sample_session.game_state or {})["enemies"][0]
    hold_name = "准备法术: 魔法飞弹"
    sample_character.concentration = hold_name
    combat_state.turn_states = {
        sample_character.id: {
            "action_used": True,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "ready_action": build_ready_spell_payload(
                actor_id=sample_character.id,
                actor_name=sample_character.name,
                target_id=enemy["id"],
                target_name=enemy["name"],
                spell_name="魔法飞弹",
                spell_level=1,
                slot_already_consumed=True,
                slot_key="1st",
                slots_remaining=0,
                concentration_spell_name=hold_name,
            ),
        },
    }
    flag_modified(combat_state, "turn_states")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/concentration/end",
        headers=headers,
        json={"character_id": sample_character.id},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["concentration_ended"] is True
    assert data["concentration_spell_name"] == hold_name
    assert data["ready_action_failed"]["reason"] == "concentration_ended"
    assert data["actor_state"]["ready_action_failed"]["reason"] == "concentration_ended"
    assert data["action"] == "concentration_end"
    assert data["dice_result"]["type"] == "concentration_end"
    assert data["dice_result"]["ready_action_failed"] == data["ready_action_failed"]
    assert data["special_action"] == data["dice_result"]

    await db_session.refresh(sample_character)
    await db_session.refresh(combat_state)
    assert sample_character.concentration is None
    turn_state = combat_state.turn_states[sample_character.id]
    assert "ready_action" not in turn_state
    assert turn_state["ready_action_failed"]["reason"] == "concentration_ended"


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
    assert data["action"] == "condition_add"
    assert data["target_id"] == sample_character.id
    assert data["target_name"] == sample_character.name
    assert data["condition_action"] == "add"
    assert data["condition_result"] == {
        "condition": "paralyzed",
        "condition_action": "add",
        "applied": True,
        "removed": False,
        "immune": False,
        "target_id": sample_character.id,
        "target_name": sample_character.name,
    }
    assert data["concentration"] is None
    assert data["target_state"]["concentration"] is None
    assert data["target_state"]["conditions"] == ["paralyzed"]
    assert data["target_state"]["life_state"] == "alive"
    assert data["dice_result"]["type"] == "condition_update"
    assert data["dice_result"]["condition"] == "paralyzed"
    assert data["dice_result"]["condition_result"] == data["condition_result"]
    assert data["dice_result"]["target_state"] == data["target_state"]
    assert data["special_action"] == data["dice_result"]
    await db_session.refresh(sample_character)
    assert sample_character.concentration is None

    r = await client.post(
        f"/game/combat/{sample_session.id}/condition/remove",
        headers=headers,
        json={"entity_id": sample_character.id, "condition": "paralyzed", "is_enemy": False},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["action"] == "condition_remove"
    assert data["target_id"] == sample_character.id
    assert data["target_name"] == sample_character.name
    assert data["condition_action"] == "remove"
    assert data["condition_result"] == {
        "condition": "paralyzed",
        "condition_action": "remove",
        "applied": False,
        "removed": True,
        "immune": False,
        "target_id": sample_character.id,
        "target_name": sample_character.name,
    }
    assert data["target_state"]["conditions"] == []
    assert data["dice_result"]["type"] == "condition_update"
    assert data["dice_result"]["condition_result"] == data["condition_result"]
    assert data["dice_result"]["target_state"] == data["target_state"]
    assert data["special_action"] == data["dice_result"]


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
    assert data["action"] == "condition_add"
    assert data["target_id"] == "ooze-1"
    assert data["target_name"] == "Ooze"
    assert data["condition_result"]["immune"] is True
    assert data["condition_result"]["applied"] is False
    assert data["condition_result"]["removed"] is False
    assert data["target_state"]["is_enemy"] is True
    assert data["target_state"]["conditions"] == []
    assert data["dice_result"]["type"] == "condition_update"
    assert data["dice_result"]["condition_result"] == data["condition_result"]
    assert data["special_action"] == data["dice_result"]
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


async def test_recover_thrown_weapons_restores_post_combat_inventory(
    client,
    db_session,
    sample_session,
    sample_character,
    sample_user,
):
    from sqlalchemy.orm.attributes import flag_modified

    sample_session.combat_active = False
    sample_character.equipment = {
        "weapons": [{
            "name": "Javelin",
            "type": "simple_melee",
            "damage": "1d6",
            "properties": ["thrown(30/120)"],
            "quantity": 1,
            "equipped": True,
        }],
    }
    sample_session.game_state = {
        **(sample_session.game_state or {}),
        "thrown_weapon_recovery_pool": {
            "version": 1,
            "items": [{
                "id": "thrown-1",
                "status": "available",
                "character_id": sample_character.id,
                "character_name": sample_character.name,
                "weapon": "Javelin",
                "quantity": 1,
                "item": {
                    "name": "Javelin",
                    "type": "simple_melee",
                    "damage": "1d6",
                    "properties": ["thrown(30/120)"],
                    "quantity": 1,
                    "equipped": False,
                },
                "public": True,
            }],
        },
    }
    flag_modified(sample_character, "equipment")
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/game/combat/{sample_session.id}/recover-thrown-weapons",
        headers=headers,
        json={"character_id": sample_character.id},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["recovered"] == [{
        "id": "thrown-1",
        "weapon": "Javelin",
        "quantity": 1,
        "item": {
            "name": "Javelin",
            "type": "simple_melee",
            "damage": "1d6",
            "properties": ["thrown(30/120)"],
            "quantity": 1,
            "equipped": False,
        },
    }]
    assert data["equipment"]["weapons"][0]["quantity"] == 2
    assert data["recovery_pool"]["items"][0]["status"] == "recovered"

    await db_session.refresh(sample_character)
    await db_session.refresh(sample_session)
    assert sample_character.equipment["weapons"][0]["quantity"] == 2
    pool_item = sample_session.game_state["thrown_weapon_recovery_pool"]["items"][0]
    assert pool_item["status"] == "recovered"
    assert pool_item["recovered_by_character_id"] == sample_character.id

    second = await client.post(
        f"/game/combat/{sample_session.id}/recover-thrown-weapons",
        headers=headers,
        json={"character_id": sample_character.id},
    )
    assert second.status_code == 200, second.text
    assert second.json()["recovered"] == []
    await db_session.refresh(sample_character)
    assert sample_character.equipment["weapons"][0]["quantity"] == 2
