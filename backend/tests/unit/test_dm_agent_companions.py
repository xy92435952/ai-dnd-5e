import json

import pytest
from langchain_core.messages import HumanMessage

from services.graphs.dm_agent_companions import (
    _collect_ai_companions,
    _normalize_companion_brief,
    generate_companion_reactions,
    route_after_parse,
)


def test_collect_ai_companions_filters_out_player_controlled_characters():
    game_state = json.dumps({
        "characters": [
            {"id": "p1", "name": "Player", "is_player": True},
            {
                "id": "c1",
                "name": "Aela",
                "is_player": False,
                "personality": "careful",
                "speech_style": "quiet",
                "backstory": "x" * 300,
            },
            {"id": "bad", "is_player": False},
        ]
    })

    companions = _collect_ai_companions(game_state)

    assert companions == [
        {
            "id": "c1",
            "name": "Aela",
            "personality": "careful",
            "speech_style": "quiet",
            "combat_preference": "",
            "catchphrase": "",
            "backstory": "x" * 240,
        }
    ]


def test_normalize_companion_brief_clamps_generation_controls():
    result = {
        "action_type": "investigation",
        "narrative": "You notice old ash under the altar.",
        "needs_check": {"required": False},
        "state_delta": {"combat_trigger": False},
    }

    brief = _normalize_companion_brief(
        {"enabled": "true", "speaker_limit": 99, "max_words": "999", "focus": "ashes"},
        result,
    )

    assert brief["enabled"] is True
    assert brief["speaker_limit"] == 2
    assert brief["max_words"] == 120
    assert brief["focus"] == "ashes"


def test_route_after_parse_only_generates_for_exploration_ai_companions():
    game_state = json.dumps({
        "characters": [
            {"id": "p1", "name": "Player", "is_player": True},
            {"id": "c1", "name": "Aela", "is_player": False},
        ]
    })
    state = {
        "combat_active": False,
        "game_state": game_state,
        "result": {
            "action_type": "dialogue",
            "needs_check": {"required": False},
            "state_delta": {"combat_trigger": False},
            "companion_brief": {"enabled": True, "speaker_limit": 1},
        },
    }

    assert route_after_parse(state) == "generate_companion_reactions"

    state["combat_active"] = True
    assert route_after_parse(state) == "end"


@pytest.mark.asyncio
async def test_generate_companion_reactions_uses_companion_llm(monkeypatch):
    seen = {}

    class FakeLLM:
        async def ainvoke(self, messages):
            seen["messages"] = messages

            class Response:
                content = "[Aela]: Keep your eyes on the altar."

            return Response()

    monkeypatch.setattr("services.graphs.dm_agent_companions.get_llm", lambda **_kwargs: FakeLLM())

    result = await generate_companion_reactions({
        "player_action": "I inspect the altar.",
        "game_state": json.dumps({
            "characters": [{"id": "c1", "name": "Aela", "is_player": False}]
        }),
        "messages": [HumanMessage(content="I enter the shrine.")],
        "result": {
            "narrative": "The altar is cold.",
            "needs_check": {"required": False},
            "state_delta": {"combat_trigger": False},
            "companion_brief": {"enabled": True, "speaker_limit": 1},
        },
    })

    assert result["result"]["companion_reactions"] == "[Aela]: Keep your eyes on the altar."
    assert "Available AI companions" in seen["messages"][1].content
