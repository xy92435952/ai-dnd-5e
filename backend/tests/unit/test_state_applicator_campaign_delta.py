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
                {
                    "quest": "调查暗门",
                    "status": "active",
                    "outcome": "",
                    "branch": "井底调查线",
                    "next_step": "确认暗门是否会在月光下开启",
                    "failure_consequence": "守卫巡逻会提前封锁井口",
                    "fail_forward": "错过月光窗口后仍可通过铁匠的旧钥匙寻找侧门",
                },
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
    assert session.game_state["location_graph"]["current_location_id"] == "矿村井口"
    assert session.game_state["location_graph"]["nodes"][-1]["name"] == "矿村井口"
    assert session.campaign_state["quest_log"] == [
        {"quest": "寻找矿工", "status": "completed", "outcome": "矿工获救"},
        {
            "quest": "调查暗门",
            "status": "active",
            "outcome": "",
            "branch": "井底调查线",
            "next_step": "确认暗门是否会在月光下开启",
            "failure_consequence": "守卫巡逻会提前封锁井口",
            "fail_forward": "错过月光窗口后仍可通过铁匠的旧钥匙寻找侧门",
        },
    ]
    assert session.campaign_state["npc_registry"]["铁匠"] == {
        "relationship": "友好",
        "key_facts": ["欠玩家人情", "愿意修装备"],
        "promises": ["明早带路"],
    }
    assert session.campaign_state["key_decisions"] == ["救下铁匠", "信任铁匠"]
    assert session.campaign_state["world_flags"] == {"met_smith": True, "smith_trusted": True}
    assert [c["text"] for c in session.campaign_state["clues"]] == ["旧钥匙", "暗门在井底"]


@pytest.mark.asyncio
async def test_state_applicator_preserves_scenario_memory_across_several_turns():
    session = Session(
        id="session-memory",
        module_id="module-1",
        game_state={},
        campaign_state={},
    )
    applicator = StateApplicator(FakeDb())

    turns = [
        {
            "narrative": "Captain Mira admits the eclipse gate was sealed beneath the old observatory.",
            "campaign_delta": {
                "quest_updates": [
                    {"quest": "Find the Eclipse Gate", "status": "active", "outcome": ""}
                ],
                "npc_updates": [
                    {
                        "name": "Captain Mira",
                        "relationship": "wary ally",
                        "key_facts": ["Knows the old observatory route"],
                        "promises": ["Will wait at the east stair"],
                    }
                ],
                "key_decisions_add": ["Trusted Captain Mira with the moon-sigil clue"],
                "clues_add": [{"text": "The gate is below the old observatory", "category": "location"}],
                "scene_vibe": {
                    "location": "Lantern Archive",
                    "time_of_day": "midnight",
                    "tension": "tense",
                },
            },
        },
        {
            "narrative": "The party follows Mira's directions and finds a cracked moon-sigil in the observatory.",
            "campaign_delta": {
                "quest_updates": [
                    {"quest": "Find the Eclipse Gate", "status": "active", "outcome": "Reached the observatory"}
                ],
                "npc_updates": [
                    {
                        "name": "Captain Mira",
                        "relationship": "trusted",
                        "key_facts": ["Knows the old observatory route"],
                        "promises": ["Will wait at the east stair"],
                    }
                ],
                "clues_add": [
                    {"text": "A cracked moon-sigil matches the archive sketch", "category": "item"}
                ],
                "scene_vibe": {
                    "location": "Old Observatory",
                    "time_of_day": "pre-dawn",
                    "tension": "danger",
                },
            },
        },
        {
            "narrative": "Mira keeps her promise, and the moon-sigil opens the stair to the sealed gate.",
            "campaign_delta": {
                "quest_updates": [
                    {"quest": "Find the Eclipse Gate", "status": "completed", "outcome": "Gate entrance found"}
                ],
                "npc_updates": [
                    {
                        "name": "Captain Mira",
                        "relationship": "trusted",
                        "key_facts": ["Kept her promise at the east stair"],
                        "promises": [],
                    }
                ],
                "key_decisions_add": ["Used the cracked moon-sigil instead of forcing the gate"],
                "world_flags_set": {"eclipse_gate_found": True},
                "scene_vibe": {
                    "location": "Eclipse Gate",
                    "time_of_day": "dawn",
                    "tension": "focused",
                },
            },
        },
    ]

    for turn in turns:
        await applicator.apply(session, json.dumps(turn, ensure_ascii=False), characters=[])

    assert session.campaign_state["quest_log"] == [
        {"quest": "Find the Eclipse Gate", "status": "completed", "outcome": "Gate entrance found"}
    ]
    assert session.campaign_state["npc_registry"]["Captain Mira"] == {
        "relationship": "trusted",
        "key_facts": [
            "Knows the old observatory route",
            "Kept her promise at the east stair",
        ],
        "promises": ["Will wait at the east stair"],
    }
    assert session.campaign_state["key_decisions"] == [
        "Trusted Captain Mira with the moon-sigil clue",
        "Used the cracked moon-sigil instead of forcing the gate",
    ]
    assert [clue["text"] for clue in session.campaign_state["clues"]] == [
        "The gate is below the old observatory",
        "A cracked moon-sigil matches the archive sketch",
    ]
    assert session.campaign_state["world_flags"] == {"eclipse_gate_found": True}
    assert session.game_state["scene_vibe"] == {
        "location": "Eclipse Gate",
        "time_of_day": "dawn",
        "tension": "focused",
    }
    assert session.game_state["location_graph"]["current_location_id"] == "eclipse_gate"
    assert [node["name"] for node in session.game_state["location_graph"]["nodes"][-3:]] == [
        "Lantern Archive",
        "Old Observatory",
        "Eclipse Gate",
    ]
    assert "Captain Mira admits" in session.session_history
    assert "moon-sigil opens the stair" in session.session_history


