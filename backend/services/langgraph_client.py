"""
LangGraphClient — Drop-in replacement for DifyClient.
所有方法签名和返回格式与 DifyClient 完全一致。
"""

import json
from typing import Optional

from services.graphs.module_parser import run_module_parser
from services.graphs.party_generator import run_party_generator
from services.graphs.dm_agent import run_dm_agent, run_campaign_state_generator


class LangGraphClient:

    async def parse_module(self, module_text: str) -> tuple[dict, list]:
        return await run_module_parser(module_text)

    async def generate_party(
        self,
        player_class: str,
        player_race: str,
        player_level: int,
        party_size: int,
        module_data: dict,
    ) -> list[dict]:
        return await run_party_generator(
            player_class=player_class,
            player_race=player_race,
            player_level=player_level,
            party_size=party_size,
            module_data=module_data,
        )

    async def call_dm_agent(
        self,
        player_action: str,
        game_state: str,
        module_context: str,
        campaign_memory: str = "",
        retrieved_context: str = "",
        conversation_id: Optional[str] = None,
    ) -> dict:
        return await run_dm_agent(
            player_action=player_action,
            game_state=game_state,
            module_context=module_context,
            campaign_memory=campaign_memory,
            retrieved_context=retrieved_context,
            session_id=conversation_id,
        )

    async def generate_campaign_state(
        self,
        log_text: str,
        module_summary: str,
        existing_state: dict,
    ) -> dict:
        return await run_campaign_state_generator(
            log_text=log_text,
            module_summary=module_summary,
            existing_state=existing_state,
        )

    async def generate_takeover_action(
        self,
        character: dict,
        scene: str,
        recent_logs: list[str],
    ) -> str:
        """
        替断线玩家生成一段贴合角色人设的简短行动。

        输入：
          character    {name, char_class, level, personality, speech_style,
                        combat_preference, catchphrase, backstory}
          scene        当前场景描述（session.current_scene）
          recent_logs  最近 6-10 条 GameLog content（用于上下文）

        输出：1-2 句中文行动描述（第一人称）。失败时 fallback 用 catchphrase 或通用台词。
        """
        from services.llm import get_llm

        prompt = f"""你正在替一个**断线的玩家**临时代演他的角色。请按照这个角色的人设
生成一段**简短行动**（1-2 句，第一人称），既符合性格又能推进游戏节奏。

**角色信息：**
- 姓名：{character.get('name', '冒险者')}
- 职业：{character.get('char_class', '?')} Lv{character.get('level', 1)}
- 性格：{character.get('personality') or '（未填）'}
- 说话风格：{character.get('speech_style') or '（未填）'}
- 战斗偏好：{character.get('combat_preference') or '（未填）'}
- 口头禅：{character.get('catchphrase') or '（无）'}
- 背景：{(character.get('backstory') or '')[:300]}

**当前场景：**
{(scene or '')[:400]}

**最近发生：**
{chr(10).join(f'- {l[:200]}' for l in (recent_logs or [])[-8:])}

**输出要求：**
1. 第一人称，1-2 句话
2. 风格务必贴合 personality + speech_style（寡言→短句；健谈→可稍长）
3. 不要用元话语（"我代演"/"我作为AI"），直接以角色身份说话/行动
4. 不要选明显高风险的行为（推门、攻击重要 NPC 等）—— 偏保守/跟随

直接输出行动文本，不要前缀、引号或解释。"""

        try:
            llm = get_llm(temperature=0.85, max_tokens=200)
            resp = await llm.ainvoke(prompt)
            text = (resp.content or "").strip().strip('"\'')
            if not text:
                raise ValueError("LLM 返回空")
            return text
        except Exception:
            # 失败兜底：用 catchphrase 或通用台词
            cp = character.get('catchphrase')
            return f"{cp}（{character.get('name','他')}沉默地跟在队伍后面）" if cp else \
                   f"{character.get('name','他')}沉默地观察四周，等待时机。"


langgraph_client = LangGraphClient()
