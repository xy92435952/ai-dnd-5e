import re
import httpx
import json
from typing import Optional
from config import settings


# ── Campaign State 提示词 ─────────────────────────────────────────────────────
_CAMPAIGN_STATE_PROMPT = """
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
      "outcome": "结果描述，仅completed/failed时填写，active时为空字符串"
    }
  ],
  "world_flags": {
    "简短事件标签": true
  },
  "notable_items": ["玩家获得或失去的重要物品，最多6条"],
  "party_changes": ["队伍状态的重要变化，如等级提升、成员变动等，最多4条"]
}
"""


def _merge_campaign_states(existing: dict, new: dict) -> dict:
    """
    将新生成的战役状态叠加到已有状态上（增量合并，不覆盖已有内容）。
    - 列表字段：追加不重复的新条目
    - 字典字段：深层 update
    - quest_log：以任务名为主键 upsert
    """
    merged = dict(existing) if existing else {}

    # 列表追加去重
    for key in ("completed_scenes", "key_decisions", "notable_items", "party_changes"):
        old_list = merged.get(key, [])
        new_list = new.get(key, [])
        merged[key] = old_list + [x for x in new_list if x not in old_list]

    # dict 深层合并
    for key in ("npc_registry", "world_flags"):
        old_dict = dict(merged.get(key, {}))
        new_dict = new.get(key, {})
        old_dict.update(new_dict)
        merged[key] = old_dict

    # quest_log：以 quest 名称为主键 upsert
    quest_map = {q["quest"]: q for q in merged.get("quest_log", [])}
    for q in new.get("quest_log", []):
        quest_map[q["quest"]] = q
    merged["quest_log"] = list(quest_map.values())

    return merged


