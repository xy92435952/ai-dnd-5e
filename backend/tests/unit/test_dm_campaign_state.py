import json

import pytest

from services.graphs import dm_campaign_state
from services.graphs.dm_campaign_state import _merge_campaign_states


def test_merge_campaign_states_deduplicates_lists_and_updates_maps():
    existing = {
        "completed_scenes": ["矿洞入口"],
        "key_decisions": ["救下铁匠"],
        "notable_items": ["旧钥匙"],
        "party_changes": ["凯伦受伤"],
        "npc_registry": {
            "铁匠": {"relationship": "友好", "key_facts": ["欠玩家人情"]},
        },
        "world_flags": {"wolf_seen": True},
        "quest_log": [
            {"quest": "寻找失踪矿工", "status": "active", "outcome": ""},
        ],
    }
    new = {
        "completed_scenes": ["矿洞入口", "矿井深处"],
        "key_decisions": ["救下铁匠", "放走斥候"],
        "notable_items": ["旧钥匙", "银质徽章"],
        "party_changes": ["凯伦受伤"],
        "npc_registry": {
            "铁匠": {"relationship": "盟友", "key_facts": ["愿意修装备"]},
            "斥候": {"relationship": "复杂", "key_facts": ["知道暗门"]},
        },
        "world_flags": {"wolf_seen": True, "scout_spared": True},
        "quest_log": [
            {"quest": "寻找失踪矿工", "status": "completed", "outcome": "矿工获救"},
            {"quest": "调查暗门", "status": "active", "outcome": ""},
        ],
    }

    merged = _merge_campaign_states(existing, new)

    assert merged["completed_scenes"] == ["矿洞入口", "矿井深处"]
    assert merged["key_decisions"] == ["救下铁匠", "放走斥候"]
    assert merged["notable_items"] == ["旧钥匙", "银质徽章"]
    assert merged["party_changes"] == ["凯伦受伤"]
    assert merged["npc_registry"]["铁匠"]["relationship"] == "盟友"
    assert merged["npc_registry"]["斥候"]["key_facts"] == ["知道暗门"]
    assert merged["world_flags"] == {"wolf_seen": True, "scout_spared": True}
    assert merged["quest_log"] == [
        {"quest": "寻找失踪矿工", "status": "completed", "outcome": "矿工获救"},
        {"quest": "调查暗门", "status": "active", "outcome": ""},
    ]


def test_merge_campaign_states_tolerates_malformed_quest_entries():
    existing = {
        "quest_log": [
            {"quest": "守住营地", "status": "active", "outcome": ""},
            {"status": "broken"},
        ],
    }
    new = {
        "quest_log": [
            {"quest": "守住营地", "status": "completed", "outcome": "狼群退走"},
            {"status": "missing quest"},
            "not a dict",
        ],
    }

    merged = _merge_campaign_states(existing, new)

    assert merged["quest_log"] == [
        {"quest": "守住营地", "status": "completed", "outcome": "狼群退走"},
    ]


@pytest.mark.asyncio
async def test_run_campaign_state_generator_merges_llm_json(monkeypatch):
    existing = {
        "completed_scenes": ["开场"],
        "quest_log": [{"quest": "寻找矿工", "status": "active", "outcome": ""}],
    }
    generated = {
        "completed_scenes": ["开场", "矿洞"],
        "quest_log": [{"quest": "寻找矿工", "status": "completed", "outcome": "矿工获救"}],
        "npc_registry": {"铁匠": {"relationship": "友好"}},
        "world_flags": {"miners_saved": True},
    }

    class FakeLLM:
        async def ainvoke(self, messages):
            self.messages = messages
            return type("Resp", (), {"content": "```json\n" + json.dumps(generated, ensure_ascii=False) + "\n```"})()

    fake_llm = FakeLLM()
    monkeypatch.setattr(dm_campaign_state, "get_llm", lambda **kwargs: fake_llm)

    merged = await dm_campaign_state.run_campaign_state_generator(
        log_text="玩家救下矿工。",
        module_summary="矿洞冒险",
        existing_state=existing,
    )

    assert merged["completed_scenes"] == ["开场", "矿洞"]
    assert merged["quest_log"] == [{"quest": "寻找矿工", "status": "completed", "outcome": "矿工获救"}]
    assert merged["npc_registry"]["铁匠"]["relationship"] == "友好"
    assert merged["world_flags"]["miners_saved"] is True
    assert "矿洞冒险" in fake_llm.messages[1].content
    assert "玩家救下矿工。" in fake_llm.messages[1].content


@pytest.mark.asyncio
async def test_run_campaign_state_generator_returns_existing_state_on_llm_error(monkeypatch):
    existing = {"completed_scenes": ["开场"], "quest_log": []}

    class FailingLLM:
        async def ainvoke(self, messages):
            raise RuntimeError("model down")

    monkeypatch.setattr(dm_campaign_state, "get_llm", lambda **kwargs: FailingLLM())

    result = await dm_campaign_state.run_campaign_state_generator(
        log_text="日志",
        module_summary="模组",
        existing_state=existing,
    )

    assert result is existing