@pytest.mark.asyncio
async def test_state_applicator_tags_location_exit_choices_after_apply():
    session = Session(
        id="session-location-choice",
        module_id="module-1",
        game_state={
            "location_graph": {
                "version": 1,
                "current_location_id": "gate",
                "nodes": [
                    {"id": "gate", "name": "Gatehouse", "visited": True},
                    {"id": "yard", "name": "Training Yard", "visited": False},
                ],
                "edges": [{"from": "gate", "to": "yard", "type": "sequence"}],
            },
        },
        campaign_state={},
    )
    applicator = StateApplicator(FakeDb())

    applied = await applicator.apply(
        session,
        json.dumps({
            "action_type": "movement",
            "narrative": "The gate opens toward the practice yard.",
            "needs_check": {"required": False},
            "state_delta": {},
            "player_choices": ["Go to the Training Yard"],
        }),
        characters=[],
    )

    assert applied.player_choices[0]["text"] == "Go to the Training Yard"
    assert applied.player_choices[0]["choice_type"] == "movement"
    assert applied.player_choices[0]["location_exit"]["target_location_id"] == "yard"


@pytest.mark.asyncio
async def test_state_applicator_persists_scene_vibe_route_metadata():
    session = Session(
        id="session-runtime-route",
        module_id="module-1",
        game_state={
            "location_graph": {
                "version": 1,
                "current_location_id": "gate",
                "nodes": [{"id": "gate", "name": "Gatehouse", "visited": True}],
                "edges": [],
            },
        },
        campaign_state={},
    )
    applicator = StateApplicator(FakeDb())

    await applicator.apply(
        session,
        json.dumps({
            "narrative": "The ironbound door opens into a sealed vault.",
            "campaign_delta": {
                "scene_vibe": {
                    "location": "Sealed Vault",
                    "location_id": "vault",
                    "time_of_day": "midnight",
                    "tension": "danger",
                    "route": {
                        "type": "locked",
                        "label": "Ironbound Door",
                        "requires_key": "Gate Token",
                        "locked": True,
                        "one_way": True,
                    },
                },
            },
            "state_delta": {},
            "player_choices": [],
        }),
        characters=[],
    )

    graph = session.game_state["location_graph"]
    assert graph["current_location_id"] == "vault"
    assert graph["nodes"][-1]["id"] == "vault"
    assert graph["nodes"][-1]["name"] == "Sealed Vault"
    assert graph["edges"][-1] == {
        "from": "gate",
        "to": "vault",
        "type": "locked",
        "label": "Ironbound Door",
        "requires_key": "Gate Token",
        "locked": True,
        "one_way": True,
    }
