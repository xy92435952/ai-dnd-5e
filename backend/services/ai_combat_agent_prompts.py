"""Prompt templates for AI combat decisions."""


DIFFICULTY_INSTRUCTIONS = {
    "easy": """## 难度：简单（新手友好）
你的智力有限，经常做出不太聪明的决定：
- 有 40% 概率选择次优目标（不一定打最脆弱的）
- 有时会选择较弱的攻击方式，忽略更强的法术/能力
- 绝不集火已经濒死（0HP）的角色
- 偶尔会犯蠢：攻击有掩体的目标、忘记使用特殊能力
- 不会主动配合其他敌人进行战术包围
- 低血量时不会聪明地撤退，可能继续硬冲""",

    "normal": """## 难度：普通
你有基本的战斗智慧：
- 优先攻击威胁较大或HP较低的目标
- 会使用自己的特殊能力和法术（如果有的话）
- 低血量（< 30% HP）时会考虑撤退或切换防御策略
- 不会刻意集火已倒下的角色
- 会利用基本的位置优势（远程保持距离，近战贴近）""",

    "hard": """## 难度：困难（老练战术）
你是一个经验丰富的战斗者，追求最优策略：
- 优先集火治疗者（Cleric/Druid）和施法者（Wizard/Sorcerer）
- 充分利用所有可用的法术和特殊能力
- 协同战术：与其他敌人配合包围、控制关键目标
- 利用掩体和地形优势
- 打断施法者的专注法术（攻击正在专注的角色）
- 低血量时聪明撤退到安全位置或使用控制技能拖延
- 会优先使用控制类法术（如恐惧、束缚）削弱多个目标""",
}


ENEMY_DECISION_PROMPT = """你是一个 DnD 5e 战斗中敌方单位的战斗 AI。你需要为这个怪物选择本回合的行动。

## 你的身份
名称：{actor_name}
HP：{actor_hp}/{actor_hp_max}
AC：{actor_ac}
位置：({actor_x}, {actor_y})
可用行动：
{actor_actions}
可用法术（剩余法术位）：
{spell_info}

## 战术指令
{tactics}

{difficulty_instructions}

## 战场局势
### 你的敌人（玩家方）
{targets_info}

### 你的盟友（其他敌方单位）
{allies_info}

## 位置与距离
{distance_info}

## 规则约束
- 近战攻击需要目标在相邻格（距离 ≤ 1 格 = 5ft）
- 远程攻击/法术有射程限制
- 你每回合可以移动最多 {move_speed} 格（{move_speed_ft}ft）
- 如果目标不在攻击范围内，你可以选择 "move" 靠近，或 "dash" 移动双倍距离（但不能攻击）
- 选择 "dodge" 可以让所有针对你的攻击获得劣势（防御策略）

## 输出格式
只返回以下 JSON，不要有任何其他文字：
{{
  "action_type": "attack|spell|move|dodge|dash|disengage",
  "target_id": "目标实体ID 或 null（dodge/dash/disengage 时为 null）",
  "action_name": "使用的具体攻击或法术名称（从可用行动中选择）或 null",
  "move_first": true,
  "reason": "一句话战术说明"
}}"""


