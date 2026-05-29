import json

import pytest

from services.graphs.dm_agent_companions import (
    generate_companion_reactions,
    route_after_parse,
)
from services.graphs.dm_agent_nodes import parse_validate
from services.graphs.dm_agent_prompts import EXPLORE_SYSTEM
from services.graphs.dm_agent_runtime import wrap_final_state


PUBLIC_SCHEMA_FIELDS = {
    "narrative": str,
    "needs_check": dict,
    "state_delta": dict,
    "player_choices": list,
    "companion_reactions": str,
}


REGRESSION_PROMPTS = [
    {
        "name": "dialogue_choices",
        "player_prompt": "I ask the archivist what happened to the sealed gate.",
        "raw_output": {
            "action_type": "dialogue",
            "narrative": "The archivist lowers her candle and describes a gate sealed after the last eclipse.",
            "needs_check": {
                "required": False,
                "check_type": None,
                "ability": None,
                "dc": 10,
            },
            "state_delta": {
                "characters": [],
                "enemies": [],
                "combat_trigger": False,
                "combat_end": False,
                "gold_changes": [],
                "clues_add": [
                    {"text": "The sealed gate was closed after an eclipse.", "category": "dialogue"}
                ],
            },
            "player_choices": [
                {
                    "text": "Ask who ordered the gate sealed.",
                    "tags": [{"label": "Lore", "kind": "lore"}],
                },
                "Thank the archivist and inspect the gate yourself.",
            ],
            "companion_reactions": "",
            "companion_brief": {"enabled": False, "speaker_limit": 0},
        },
        "expected": {
            "needs_check_required": False,
            "choice_count": 2,
            "character_delta_count": 0,
        },
    },
    {
        "name": "pending_skill_check",
        "player_prompt": "I squeeze through the cracked portcullis before it drops.",
        "raw_output": {
            "action_type": "skill_check",
            "narrative": "You twist sideways and commit to the gap just as the chains begin to shriek.",
            "needs_check": {
                "required": True,
                "check_type": "Acrobatics",
                "ability": "dex",
                "dc": 15,
                "context": "The opening is narrow and closing fast.",
            },
            "state_delta": {
                "characters": [{"id": "c1", "hp_change": "-5"}],
                "enemies": [{"id": "e1", "hp_change": "-3"}],
                "combat_trigger": True,
                "combat_end": True,
                "gold_changes": [{"id": "c1", "amount": "25"}],
            },
            "player_choices": [
                {"text": "Slip through successfully.", "tags": [{"label": "Success", "kind": "success"}]},
                {"text": "Get caught by the gate.", "tags": [{"label": "Failure", "kind": "fail"}]},
            ],
            "companion_reactions": "",
        },
        "expected": {
            "needs_check_required": True,
            "choice_count": 0,
            "character_delta_count": 0,
            "combat_trigger": False,
            "combat_end": False,
        },
    },
]


def test_explore_system_prompt_keeps_public_schema_keys_visible():
    for key in PUBLIC_SCHEMA_FIELDS:
        assert f'"{key}"' in EXPLORE_SYSTEM

    assert "Return `companion_reactions` as an empty string." in EXPLORE_SYSTEM
    assert "companion_brief" in EXPLORE_SYSTEM


@pytest.mark.asyncio
@pytest.mark.parametrize("case", REGRESSION_PROMPTS, ids=lambda case: case["name"])
async def test_parse_validate_and_runtime_wrapper_keep_public_schema_for_regression_prompts(case):
    parsed = await parse_validate({
        "player_action": case["player_prompt"],
        "llm_output": json.dumps(case["raw_output"]),
        "combat_active": False,
    })

    result = parsed["result"]
    for field, expected_type in PUBLIC_SCHEMA_FIELDS.items():
        assert field in result
        assert isinstance(result[field], expected_type)

    expected = case["expected"]
    assert result["needs_check"]["required"] is expected["needs_check_required"]
    assert len(result["player_choices"]) == expected["choice_count"]
    assert len(result["state_delta"]["characters"]) == expected["character_delta_count"]
    if "combat_trigger" in expected:
        assert result["state_delta"]["combat_trigger"] is expected["combat_trigger"]
    if "combat_end" in expected:
        assert result["state_delta"]["combat_end"] is expected["combat_end"]

    wrapped = wrap_final_state({"result": result, "error": parsed["error"]}, session_id="schema-regression")
    result_payload = json.loads(wrapped["result"])
    for field, expected_type in PUBLIC_SCHEMA_FIELDS.items():
        assert field in result_payload
        assert isinstance(result_payload[field], expected_type)
    assert wrapped["needs_check"] == result["needs_check"]
    assert json.loads(wrapped["state_delta"]) == result["state_delta"]


@pytest.mark.asyncio
async def test_companion_reaction_regression_prompt_uses_separate_handoff(monkeypatch):
    parsed = await parse_validate({
        "player_action": "I study the cracked altar and wait for a sign.",
        "llm_output": json.dumps({
            "action_type": "investigation",
            "narrative": "Cold dust gathers in the altar seams, outlining an old sunburst.",
            "needs_check": {"required": False},
            "state_delta": {
                "characters": [],
                "enemies": [],
                "combat_trigger": False,
                "combat_end": False,
            },
            "player_choices": [],
            "companion_reactions": "[Aela]: This should not be drafted by the main DM node.",
            "companion_brief": {
                "enabled": True,
                "scene_type": "reveal",
                "emotion": "uneasy",
                "focus": "The altar shows a hidden sunburst.",
                "speaker_limit": 1,
                "max_words": 16,
            },
        }),
        "combat_active": False,
    })

    state = {
        **parsed,
        "player_action": "I study the cracked altar and wait for a sign.",
        "combat_active": False,
        "game_state": json.dumps({
            "characters": [
                {"id": "p1", "name": "Player", "is_player": True},
                {"id": "c1", "name": "Aela", "is_player": False, "speech_style": "direct"},
            ]
        }),
    }

    assert parsed["result"]["companion_reactions"] == ""
    assert route_after_parse(state) == "generate_companion_reactions"

    class FakeLLM:
        async def ainvoke(self, _messages):
            class Response:
                content = "[Aela]: That mark was meant to be hidden."

            return Response()

    monkeypatch.setattr("services.graphs.dm_agent_companions.get_llm", lambda **_kwargs: FakeLLM())

    generated = await generate_companion_reactions(state)

    assert generated["result"]["companion_reactions"] == "[Aela]: That mark was meant to be hidden."
