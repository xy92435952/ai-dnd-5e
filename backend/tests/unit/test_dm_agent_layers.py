import pytest

from services.graphs import dm_agent


@pytest.mark.asyncio
async def test_input_layer_passes_action_source_to_guard(monkeypatch):
    seen = {}

    async def fake_classify(player_action, source="human_input"):
        seen["player_action"] = player_action
        seen["source"] = source
        return {"verdict": "in_game", "reason": "ok", "refusal": ""}

    monkeypatch.setattr("services.input_guard.classify_player_input", fake_classify)

    result = await dm_agent.input_layer({
        "player_action": "检查墙上的符文",
        "action_source": "ai_generated_choice",
    })

    assert seen == {
        "player_action": "检查墙上的符文",
        "source": "ai_generated_choice",
    }
    assert result["guard_verdict"] == "in_game"
    assert result["input_meta"]["source"] == "ai_generated_choice"
    assert result["input_meta"]["is_human_input"] is False


def test_rules_layer_mentions_advantage_and_inspiration_as_legal_terms():
    context = dm_agent._build_rules_context({
        "action_source": "human_input",
        "player_action": "我使用激励骰获得优势",
        "game_state": '{"current_actor_id":"c1","current_actor_name":"凯伦","characters":[{"id":"c1","name":"凯伦","char_class":"Bard","level":3}]}',
        "input_meta": {"source": "human_input"},
    })

    assert "优势" in context
    assert "激励骰" in context
    assert "本身不是作弊词" in context
