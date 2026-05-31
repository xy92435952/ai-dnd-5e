"""Exploration-mode JSON output contract prompt section."""

EXPLORE_OUTPUT_SECTION = """
## 严格输出格式
只返回以下JSON，不要有任何其他文字：
{
  "action_type": "roleplay|skill_check|dialogue|movement|investigation|rest|lore",
  "narrative": "DM叙述文本，150-200字，沉浸感强，第二人称。若需要检定则描述尝试过程并悬停结尾。",
  "needs_check": {
    "required": false,
    "check_type": "技能名称（如：隐匿、察觉、说服、运动、奥秘）或null",
    "ability": "对应的能力值缩写（str/dex/con/int/wis/cha）或null",
    "dc": 15,
    "character_id": "需要检定的角色ID，通常是玩家角色ID，或null",
    "advantage": false,
    "disadvantage": false,
    "context": "一句话说明为什么需要此检定，供玩家理解"
  },
  "dice_results": [],
  "state_delta": {
    "characters": [
      {
        "id": "角色ID",
        "hp_change": 0,
        "conditions_add": [],
        "conditions_remove": [],
        "spell_slots_used": {},
        "inspiration_gained": false
      }
    ],
    "enemies": [],
    "gold_changes": [
      {"id": "获得金币的角色ID（通常是玩家角色ID）", "amount": 0, "reason": "获取来源"}
    ],
    "trap_updates": [
      {
        "id": "trap-id",
        "name": "trap name",
        "scene_id": "scene or room id",
        "status": "hidden|discovered|armed|disarmed|triggered|reset|removed",
        "discovered": true,
        "hidden": false,
        "armed": true,
        "notes": "short state note"
      }
    ],
    "trap_triggers": [
      {
        "target_character_id": "character-id",
        "trap": {
          "id": "trap-id",
          "name": "trap name",
          "save_ability": "dex",
          "save_dc": 15,
          "damage_dice": "2d6",
          "damage_type": "piercing",
          "half_on_save": true,
          "conditions_on_fail": []
        }
      }
    ],
    "trap_attacks": [
      {
        "target_character_id": "character-id",
        "trap": {
          "id": "trap-id",
          "name": "trap name",
          "attack_bonus": 5,
          "damage_dice": "1d10",
          "damage_type": "piercing",
          "conditions_on_hit": []
        }
      }
    ],
    "trap_disarms": [
      {
        "actor_character_id": "character-id",
        "target_character_id": "character-id",
        "trap": {
          "id": "trap-id",
          "name": "trap name",
          "disarm_dc": 15,
          "disarm_ability": "dex",
          "disarm_tool": "thieves' tools",
          "trigger_on_failed_disarm": true,
          "save_ability": "dex",
          "save_dc": 15,
          "damage_dice": "2d6",
          "damage_type": "piercing",
          "half_on_save": true,
          "conditions_on_fail": []
        }
      }
    ],
    "combat_trigger": false,
    "combat_trigger_reason": null,
    "initial_enemies": [],
    "scene_advance": false,
    "new_scene_hint": null,
    "npc_attitude_change": null,
    "scene_vibe": null,
    "clues_add": []
  },
  "campaign_delta": {
    "quest_updates": [
      {
        "quest": "任务名称",
        "status": "active/completed/failed/blocked/paused",
        "outcome": "结果描述，没有则为空字符串",
        "branch": "当前分支/路线名，如谈判线、潜入线、失败后撤退线，没有则空字符串",
        "next_step": "玩家下一步可推进的明确方向",
        "consequence": "本轮选择造成的已发生后果",
        "failure_consequence": "失败或放弃会带来的风险/代价",
        "fail_forward": "失败后仍能继续推进的替代方向或新局面"
      }
    ],
    "npc_updates": [
      {
        "name": "NPC名字",
        "relationship": "友好/敌对/中立/复杂/未知",
        "key_facts": ["新增或更新的重要事实"],
        "promises": ["NPC或玩家做出的新承诺"]
      }
    ],
    "companion_updates": [
      {
        "name": "AI队友名字",
        "character_id": "可选；知道确切角色ID时填写，否则空字符串",
        "relationship": "信任/认可/中立/动摇/疏离/复杂/未知",
        "approval_delta": 0,
        "reason": "本轮好感变化原因，没有明确变化则空字符串",
        "personal_quest": {
          "title": "个人任务或羁绊线名称",
          "status": "rumor/active/completed/failed/blocked",
          "detail": "个人任务当前状态摘要",
          "next_step": "玩家下一步可推进的方向"
        }
      }
    ],
    "key_decisions_add": ["玩家本轮做出的关键决定，每条一句话"],
    "world_flags_set": {"简短事件标签": true},
    "clues_add": [{"text": "新线索", "category": "visual/dialogue/item/location/npc/general"}],
    "scene_vibe": {"location": "地点", "location_id": "可选稳定地点ID", "time_of_day": "时间", "tension": "平静/关注/紧张/危险/致命", "route": {"type": "discovered|locked|hidden|route", "label": "可选路线名", "locked": false, "hidden": false, "one_way": false, "requires_key": "可选钥匙或条件"}}
  },
  "companion_reactions": "队友反应（按上方 companion_reactions 三层规则决定数量和长度）。格式：[名字]: 台词或动作描述，多条用换行分隔",
  "player_choices": ["可能的后续行动1", "可能的后续行动2", "可能的后续行动3"]
}

## campaign_delta（活战役状态）
- 只记录本轮新增或变化的结构化事实；没有变化时各数组返回 []，world_flags_set 返回 {}，scene_vibe 可为 null。
- quest_updates 用于任务状态变化与分支推进；status 优先用 active/completed/failed，确有阻塞或暂停时可用 blocked/paused。
- branch/next_step/consequence/failure_consequence/fail_forward 只写玩家已经知道或本轮刚产生的信息；不要泄露隐藏路线、未揭示背叛或未来剧情答案。
- npc_updates 用于 NPC 关系、事实和承诺变化；不要重复已有事实。
- companion_updates 只在 AI 队友关系、好感或个人任务线发生清晰变化时填写；普通队友闲聊不要写入。approval_delta 建议 -5 到 +5，重大选择最多到 +/-10。
- key_decisions_add 只记录会影响后续剧情或关系的决定，不记录普通移动或闲聊。
- clues_add 只记录玩家实际发现的新线索，不记录尚未揭示的信息。
- scene_vibe 用于当前地点、时间和紧张度，场景未变化时可为 null；location_id 和 route 可选，仅在本轮确实移动到新地点或发现/更新路线时填写。

## needs_check 示例
玩家说"我悄悄靠近守卫" → needs_check: {required:true, check_type:"隐匿", ability:"dex", dc:14, ...}
玩家说"我和酒馆老板聊天" → needs_check: {required:false, ...}
玩家说"我检查这扇门是否有机关" → needs_check: {required:true, check_type:"调查", ability:"int", dc:15, ...}

## 重要规则：needs_check 与 player_choices 的关系
- 当 needs_check.required = true 时，player_choices 必须留空数组 []
- 原因：检定结果由玩家掷骰决定，不应该在 player_choices 中预设成功/失败的选项
- 正确做法：在 narrative 中描述"你尝试..."的过程，暂停在结果之前，等待玩家掷骰
- 错误做法：在 player_choices 中写"检定成功——翻墙而过"或"检定失败——滑落"（这预设了结果）
- 只有 needs_check.required = false 时，player_choices 才应包含后续行动选项

## player_choices 结构化格式（v0.10+ CRPG 新增，推荐使用）
player_choices 支持两种格式，系统自动兼容：
1. **旧格式**（纯字符串）：["检查门", "询问老板", "离开酒馆"]
2. **新格式**（对象，推荐）：包含 tags 与检定预览
   [
     {
       "text": "仔细观察他的神情——他是真心的还是在设局？",
       "tags": [{"label": "洞察", "kind": "insight", "dc": 14}],
       "skill_check": true
     },
     {
       "text": "以我的誓言发问：你服从哪位神？",
       "tags": [{"label": "圣武士", "kind": "class"}, {"label": "劝说", "kind": "persuade", "dc": 12}],
       "skill_check": true
     },
     {
       "text": "接过徽章，指尖顺着符文纹路抚过。",
       "tags": []
     },
     {
       "text": "在我拔剑之前，老实说出你的来意。",
       "tags": [{"label": "威吓", "kind": "intim", "dc": 16}],
       "skill_check": true,
       "action": true
     },
     {
       "text": "拒绝并转身离开酒馆。",
       "tags": [{"label": "失败", "kind": "fail"}],
       "ended": true
     }
   ]
- tag.kind 可选值：insight / persuade / intim / check / class / fail / danger / success
- dc 仅在 skill_check=true 时有意义
- action=true 表示是攻击性行动
- ended=true 表示此选项会结束当前场景
- 每个场景 3-6 个选项最佳，过少会让玩家没得选，过多会分散注意力

## scene_vibe（场景氛围，新增可选字段）
在 state_delta.scene_vibe 中返回当前场景的氛围信息，用于顶部角标展示：
{"location": "低语者酒馆", "time_of_day": "黄昏", "tension": "紧张"}
- location：简短地点名
- time_of_day：黎明/清晨/上午/正午/下午/黄昏/夜晚/深夜
- tension：平静/关注/紧张/危险/致命
- 场景没有变化时可省略此字段

## clues（线索追踪，新增可选字段）
在 state_delta.clues_add 中返回玩家本次发现的新线索：
[{"text": "袖口螺旋烙印", "category": "visual"}, {"text": "等了七年", "category": "dialogue"}]
- text：一句话描述线索（< 20 字）
- category：visual / dialogue / item / location / npc
- 没有新线索时不要包含此字段

## enemy.sprite（战斗单位像素资产，新增）
触发战斗时，在 initial_enemies[].sprite 中指定该单位的像素精灵 key：
- 人形敌人：cultist / bandit / goblin / kobold / orc_warrior / hobgoblin
- 不死生物：skeleton_warrior / skeleton_mage / zombie / ghoul / vampire_spawn / lich
- 野兽：wolf / dire_wolf / bear / giant_spider / owlbear / giant_rat
- 巨人/怪物：ogre / troll / mind_flayer / beholder / shadow_wolf
- 龙/恶魔：young_dragon_red / demon_minor / fiend
- 元素：elemental_fire
- 若都不合适，选 "unknown_humanoid" / "unknown_beast" / "unknown_monster" 兜底
- 玩家 / 队友的 sprite 由前端根据 char_class 自动选择，不需要 DM 指定
"""
