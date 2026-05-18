import json

from config import Settings
from services.context_builder_memory import build_module_context


class FakeModule:
    name = "长模组"
    parsed_content = {
        "setting": "被风暴环绕的群岛",
        "tone": "阴郁悬疑",
        "plot_summary": "玩家正在调查灯塔失踪案。",
        "scenes": [
            {"title": "灯塔入口", "description": "门上刻着新鲜划痕。"},
            {"title": "海蚀洞", "description": "潮水掩盖脚印。"},
        ],
        "npcs": [
            {"name": f"NPC{i}", "role": "村民", "secret": "x" * 200}
            for i in range(8)
        ],
        "monsters": [
            {"name": f"Monster{i}", "hp": 20, "trait": "y" * 200}
            for i in range(8)
        ],
        "magic_items": [
            {"name": f"Item{i}", "effect": "z" * 200}
            for i in range(8)
        ],
    }


class FakeSession:
    current_scene = "灯塔入口"


def test_build_module_context_keeps_scene_and_caps_large_lists():
    payload = build_module_context(module=FakeModule(), session=FakeSession())

    assert payload["current_scene"] == "灯塔入口"
    assert payload["scene"] == {"title": "灯塔入口", "description": "门上刻着新鲜划痕。"}
    assert len(payload["npcs"]) == 3
    assert len(payload["monsters"]) == 3
    assert len(payload["magic_items"]) == 2
    assert "module_context_omitted" in payload


def test_build_module_context_stays_under_prompt_budget():
    payload = build_module_context(module=FakeModule(), session=FakeSession())
    encoded = json.dumps(payload, ensure_ascii=False)

    assert len(encoded) <= Settings(_env_file=None).module_context_max_chars


def test_default_module_context_budget_prioritizes_dm_quality():
    assert Settings(_env_file=None).module_context_max_chars >= 6000


def test_build_module_context_preserves_rich_current_scene_when_budget_allows(monkeypatch):
    scene_description = "灯塔石阶上覆盖盐霜，墙面刻着三枚倒置星纹。" * 120

    class RichSceneModule(FakeModule):
        parsed_content = {
            **FakeModule.parsed_content,
            "scenes": [
                {"title": "灯塔入口", "description": scene_description},
            ],
            "npcs": [
                {
                    "name": "艾莲娜",
                    "role": "灯塔守望者",
                    "summary": "她知道失踪船员最后一次出现的位置。",
                    "description": "她总是避开关于倒置星纹的问题。",
                    "personality": "谨慎但愿意帮助真诚的冒险者。",
                },
            ],
        }

    from services import context_builder_memory

    monkeypatch.setattr(context_builder_memory.settings, "module_context_max_chars", 6000)
    payload = build_module_context(module=RichSceneModule(), session=FakeSession())
    encoded = json.dumps(payload, ensure_ascii=False)

    assert len(encoded) <= 6000
    assert len(payload["scene"]["description"]) > 1000
    assert payload["npcs"][0]["summary"] == "她知道失踪船员最后一次出现的位置。"


def test_build_module_context_keeps_extreme_scene_under_prompt_budget(monkeypatch):
    class ExtremeModule(FakeModule):
        parsed_content = {
            **FakeModule.parsed_content,
            "setting": "设定" * 500,
            "plot_summary": "剧情" * 800,
            "scenes": [
                {"title": "灯塔入口", "description": "场景细节" * 800},
            ],
            "npcs": [
                {
                    "name": "冗长 NPC",
                    "role": "村民" * 80,
                    "summary": "摘要" * 160,
                    "description": "描述" * 240,
                    "personality": "性格" * 160,
                }
                for _ in range(5)
            ],
        }

    from services import context_builder_memory

    monkeypatch.setattr(context_builder_memory.settings, "module_context_max_chars", 2200)
    payload = build_module_context(module=ExtremeModule(), session=FakeSession())
    encoded = json.dumps(payload, ensure_ascii=False)

    assert len(encoded) <= 2200
    assert "truncated_to_prompt_budget" in payload["module_context_omitted"]
