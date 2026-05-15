import logging


logger = logging.getLogger(__name__)


OPENING_PROMPT = """你是一位经验丰富的 DnD 5e 地下城主，现在要为一场新冒险生成开场白。

## 你拥有的信息
- 模组名称：{module_name}
- 世界观/背景设定：{setting}
- 基调：{tone}
- 第一个场景的描述：{first_scene_desc}

## 开场白要求
1. **绝对不能剧透**——不要透露主线剧情走向、Boss身份、关键NPC的秘密、任何悬念的答案
2. **营造悬念**——用感官细节（异常的气味、远处的声响、不自然的沉寂）暗示"有什么不对劲"
3. **建立氛围**——让玩家感受到冒险的世界观基调（阴森/奇幻/史诗/诡异）
4. **引导行动**——结尾自然地让玩家产生"我想往前探索"的冲动，但不要直接列出选项
5. **第二人称叙述**——"你踏入..."、"你注意到..."
6. **200-300字**，中文，沉浸式文学风格
7. 不要使用 Markdown 格式，纯文本即可

直接输出开场白文本，不要有任何前缀、解释或标签。"""


async def generate_opening(parsed: dict, raw_scene: str) -> str:
    """Generate a spoiler-safe opening scene. Fall back to the raw scene on LLM failure."""
    try:
        from services.llm import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_llm(temperature=0.85, max_tokens=600)
        prompt = OPENING_PROMPT.format(
            module_name=parsed.get("name", "未知模组"),
            setting=parsed.get("setting", "一个神秘的奇幻世界"),
            tone=parsed.get("tone", "冒险"),
            first_scene_desc=raw_scene or "冒险的起点",
        )
        resp = await llm.ainvoke([
            SystemMessage(content="你是一位经验丰富的 DnD 5e 地下城主，擅长用沉浸式的文学语言描述场景。"),
            HumanMessage(content=prompt),
        ])
        text = resp.content.strip()
        if len(text) > 30:
            return text
    except Exception as exc:
        logger.warning("开场白生成失败，使用原始场景描述: %s", exc)

    return raw_scene or f"你站在{parsed.get('setting', '一个神秘的地方')}的入口处。冒险即将开始。"
