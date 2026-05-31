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
        "companion_updates": [
            {
                "name": "艾琳",
                "character_id": "ally-1",
                "relationship": "信任",
                "approval_delta": "8",
                "reason": "玩家保护了平民",
                "personal_quest": {
                    "title": "月下旧誓",
                    "status": "active",
                    "detail": "她提到旧誓约仍未完成",
                    "next_step": "询问银叶徽记",
                },
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
        "companion_updates": [
            {
                "name": "艾琳",
                "character_id": "ally-1",
                "relationship": "信任",
                "approval": None,
                "approval_delta": 8,
                "reason": "玩家保护了平民",
                "personal_quest": {
                    "title": "月下旧誓",
                    "status": "active",
                    "detail": "她提到旧誓约仍未完成",
                    "next_step": "询问银叶徽记",
                },
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


def test_normalize_campaign_delta_preserves_branching_quest_metadata():
    delta = normalize_campaign_delta({
        "quest_updates": [
            {
                "quest": "守住营地",
                "status": "blocked",
                "outcome": "",
                "branch": "后撤线",
                "next_step": "护送幸存者进入旧矿道",
                "consequence": "营地外圈已经失守",
                "failure_consequence": "拖延会让狼群追上伤员",
                "fail_forward": "即使营地失守，幸存者仍能在旧矿道重组防线",
                "detail": "防守目标转为撤退目标",
            }
        ],
    })

    assert delta["quest_updates"] == [
        {
            "quest": "守住营地",
            "status": "blocked",
            "outcome": "",
            "branch": "后撤线",
            "next_step": "护送幸存者进入旧矿道",
            "consequence": "营地外圈已经失守",
            "failure_consequence": "拖延会让狼群追上伤员",
            "fail_forward": "即使营地失守，幸存者仍能在旧矿道重组防线",
            "detail": "防守目标转为撤退目标",
        }
    ]


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


def test_apply_campaign_delta_merges_branching_quest_hooks():
    existing = {
        "quest_log": [
            {
                "quest": "守住营地",
                "status": "active",
                "outcome": "",
                "branch": "正面防守",
                "next_step": "守住东侧木门",
            }
        ],
    }

    merged = apply_campaign_delta(existing, {
        "quest_updates": [
            {
                "quest": "守住营地",
                "status": "failed",
                "outcome": "狼群冲破外圈，幸存者退入旧矿道。",
                "branch": "失败后撤退线",
                "next_step": "护送幸存者穿过矿道岔路。",
                "failure_consequence": "伤员会拖慢队伍并吸引追踪。",
                "fail_forward": "营地失守后，旧矿道成为新的防线和线索入口。",
            }
        ],
    }, now_iso="2026-06-01T01:00:00Z")

    assert merged["quest_log"] == [
        {
            "quest": "守住营地",
            "status": "failed",
            "outcome": "狼群冲破外圈，幸存者退入旧矿道。",
            "branch": "失败后撤退线",
            "next_step": "护送幸存者穿过矿道岔路。",
            "failure_consequence": "伤员会拖慢队伍并吸引追踪。",
            "fail_forward": "营地失守后，旧矿道成为新的防线和线索入口。",
        }
    ]
    assert merged["recent_updates"] == [
        {
            "type": "quest",
            "label": "守住营地",
            "detail": "狼群冲破外圈，幸存者退入旧矿道。",
            "at": "2026-06-01T01:00:00Z",
            "status": "failed",
            "branch": "失败后撤退线",
        }
    ]


def test_apply_campaign_delta_merges_companion_bonds_and_personal_quest_hooks():
    existing = {
        "companion_bonds": {
            "ally-1": {
                "name": "艾琳",
                "character_id": "ally-1",
                "approval": 12,
                "relationship": "谨慎盟友",
                "personal_quest": {"title": "月下旧誓", "status": "rumor"},
            },
        },
    }

    merged = apply_campaign_delta(existing, {
        "companion_updates": [
            {
                "name": "艾琳",
                "character_id": "ally-1",
                "relationship": "信任",
                "approval_delta": 6,
                "reason": "玩家尊重了她的侦察判断",
                "personal_quest": {
                    "title": "月下旧誓",
                    "status": "active",
                    "detail": "她愿意解释银叶徽记的来源",
                    "next_step": "在安全营地单独交谈",
                },
            },
            {
                "name": "博恩",
                "approval": -4,
                "reason": "玩家拒绝救援俘虏",
            },
        ],
    }, now_iso="2026-06-01T00:00:00Z")

    assert merged["companion_bonds"]["ally-1"] == {
        "name": "艾琳",
        "character_id": "ally-1",
        "approval": 18,
        "relationship": "信任",
        "last_approval_delta": 6,
        "last_approval_reason": "玩家尊重了她的侦察判断",
        "personal_quest": {
            "title": "月下旧誓",
            "status": "active",
            "detail": "她愿意解释银叶徽记的来源",
            "next_step": "在安全营地单独交谈",
        },
    }
    assert merged["companion_bonds"]["博恩"] == {
        "name": "博恩",
        "approval": -4,
        "last_approval_reason": "玩家拒绝救援俘虏",
    }
    assert merged["recent_updates"] == [
        {
            "type": "companion",
            "label": "艾琳",
            "detail": "信任 / 好感+6 / 玩家尊重了她的侦察判断",
            "at": "2026-06-01T00:00:00Z",
        },
        {
            "type": "companion",
            "label": "博恩",
            "detail": "玩家拒绝救援俘虏",
            "at": "2026-06-01T00:00:00Z",
        },
    ]