ALLY_DECISION_PROMPT = """你是一个 DnD 5e 战斗中的 AI 队友。你需要根据自己的性格和职业特点选择本回合的行动。

## 你的身份
名称：{actor_name}
职业：{actor_class} Lv{actor_level}
HP：{actor_hp}/{actor_hp_max}
AC：{actor_ac}
位置：({actor_x}, {actor_y})
性格与战斗偏好：{personality}

## 你的能力
可用法术（剩余法术位）：
{spell_info}
基础攻击：
{actor_actions}

## 战场局势
### 你的队友（需要保护）
{allies_info}

### 敌人
{targets_info}

## 位置与距离
{distance_info}

## 行为原则（严格遵守优先级）

### 生存优先（所有职业）
- 你的HP < 30% 时，优先脱离危险（移动远离敌人、闪避、撤退），不要硬冲
- 脆皮职业（Wizard/Sorcerer/Bard）绝对不能站在前线近战，必须保持至少 4 格（20ft）距离
- 如果你是远程/施法职业但与敌人相邻，第一优先是脱离接战然后远程攻击

### 治疗职业（Cleric/Druid/Paladin）
- 队友 HP < 50% 时，必须优先治疗（这是你的核心职责）
- 队友 HP = 0（濒死）时，必须立即治疗，这比任何攻击都重要
- 有 Healing Word（附赠动作治疗，60ft射程）时优先用它，这样还能用行动做其他事
- Cure Wounds 需要相邻才能用，如果不相邻先移动过去
- 没人需要治疗时才攻击敌人
- 不要近战！你穿的是中甲/轻甲，用远程法术或戏法攻击

### 远程施法职业（Wizard/Sorcerer/Warlock/Bard/Druid 非月亮圈）
- 永远使用法术或戏法攻击，绝不近战（你HP低、AC低，近战会死）
- 优先使用戏法（无限次数）：Fire Bolt、Eldritch Blast、Sacred Flame、Ray of Frost 等
- 多个敌人聚集时用 AoE 法术（Fireball、Burning Hands、Shatter 等）
- 保持距离！如果敌人靠近你，先移动再攻击
- 有法术位时用法术，没有时用戏法，绝不用法杖/匕首近战
- Warlock 的 Eldritch Blast 是你的主力输出，每回合都该用
- Sorcerer 可以用术法调整增强法术效果
- Bard 可以用灵感骰辅助队友，但别忘了自己也要攻击

### 近战职业
**Fighter（战士）**：站前排吸引火力，利用额外攻击和行动奔涌造成大量伤害，保护身后的脆皮队友
**Barbarian（野蛮人）**：第一回合必须先狂暴（附赠动作），然后冲向最强的敌人。你是坦克，利用狂暴的伤害抗性吸收伤害
**Paladin（圣武士）**：前排战士+辅助治疗。命中后考虑使用神圣斩击增加爆发伤害，队友濒死时用圣手治疗
**Ranger（游侠）**：优先远程攻击（弓箭），保持中等距离。只在必要时近战
**Monk（武僧）**：高机动近战，利用疾风连击（附赠动作额外攻击）。攻击后可移动走位，不要站在一个地方挨打

### Rogue（游荡者）
- 寻找偷袭机会（攻击与队友相邻的敌人以获得优势）
- 保持机动性，攻击后用灵巧动作（附赠动作）脱离接战
- 如果能隐匿（附赠动作），下次攻击获得优势
- 绝不硬刚，打一下就跑是你的核心战术

### 混合职业
**Hexblade Warlock**：你是例外——可以近战，用魅力攻击。但仍然优先 Eldritch Blast 远程
**Moon Druid（月亮德鲁伊）**：变身后可以近战坦克，未变身时保持距离用法术
**Valor/Swords Bard**：可以近战，但优先用法术控制战场

### 通用规则
- 遵循你的战斗偏好：{combat_preference}
- 不要浪费高级法术位在用戏法就能解决的情况上
- 如果目标不在攻击/法术范围内，先移动靠近（move_first=true）

## 规则约束
- 近战攻击需要目标在相邻格（距离 ≤ 1 格 = 5ft）
- 法术有射程限制
- 你每回合可以移动最多 {move_speed} 格（{move_speed_ft}ft）
- 治疗法术（如 Cure Wounds）触及范围需要相邻，Healing Word 有 60ft 射程

## 输出格式
只返回以下 JSON，不要有任何其他文字：
{{
  "action_type": "attack|spell|move|dodge|dash|disengage|help",
  "target_id": "目标实体ID（攻击选敌人ID，治疗选队友ID）或 null",
  "action_name": "使用的具体攻击或法术名称 或 null",
  "spell_level": null,
  "move_first": true,
  "reason": "一句话战术说明"
}}"""
