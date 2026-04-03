"""
战斗叙事生成器 — 将机械式战斗结果转化为生动的叙事描述
使用 LLM 为每个战斗行动生成沉浸式文本，同时保留原始机械数据。
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from services.llm import get_llm

logger = logging.getLogger(__name__)

NARRATOR_SYSTEM = """你是一位经验丰富的DnD地下城主，擅长用生动、简洁的语言描述战斗场景。

你的任务是将战斗行动的机械结果转化为沉浸式的叙事描述。

规则：
- 每次描述控制在1-3句话（40-80字）
- 使用具体的动作描写（武器挥砍的角度、法术的视觉效果、闪避的姿态）
- 暴击时描述要特别精彩和有冲击力
- 大失手时要有戏剧性的滑稽或危险感
- 未命中时根据差距描写：险些命中vs轻松躲开
- 法术要有魔法视觉效果描写（光芒、火焰、寒冰等）
- 治疗法术要有温暖、神圣的光辉感
- 保持紧张感和节奏感，像在讲述一个史诗故事
- 偶尔加入环境互动描写（火花溅落、地面震动、空气中的魔力波动）
- 不要重复使用相同的描述方式
- 不要使用emoji
- 只返回叙事文本，不要有任何额外标记或解释"""

NARRATE_TEMPLATE = """战斗情况：
攻击者：{actor_name}（{actor_class}）
目标：{target_name}
行动类型：{action_type}
{details}

请用生动的语言描述这个战斗瞬间："""

BATCH_TEMPLATE = """以下是本回合所有AI控制角色的行动，请为每个行动生成一段生动描述，用换行分隔：

{actions}

为每个行动各写1-2句生动描述，按序号排列，每个描述独占一行，格式为"序号. 描述"："""


async def narrate_action(
    actor_name: str,
    actor_class: str,
    target_name: str,
    action_type: str,
    hit: bool = False,
    is_crit: bool = False,
    is_fumble: bool = False,
    damage: int = 0,
    damage_type: str = "",
    spell_name: str = "",
    heal_amount: int = 0,
    extra_details: str = "",
) -> str:
    """为单个战斗行动生成生动叙事。失败时返回 fallback 机械描述。"""
    # 构建详情
    details_parts = []
    if action_type == "attack":
        if is_crit:
            details_parts.append("结果：暴击！")
        elif is_fumble:
            details_parts.append("结果：大失手！")
        elif hit:
            details_parts.append(f"结果：命中，造成 {damage} 点{damage_type}伤害")
        else:
            details_parts.append("结果：未命中")
    elif action_type == "spell":
        details_parts.append(f"法术：{spell_name}")
        if heal_amount > 0:
            details_parts.append(f"治疗量：{heal_amount}")
        elif damage > 0:
            details_parts.append(f"伤害：{damage} 点{damage_type}伤害")
    elif action_type == "dodge":
        details_parts.append("采取闪避姿态，专注于躲避攻击")
    elif action_type == "dash":
        details_parts.append("使用冲刺，加速穿越战场")
    elif action_type == "disengage":
        details_parts.append("巧妙脱离接战，安全撤退")
    elif action_type == "help":
        details_parts.append(f"协助 {target_name}")
    elif action_type == "grapple":
        details_parts.append(f"尝试擒抱 {target_name}，{'成功' if hit else '失败'}")
    elif action_type == "shove":
        details_parts.append(f"尝试推撞 {target_name}，{'成功' if hit else '失败'}")
    elif action_type == "smite":
        details_parts.append(f"神圣斩击！额外造成 {damage} 点辐光伤害")
    elif action_type == "reaction":
        details_parts.append(extra_details or "使用反应动作")
    elif action_type == "class_feature":
        details_parts.append(extra_details or "使用职业特性")

    if extra_details and action_type == "attack":
        details_parts.append(extra_details)

    details = "\n".join(details_parts)

    prompt = NARRATE_TEMPLATE.format(
        actor_name=actor_name,
        actor_class=actor_class or "冒险者",
        target_name=target_name or "敌人",
        action_type=action_type,
        details=details,
    )

    try:
        import asyncio
        llm = get_llm(temperature=0.9, max_tokens=200)
        resp = await asyncio.wait_for(
            llm.ainvoke([
                SystemMessage(content=NARRATOR_SYSTEM),
                HumanMessage(content=prompt),
            ]),
            timeout=8.0,  # 8秒超时，避免拖慢游戏
        )
        narrative = resp.content.strip()
        if narrative and len(narrative) > 5:
            return narrative
    except asyncio.TimeoutError:
        logger.warning("Combat narration timed out (8s)")
    except Exception as e:
        logger.warning(f"Combat narration failed: {e}")

    # Fallback: 返回空字符串，让调用方使��原有机械描述
    return ""


async def narrate_batch(actions: list[dict]) -> list[str]:
    """批量叙述多个AI行动（一次LLM调用）。

    actions: [{"actor_name", "target_name", "action_type", "mechanical_desc"}, ...]
    返回与 actions 等长的叙事列表。
    """
    if not actions:
        return []

    action_lines = []
    for i, a in enumerate(actions, 1):
        action_lines.append(
            f"{i}. {a.get('actor_name','?')}（{a.get('actor_class','冒险者')}）"
            f"对 {a.get('target_name','?')} {a.get('mechanical_desc','行动')}"
        )

    prompt = BATCH_TEMPLATE.format(actions="\n".join(action_lines))

    try:
        import asyncio, re
        llm = get_llm(temperature=0.9, max_tokens=150 * len(actions))
        resp = await asyncio.wait_for(
            llm.ainvoke([
                SystemMessage(content=NARRATOR_SYSTEM),
                HumanMessage(content=prompt),
            ]),
            timeout=10.0,
        )
        text = resp.content.strip()
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if line and len(line) > 3:
                cleaned = re.sub(r'^\d+[\.\、\：\:]\s*', '', line)
                if cleaned:
                    lines.append(cleaned)

        while len(lines) < len(actions):
            lines.append("")
        return lines[:len(actions)]

    except asyncio.TimeoutError:
        logger.warning("Batch combat narration timed out (10s)")
        return [""] * len(actions)
    except Exception as e:
        logger.warning(f"Batch combat narration failed: {e}")
        return [""] * len(actions)
