import json

from services.graphs.module_parser import _try_parse_json as facade_try_parse_json
from services.graphs.module_parser_helpers import (
    _fill_monster_defaults,
    _merge_module_partials,
    _split_module_data_for_chunks,
    _split_module_text,
    _try_parse_json,
)


def test_try_parse_json_repairs_code_block_and_inner_quotes():
    payload = '```json\n{"name": "酒馆", "setting": "老板说"欢迎"后离开"}\n```'

    parsed = _try_parse_json(payload)

    assert parsed["name"] == "酒馆"
    assert "欢迎" in parsed["setting"]
    assert facade_try_parse_json(payload) == parsed


def test_split_module_text_prefers_markdown_sections():
    text = "前言\n\n## 第一幕\n" + "A" * 20 + "\n\n## 第二幕\n" + "B" * 20

    segments = _split_module_text(text, max_chars=30)

    assert len(segments) == 3
    assert segments[1].startswith("## 第一幕")
    assert segments[2].startswith("## 第二幕")


def test_merge_module_partials_deduplicates_named_entities_and_reorders_scenes():
    merged = _merge_module_partials([
        {
            "name": "矿洞",
            "level_min": 3,
            "level_max": 4,
            "recommended_party_size": 4,
            "scenes": [{"name": "入口", "order": 7}],
            "npcs": [{"name": "莉亚", "role": "村长", "personality": "谨慎"}],
            "monsters": [{"name": "哥布林", "cr": 0.25}],
            "magic_items": [{"name": "月光剑", "type": "武器"}],
            "key_rewards": ["地图"],
        },
        {
            "level_min": 1,
            "level_max": 6,
            "scenes": [{"name": "深处", "order": 99}],
            "npcs": [{"name": "莉亚", "role": "村长", "personality": "非常谨慎且善良"}],
            "monsters": [{"name": "哥布林", "cr": 0.25}],
            "magic_items": [{"name": "月光剑", "type": "武器"}],
            "key_rewards": ["地图", "钥匙"],
        },
    ])

    assert [scene["order"] for scene in merged["scenes"]] == [0, 1]
    assert merged["level_min"] == 1
    assert merged["level_max"] == 6
    assert len(merged["npcs"]) == 1
    assert merged["npcs"][0]["personality"] == "非常谨慎且善良"
    assert len(merged["monsters"]) == 1
    assert merged["key_rewards"] == ["地图", "钥匙"]


def test_split_module_data_for_chunks_keeps_monsters_only_in_first_batch():
    module_data = {
        "name": "大模组",
        "scenes": [{"name": f"场景{i}"} for i in range(3)],
        "npcs": [{"name": f"NPC{i}"} for i in range(2)],
        "magic_items": [{"name": f"物品{i}"} for i in range(2)],
        "monsters": [{"name": "巨魔"}],
    }

    batches = _split_module_data_for_chunks(module_data, items_per_batch=3)

    assert len(batches) == 3
    assert batches[0]["monsters"] == [{"name": "巨魔"}]
    assert batches[1]["monsters"] == []
    assert batches[2]["monsters"] == []


def test_fill_monster_defaults_adds_combat_ready_fields():
    monster = _fill_monster_defaults({"name": "影兽", "cr": 2, "hp": 22})

    assert monster["ability_scores"]["str"] >= 10
    assert monster["actions"][0]["attack_bonus"] >= 2
    assert monster["known_spells"] == []
    assert monster["cantrips"] == []
    assert monster["spell_slots"] == {}
    assert monster["spell_ability"] is None
    assert monster["spell_save_dc"] is None
    assert monster["hp_dice"]
    assert monster["tactics"]
    json.dumps(monster, ensure_ascii=False)
