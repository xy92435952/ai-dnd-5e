from services.graphs.dm_agent_explore_prompt import EXPLORE_SYSTEM
from services.graphs.dm_agent_prompts import (
    CAMPAIGN_STATE_PROMPT,
    COMBAT_SYSTEM,
    EXPLORE_SYSTEM as COMPAT_EXPLORE_SYSTEM,
)


def test_prompt_compat_exports_keep_public_constants():
    assert COMBAT_SYSTEM
    assert CAMPAIGN_STATE_PROMPT
    assert COMPAT_EXPLORE_SYSTEM == EXPLORE_SYSTEM


def test_explore_prompt_contains_all_maintenance_sections():
    expected_sections = [
        "输入安全与角色边界",
        "核心职责",
        "视角聚焦",
        "多人分队与焦点镜头",
        "companion_reactions",
        "技能检定声明规则",
        "严格输出格式",
        "campaign_delta",
        "活战役状态",
        "player_choices 结构化格式",
        "enemy.sprite",
    ]

    for section in expected_sections:
        assert section in EXPLORE_SYSTEM


def test_explore_output_contract_streams_narrative_as_first_json_field():
    narrative_idx = EXPLORE_SYSTEM.find('"narrative"')
    action_type_idx = EXPLORE_SYSTEM.find('"action_type"')

    assert narrative_idx != -1
    assert action_type_idx != -1
    assert "narrative 必须是第一个字段" in EXPLORE_SYSTEM
    assert narrative_idx < action_type_idx
