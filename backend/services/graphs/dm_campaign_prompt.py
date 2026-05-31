"""Prompt for extracting durable campaign state from adventure history."""

CAMPAIGN_STATE_PROMPT = """
请分析以上冒险记录，提取关键信息，以纯JSON格式输出战役状态摘要。
只输出JSON，不要输出任何其他文字、解释或Markdown标记。

输出格式：
{
  "completed_scenes": ["已完成的场景名称列表"],
  "key_decisions": ["玩家做出的关键决定及后果，每条一句话，最多8条"],
  "npc_registry": {
    "NPC名字": {
      "relationship": "友好/敌对/中立/未知",
      "key_facts": ["关于此NPC的重要信息，最多3条"],
      "promises": ["NPC或玩家做出的承诺，没有则为空数组"]
    }
  },
  "quest_log": [
    {
      "quest": "任务名称",
      "status": "active/completed/failed",
      "outcome": "结果描述，仅completed/failed时填写，active时为空字符串",
      "branch": "当前分支/路线名，没有则为空字符串",
      "next_step": "玩家下一步可推进的方向",
      "consequence": "已发生后果",
      "failure_consequence": "失败或放弃会造成的风险",
      "fail_forward": "失败后仍可继续推进的新局面"
    }
  ],
  "companion_bonds": {
    "AI队友名字或角色ID": {
      "name": "AI队友名字",
      "relationship": "信任/认可/中立/动摇/疏离/复杂/未知",
      "approval": 0,
      "last_approval_reason": "最近一次好感变化原因，没有则为空字符串",
      "personal_quest": {
        "title": "个人任务或羁绊线名称",
        "status": "rumor/active/completed/failed/blocked",
        "detail": "当前状态摘要",
        "next_step": "下一步推进方向"
      }
    }
  },
  "world_flags": {
    "简短事件标签": true
  },
  "notable_items": ["玩家获得或失去的重要物品，最多6条"],
  "party_changes": ["队伍状态的重要变化，如等级提升、成员变动等，最多4条"]
}
"""