class DifyClient:
    """封装 Dify Workflow API 调用"""

    def __init__(self):
        self.base_url = settings.dify_base_url.rstrip("/")
        self.timeout = 120.0  # AI响应可能较慢

    async def _run_workflow(self, api_key: str, inputs: dict) -> dict:
        """调用 Dify Workflow（blocking 模式）"""
        url = f"{self.base_url}/workflows/run"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": inputs,
            "response_mode": "blocking",
            "user": "ai-trpg-player",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Dify blocking 响应结构: data.outputs
        if data.get("data", {}).get("status") == "failed":
            error = data["data"].get("error", "Dify workflow failed")
            raise RuntimeError(f"Dify workflow error: {error}")

        return data.get("data", {}).get("outputs", {})

    async def _send_chatflow_message(
        self,
        api_key: str,
        query: str,
        inputs: dict,
        conversation_id: Optional[str] = None,
    ) -> dict:
        """
        调用 Dify Chatflow API（/chat-messages，blocking 模式）。
        conversation_id 为空字符串时 Dify 会创建新对话并返回新 ID。
        """
        url = f"{self.base_url}/chat-messages"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": query,
            "inputs": inputs,
            "response_mode": "blocking",
            "user": "ai-trpg-player",
            "conversation_id": conversation_id or "",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def parse_module(self, module_text: str) -> tuple[dict, list]:
        """
        WF1: 解析模组文本。
        返回 (module_data_dict, rag_chunks_list)。
        rag_chunks 是 WF1 v0.4 新增输出，旧版 WF1 不含此字段时返回空列表。
        """
        outputs = await self._run_workflow(
            api_key=settings.dify_module_parser_key,
            inputs={"module_text": module_text},
        )
        # module_data
        raw_module = outputs.get("module_data", "{}")
        try:
            module_data = json.loads(raw_module)
        except json.JSONDecodeError:
            module_data = {}

        # rag_chunks（WF1 v0.4 新增）
        raw_chunks = outputs.get("rag_chunks", "[]")
        try:
            rag_chunks = json.loads(raw_chunks)
            if not isinstance(rag_chunks, list):
                rag_chunks = []
        except json.JSONDecodeError:
            rag_chunks = []

        return module_data, rag_chunks

    async def generate_party(
        self,
        player_class: str,
        player_race: str,
        player_level: int,
        party_size: int,
        module_data: dict,
    ) -> list[dict]:
        """WF2: 生成AI队友"""
        outputs = await self._run_workflow(
            api_key=settings.dify_party_generator_key,
            inputs={
                "player_class": player_class,
                "player_race": player_race,
                "player_level": str(player_level),
                "party_size": str(party_size),
                "module_data": json.dumps(module_data, ensure_ascii=False),
            },
        )
        raw = outputs.get("companions", "[]")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []

    async def generate_campaign_state(
        self,
        log_text:       str,
        module_summary: str,
        existing_state: dict,
    ) -> dict:
        """
        将冒险日志压缩为结构化战役档案 JSON。
        使用 DM Agent Chatflow（新对话，不影响游戏会话），不再依赖 WF3 旧版 Key。
        """
        prompt = (
            f"{_CAMPAIGN_STATE_PROMPT}\n\n"
            f"## 模组背景\n{module_summary}\n\n"
            f"## 冒险记录\n{log_text}"
        )
        try:
            data = await self._send_chatflow_message(
                api_key         = settings.dify_dm_agent_key,
                query           = prompt,
                inputs          = {
                    "game_state":        "{}",
                    "module_context":    module_summary,
                    "campaign_memory":   json.dumps(existing_state, ensure_ascii=False),
                    "retrieved_context": "",
                },
                conversation_id = None,   # 新对话，不持久化，不影响游戏会话
            )
            raw = data.get("answer", "")
            raw = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
            new_state = json.loads(raw)
            return _merge_campaign_states(existing_state, new_state)
        except Exception:
            return existing_state   # AI 输出不合法时保留旧档案

    async def call_dm_agent(
        self,
        player_action:    str,
        game_state:       str,
        module_context:   str,
        campaign_memory:  str = "",
        retrieved_context: str = "",
        conversation_id:  Optional[str] = None,
    ) -> dict:
        """
        DM 全能代理（Chatflow 版）。
        通过 conversation_id 实现跨轮次原生对话记忆，无需后端手动传入 session_history。
        返回格式与旧版兼容，额外包含 _conversation_id 供调用方存储。
        """
        data = await self._send_chatflow_message(
            api_key         = settings.dify_dm_agent_key,
            query           = player_action,
            inputs          = {
                "game_state":         game_state,
                "module_context":     module_context,
                "campaign_memory":    campaign_memory,
                "retrieved_context":  retrieved_context,   # RAG 检索结果注入
            },
            conversation_id = conversation_id,
        )

        answer_text       = data.get("answer", "")
        new_conv_id       = data.get("conversation_id", "")

        # 去掉 AI 可能输出的 Markdown 代码块包裹
        clean = re.sub(r"```(?:json)?\s*|\s*```", "", answer_text).strip()

        try:
            result = json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            # AI 输出不合法时，把原文作为叙事
            result = {
                "action_type":        "exploration",
                "narrative":          answer_text or "（DM响应解析失败）",
                "companion_reactions":"",
                "needs_check":        {"required": False},
                "state_delta":        {},
                "player_choices":     [],
            }

        def to_bool(v):
            return str(v).lower() == "true" if isinstance(v, str) else bool(v)

        state_delta = result.get("state_delta", {})
        needs_check = result.get("needs_check", {"required": False})
        if isinstance(needs_check, str):
            try:
                needs_check = json.loads(needs_check)
            except (json.JSONDecodeError, ValueError):
                needs_check = {"required": False}

        # 重新包装为与 StateApplicator 兼容的格式
        # result 字段内嵌完整数据，StateApplicator 从中读取
        wrapped_result = {
            "action_type":        result.get("action_type", "exploration"),
            "narrative":          result.get("narrative", ""),
            "companion_reactions":result.get("companion_reactions", ""),
            "needs_check":        needs_check,
            "player_choices":     result.get("player_choices", []),
            "state_delta":        state_delta,
            "dice_results":       result.get("dice_results", []),
            "ai_turns":           result.get("ai_turns", []),
        }

        return {
            "result":              json.dumps(wrapped_result, ensure_ascii=False),
            "action_type":         wrapped_result["action_type"],
            "narrative":           wrapped_result["narrative"],
            "state_delta":         json.dumps(state_delta, ensure_ascii=False),
            "companion_reactions": wrapped_result["companion_reactions"],
            "dice_display":        wrapped_result["dice_results"],
            "needs_check":         needs_check,
            "combat_trigger":      to_bool(state_delta.get("combat_trigger", False)),
            "combat_end":          to_bool(state_delta.get("combat_end", False)),
            "success":             True,
            "error":               "",
            "_conversation_id":    new_conv_id,
        }


dify_client = DifyClient()
