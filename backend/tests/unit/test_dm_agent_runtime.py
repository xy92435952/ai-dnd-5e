import json

from services.graphs.dm_agent_runtime import (
    build_initial_state,
    build_pre_rolled_dice,
    read_combat_active,
    wrap_final_state,
)


def test_build_pre_rolled_dice_returns_expected_pool_shape():
    pool = build_pre_rolled_dice()

    assert len(pool["d20"]) == 16
    assert len(pool["adv"]) == 6
    assert len(pool["dis"]) == 6
    assert len(pool["d4"]) == 8
    assert len(pool["d6"]) == 12
    assert len(pool["d8"]) == 8
    assert len(pool["d10"]) == 6
    assert len(pool["d12"]) == 4
    assert len(pool["hit_dice"]) == 6
    assert isinstance(pool["d100"], int)
    assert all(1 <= value <= 20 for value in pool["d20"])
    assert all(1 <= value <= 20 for value in pool["adv"])
    assert all(1 <= value <= 20 for value in pool["dis"])


def test_read_combat_active_tolerates_bad_json():
    assert read_combat_active('{"combat_active": true}') is True
    assert read_combat_active('{"combat_active": false}') is False
    assert read_combat_active("{bad json") is False
    assert read_combat_active(None) is False


def test_build_initial_state_preserves_public_inputs_and_defaults():
    state = build_initial_state(
        player_action="检查石门",
        game_state='{"scene": "gate"}',
        module_context="古堡入口",
        campaign_memory="救过铁匠",
        retrieved_context="门上有旧血",
        action_source="ai_generated_choice",
    )

    assert state["player_action"] == "检查石门"
    assert state["action_source"] == "ai_generated_choice"
    assert state["module_context"] == "古堡入口"
    assert state["campaign_memory"] == "救过铁匠"
    assert state["retrieved_context"] == "门上有旧血"
    assert state["messages"] == []
    assert state["result"] == {}
    assert state["error"] == ""


def test_wrap_final_state_matches_langgraph_client_contract():
    final_state = {
        "result": {
            "action_type": "combat_attack",
            "narrative": "剑锋划开阴影。",
            "companion_reactions": "艾拉低声提醒你留意后方。",
            "needs_check": '{"required": true, "check_type": "attack"}',
            "player_choices": ["继续追击"],
            "state_delta": {
                "combat_trigger": "true",
                "combat_end": "false",
                "enemies": [{"id": "g1", "hp_change": -5}],
            },
            "dice_results": [{"label": "攻击骰", "total": 17}],
            "ai_turns": [{"actor": "goblin"}],
            "campaign_delta": {
                "quest_updates": [{"quest": "调查暗门", "status": "active", "outcome": ""}],
            },
        },
        "error": "",
    }

    wrapped = wrap_final_state(final_state, session_id="s1")
    result_payload = json.loads(wrapped["result"])

    assert wrapped["action_type"] == "combat_attack"
    assert wrapped["narrative"] == "剑锋划开阴影。"
    assert wrapped["dice_display"] == [{"label": "攻击骰", "total": 17}]
    assert wrapped["combat_trigger"] is True
    assert wrapped["combat_end"] is False
    assert wrapped["_conversation_id"] == "s1"
    assert wrapped["needs_check"] == {"required": True, "check_type": "attack"}
    assert result_payload["player_choices"] == ["继续追击"]
    assert result_payload["campaign_delta"]["quest_updates"][0]["quest"] == "调查暗门"
    assert json.loads(wrapped["state_delta"])["enemies"][0]["hp_change"] == -5
