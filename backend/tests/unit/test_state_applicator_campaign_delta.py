import json

import pytest

from models.session import Session
from services.state_applicator import StateApplicator


class FakeDb:
    def __init__(self):
        self.added = []

    def add(self, item):
        self.added.append(item)


@pytest.mark.asyncio
async def test_state_applicator_merges_campaign_delta_into_session_memory():
    session = Session(
        id="session-1",
        module_id="module-1",
        game_state={},
        campaign_state={
            "quest_log": [{"quest": "寻找矿工", "status": "active", "outcome": ""}],
            "npc_registry": {"铁匠": {"relationship": "中立", "key_facts": ["欠玩家人情"], "promises": []}},
            "key_decisions": ["救下铁匠"],
            "world_flags": {"met_smith": True},
            "clues": [{"text": "旧钥匙", "category": "item", "is_new": False}],
        },
    )
    applicator = StateApplicator(FakeDb())

    result = {
        "narrative": "铁匠低声说出井底暗门的位置。",
        "campaign_delta": {
            "quest_updates": [
                {"quest": "寻找矿工", "status": "completed", "outcome": "矿工获救"},
                {"quest": "调查暗门", "status": "active", "outcome": ""},
            ],
            "npc_updates": [
                {
                    "name": "铁匠",
                    "relationship": "友好",
                    "key_facts": ["愿意修装备"],
                    "promises": ["明早带路"],
                }
            ],
            "key_decisions_add": ["信任铁匠"],
            "world_flags_set": {"smith_trusted": True},
            "clues_add": [
                {"text": "旧钥匙", "category": "item"},
                {"text": "暗门在井底", "category": "location"},
            ],
            "scene_vibe": {"location": "矿村井口", "time_of_day": "深夜", "tension": "紧张"},
        },
    }

    await applicator.apply(session, json.dumps(result, ensure_ascii=False), characters=[])

    assert session.game_state["scene_vibe"] == {
        "location": "矿村井口",
        "time_of_day": "深夜",
        "tension": "紧张",
    }
    assert session.campaign_state["quest_log"] == [
        {"quest": "寻找矿工", "status": "completed", "outcome": "矿工获救"},
        {"quest": "调查暗门", "status": "active", "outcome": ""},
    ]
    assert session.campaign_state["npc_registry"]["铁匠"] == {
        "relationship": "友好",
        "key_facts": ["欠玩家人情", "愿意修装备"],
        "promises": ["明早带路"],
    }
    assert session.campaign_state["key_decisions"] == ["救下铁匠", "信任铁匠"]
    assert session.campaign_state["world_flags"] == {"met_smith": True, "smith_trusted": True}
    assert [c["text"] for c in session.campaign_state["clues"]] == ["旧钥匙", "暗门在井底"]
