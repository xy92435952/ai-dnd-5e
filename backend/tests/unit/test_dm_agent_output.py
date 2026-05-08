import json

from langchain_core.messages import AIMessage, HumanMessage

from services.graphs.dm_agent_utils import normalize_dm_output


def test_normalize_dm_output_coerces_numeric_state_delta_fields():
    raw = json.dumps({
        "action_type": "combat_attack",
        "narrative": "你挥剑命中。",
        "state_delta": {
            "characters": [{"id": "c1", "hp_change": "-3"}],
            "enemies": [{"id": "e1", "hp_change": "-7"}],
            "gold_changes": [{"character_id": "c1", "amount": "12"}],
        },
        "ai_turns": [
            {
                "actor_id": "e1",
                "state_delta": {
                    "characters": [{"id": "c1", "hp_change": "bad"}],
                    "enemies": [],
                },
            },
        ],
    }, ensure_ascii=False)

    data, error, messages = normalize_dm_output(raw, "攻击地精")

    assert error == ""
    assert data["state_delta"]["characters"][0]["hp_change"] == -3
    assert data["state_delta"]["enemies"][0]["hp_change"] == -7
    assert data["state_delta"]["gold_changes"][0]["amount"] == 12
    assert data["ai_turns"][0]["state_delta"]["characters"][0]["hp_change"] == 0
    assert data["needs_check"] == {
        "required": False,
        "check_type": None,
        "ability": None,
        "dc": 10,
    }
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)


def test_normalize_dm_output_parses_markdown_json_block():
    raw = """```json
{"narrative": "钟声在塔楼里回荡。", "needs_check": {"required": true, "dc": 14}}
```"""

    data, error, _messages = normalize_dm_output(raw, "检查钟楼")

    assert error == ""
    assert data["narrative"] == "钟声在塔楼里回荡。"
    assert data["needs_check"]["required"] is True
    assert data["needs_check"]["dc"] == 14
    assert data["needs_check"]["check_type"] is None
    assert data["state_delta"]["combat_trigger"] is False


def test_normalize_dm_output_preserves_check_advantage_flags_and_choice_metadata():
    raw = json.dumps({
        "action_type": "investigation",
        "narrative": "你借着队友的掩护靠近符文门。",
        "needs_check": {
            "required": False,
            "check_type": "调查",
            "ability": "int",
            "dc": 15,
            "advantage": True,
            "disadvantage": False,
            "context": "帮助动作给予优势",
        },
        "player_choices": [
            {
                "text": "用激励骰补到这次调查检定上。",
                "tags": [{"label": "调查", "kind": "check", "dc": 15}],
                "skill_check": True,
                "action": False,
                "ended": False,
            }
        ],
    }, ensure_ascii=False)

    data, error, _messages = normalize_dm_output(raw, "检查符文门")

    assert error == ""
    assert data["needs_check"]["advantage"] is True
    assert data["needs_check"]["disadvantage"] is False
    assert data["needs_check"]["context"] == "帮助动作给予优势"
    assert data["player_choices"][0]["skill_check"] is True
    assert data["player_choices"][0]["tags"][0]["kind"] == "check"
    assert data["player_choices"][0]["tags"][0]["dc"] == 15


def test_normalize_dm_output_repairs_schema_conflicts_and_bad_collection_types():
    raw = json.dumps({
        "action_type": "investigation",
        "narrative": "你停在门前，等待检定结果。",
        "needs_check": {
            "required": True,
            "check_type": "调查",
            "advantage": True,
            "disadvantage": True,
        },
        "player_choices": [
            {"tags": [{"label": "调查", "kind": "check"}], "skill_check": True},
            "等待同伴靠近",
        ],
        "state_delta": {
            "characters": {"id": "c1", "hp_change": "-5"},
            "enemies": "bad",
            "gold_changes": {"id": "c1", "amount": "7"},
        },
        "ai_turns": {"actor_id": "e1"},
    }, ensure_ascii=False)

    data, error, _messages = normalize_dm_output(raw, "检查机关")

    assert error == ""
    assert data["needs_check"]["required"] is True
    assert data["needs_check"]["advantage"] is False
    assert data["needs_check"]["disadvantage"] is False
    assert data["player_choices"] == []
    assert data["state_delta"]["characters"] == []
    assert data["state_delta"]["enemies"] == []
    assert data["state_delta"]["gold_changes"] == []
    assert data["ai_turns"] == []


def test_normalize_dm_output_falls_back_with_extracted_narrative():
    raw = '{"action_type": "exploration", "narrative": "门后的风突然停了。", "broken": '

    data, error, messages = normalize_dm_output(raw, "推开门")

    assert error
    assert data["action_type"] == "exploration"
    assert data["narrative"] == "门后的风突然停了。"
    assert data["needs_check"] == {"required": False}
    assert messages[0].content == "推开门"
    assert messages[1].content == "门后的风突然停了。"
