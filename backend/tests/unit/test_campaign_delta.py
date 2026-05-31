from services.campaign_delta import apply_campaign_delta, normalize_campaign_delta


def test_normalize_campaign_delta_repairs_bad_shapes():
    delta = normalize_campaign_delta({
        "quest_updates": {"quest": "坏形状"},
        "npc_updates": [
            {
                "name": "铁匠",
                "relationship": "友好",
                "key_facts": "知道暗门",
                "promises": ["明早带路"],
            },
            {"relationship": "缺少名字"},
        ],
        "key_decisions_add": "玩家选择信任铁匠",
        "world_flags_set": ["bad"],
        "clues_add": [{"text": "暗门在井底"}, {"category": "missing text"}],
        "scene_vibe": "tense",
    })

    assert delta == {
        "quest_updates": [],
        "npc_updates": [
            {
                "name": "铁匠",
                "relationship": "友好",
                "key_facts": ["知道暗门"],
                "promises": ["明早带路"],
            }
        ],
        "key_decisions_add": [],
        "world_flags_set": {},
        "clues_add": [{"text": "暗门在井底", "category": "general"}],
        "scene_vibe": None,
    }


def test_normalize_campaign_delta_preserves_scene_route_metadata():
    delta = normalize_campaign_delta({
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
                "dc": "14",
                "check_type": "athletics",
            },
        },
    })

    assert delta["scene_vibe"] == {
        "location": "Sealed Vault",
        "time_of_day": "midnight",
        "tension": "danger",
        "location_id": "vault",
        "route": {
            "type": "locked",
            "label": "Ironbound Door",
            "requires_key": "Gate Token",
            "check_type": "athletics",
            "dc": 14,
            "locked": True,
            "one_way": True,
        },
    }


def test_apply_campaign_delta_merges_quests_npcs_flags_decisions_and_clues():
    existing = {
        "quest_log": [{"quest": "寻找矿工", "status": "active", "outcome": ""}],
        "npc_registry": {
            "铁匠": {
                "relationship": "中立",
                "key_facts": ["欠玩家人情"],
                "promises": [],
            },
        },
        "key_decisions": ["救下铁匠"],
        "world_flags": {"met_smith": True},
        "clues": [{"text": "旧钥匙", "category": "item", "is_new": False}],
    }

    merged = apply_campaign_delta(existing, {
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
        "key_decisions_add": ["救下铁匠", "信任铁匠"],
        "world_flags_set": {"smith_trusted": True},
        "clues_add": [
            {"text": "旧钥匙", "category": "item"},
            {"text": "暗门在井底", "category": "location"},
        ],
    }, now_iso="2026-05-08T00:00:00Z")

    assert merged["quest_log"] == [
        {"quest": "寻找矿工", "status": "completed", "outcome": "矿工获救"},
        {"quest": "调查暗门", "status": "active", "outcome": ""},
    ]
    assert merged["npc_registry"]["铁匠"] == {
        "relationship": "友好",
        "key_facts": ["欠玩家人情", "愿意修装备"],
        "promises": ["明早带路"],
    }
    assert merged["key_decisions"] == ["救下铁匠", "信任铁匠"]
    assert merged["world_flags"] == {"met_smith": True, "smith_trusted": True}
    assert merged["clues"] == [
        {"text": "旧钥匙", "category": "item", "is_new": False},
        {
            "text": "暗门在井底",
            "category": "location",
            "found_at": "2026-05-08T00:00:00Z",
            "is_new": True,
        },
    ]
    assert merged["recent_updates"] == [
        {
            "type": "quest",
            "label": "寻找矿工",
            "detail": "矿工获救",
            "at": "2026-05-08T00:00:00Z",
            "status": "completed",
        },
        {
            "type": "quest",
            "label": "调查暗门",
            "detail": "active",
            "at": "2026-05-08T00:00:00Z",
            "status": "active",
        },
        {
            "type": "npc",
            "label": "铁匠",
            "detail": "友好 / 愿意修装备",
            "at": "2026-05-08T00:00:00Z",
        },
        {
            "type": "decision",
            "label": "信任铁匠",
            "detail": "关键决定",
            "at": "2026-05-08T00:00:00Z",
        },
        {
            "type": "world",
            "label": "smith_trusted",
            "detail": "已触发",
            "at": "2026-05-08T00:00:00Z",
        },
        {
            "type": "clue",
            "label": "暗门在井底",
            "detail": "location",
            "at": "2026-05-08T00:00:00Z",
        },
    ]
