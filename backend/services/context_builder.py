"""
ContextBuilder — 将数据库状态序列化为 DM Agent（Chatflow版）的输入
=================================================================
职责：
  - 将 Session / Character / CombatState / Module 等 ORM 对象
    打包成 Chatflow 所需的三个字段：
      game_state       完整游戏状态快照（JSON字符串）
      module_context   模组背景摘要（JSON字符串）
      campaign_memory  战役长期记忆——仅来自 checkpoint 存档（文本）

  注意：近期对话历史（session_history）不再由后端传入，
  Dify Chatflow 通过 conversation_id 原生维护对话记忆。

RAG 扩展点：
  构造时传入 rag_service（可选）。
  当前默认使用 RagService()（存根，返回空）。
  长团启用时传入 DifyRagService()，其余代码无需改动。
"""

import json
import logging
from typing import Optional

from models.character import Character
from models.session import Session, CombatState, GameLog
from models.module import Module
from schemas.game_schemas import GameState, EnemyState
from services.rag_service import BaseRagService, get_rag_service

logger = logging.getLogger(__name__)

# 注入 game_state 时，敌人 stat block 最多保留的字段
_ENEMY_FIELDS = [
    "id", "name", "hp_current", "hp_max", "ac", "conditions",
    "actions", "ability_scores", "speed", "resistances", "immunities",
    "special_abilities", "tactics", "dead",
]

# 角色状态快照保留字段
_CHAR_FIELDS = [
    "id", "name", "race", "char_class", "level",
    "hp_current", "hp_max", "ac", "initiative",
    "proficiency_bonus", "attack_bonus", "spell_save_dc",
    "ability_modifiers", "spell_slots", "conditions",
    "death_saves", "concentration", "known_spells",
    "cantrips", "equipped", "active_effects",
    "proficient_skills", "proficient_saves",
    # 角色叙事字段：DM 在生成对话/反应时据此代演（含玩家被托管时）
    "is_player", "personality", "backstory",
    "speech_style", "combat_preference", "catchphrase",
]


class ContextBuilder:
    """
    使用示例（api/game.py 中）：

        builder = ContextBuilder(
            session=session,
            module=module,
            characters=characters,
            combat_state=combat_state,  # 战斗中传入，否则 None
            # rag_service=DifyRagService(),  # 长团启用时取消注释
        )
        inputs = await builder.build(player_action=player_action)
        result = await dify_client.call_dm_agent(**inputs)
    """

    def __init__(
        self,
        session: Session,
        module: Module,
        characters: list[Character],
        combat_state: Optional[CombatState] = None,
        rag_service: Optional[BaseRagService] = None,
    ):
        self.session = session
        self.module = module
        self.characters = characters
        self.combat_state = combat_state
        # RAG 可插拔：自动根据 config 选择实现（已配置 KB → DifyRagService，否则存根）
        self.rag_service: BaseRagService = rag_service or get_rag_service()

    # ─────────────────────────────────────────────
    # 主入口：构建 WF3 所需全部输入字段
    # ─────────────────────────────────────────────

    async def build(self, player_action: str, current_actor_id: Optional[str] = None) -> dict:
        """
        返回可直接传入 DifyClient.call_dm_agent() 的字典。
        session_history 已移除——Chatflow 通过 conversation_id 原生维护对话记忆。
        campaign_memory 仅包含 checkpoint 存档中的结构化长期记忆。

        Args:
            player_action: 玩家行动文本
            current_actor_id: 当前发起行动的角色 id
                - 单人模式：session.player_character_id
                - 多人模式：SessionMember 查到的 character_id
                game_state 里会标注这个字段，DM 会据此聚焦叙事视角，避免
                分头行动时把不在场的队友硬塞进叙事
        """
        game_state      = self._build_game_state(current_actor_id)
        module_context  = self._build_module_context()
        campaign_memory = self._build_campaign_memory()

        # RAG 检索（存根时为空字符串，对现有功能无影响）
        retrieved_context = await self._build_retrieved_context(player_action)

        return {
            "player_action":    player_action,
            "game_state":       game_state,
            "module_context":   module_context,
            "campaign_memory":  campaign_memory,
            "retrieved_context": retrieved_context,
        }

    # ─────────────────────────────────────────────
    # game_state：完整的游戏状态快照
    # ─────────────────────────────────────────────

    def _build_game_state(self, current_actor_id: Optional[str] = None) -> str:
        gs = GameState.model_validate(
            self.session.game_state or {}
        )

        # 查当前行动者的名字（供 prompt 使用）
        actor_name = None
        if current_actor_id:
            for ch in self.characters:
                if ch.id == current_actor_id:
                    actor_name = ch.name
                    break

        state = {
            "session_id":    self.session.id,
            "combat_active": self.session.combat_active,
            "current_scene": self.session.current_scene or "",
            "round_number":  0,
            "characters":    [],
            "enemies":       [],
            "turn_order":    [],
            "current_turn":  None,
            # 当前发起行动的角色：DM 应按这个角色的视角聚焦叙事
            # 分头行动场景里，其他角色不应该凭空出现在叙事里
            "current_actor_id":   current_actor_id,
            "current_actor_name": actor_name,
        }

        # 角色快照
        for char in self.characters:
            derived = char.derived or {}
            snapshot = {
                "id":               char.id,
                "name":             char.name,
                "race":             char.race,
                "char_class":       char.char_class,
                "level":            char.level,
                "hp_current":       char.hp_current,
                "hp_max":           derived.get("hp_max", char.hp_current),
                "ac":               derived.get("ac", 10),
                "initiative":       derived.get("initiative", 0),
                "proficiency_bonus":derived.get("proficiency_bonus", 2),
                "attack_bonus":     derived.get("attack_bonus", 2),
                "spell_save_dc":    derived.get("spell_save_dc", 10),
                "ability_modifiers":derived.get("ability_modifiers", {}),
                "spell_slots":      char.spell_slots or {},
                "conditions":       char.conditions or [],
                "death_saves":      char.death_saves or {"successes":0,"failures":0,"stable":False},
                "concentration":    char.concentration,
                "known_spells":     char.known_spells or [],
                "cantrips":         char.cantrips or [],
                "proficient_skills":char.proficient_skills or [],
                "proficient_saves": char.proficient_saves or [],
                "is_player":        char.is_player,
                # 叙事字段（DM 据此代演角色：玩家被托管时也能贴合人设）
                "personality":       char.personality or "",
                "backstory":         char.backstory or "",
                "speech_style":      char.speech_style or "",
                "combat_preference": char.combat_preference or "",
                "catchphrase":       char.catchphrase or "",
                "gold":             (getattr(char, "equipment", {}) or {}).get("gold", 0),
                # 装备和主动效果（后续扩展字段，暂为空）
                "equipped":         getattr(char, "equipment", {}) or {},
                "active_effects":   getattr(char, "active_effects", {}) or {},
            }
            state["characters"].append(snapshot)

        # 战斗状态
        if self.session.combat_active and self.combat_state:
            state["round_number"] = self.combat_state.round_number
            state["turn_order"]   = self.combat_state.turn_order or []
            state["current_turn"] = (
                self.combat_state.turn_order[self.combat_state.current_turn_index]["character_id"]
                if self.combat_state.turn_order else None
            )

            # 敌人快照：只保留 AI 裁定所需字段
            game_state_data = GameState.model_validate(self.session.game_state or {})
            for enemy in game_state_data.enemies:
                enemy_dict = enemy.model_dump()
                filtered = {k: enemy_dict[k] for k in _ENEMY_FIELDS if k in enemy_dict}
                state["enemies"].append(filtered)

            # 战场位置（供 AI 判断近战/远程范围）
            state["entity_positions"] = self.combat_state.entity_positions or {}

        return json.dumps(state, ensure_ascii=False)

    # ─────────────────────────────────────────────
    # module_context：模组背景摘要（静态，每次相同）
    # ─────────────────────────────────────────────

    def _build_module_context(self) -> str:
        parsed = self.module.parsed_content or {}
        context = {
            "module_name":   self.module.name,
            "setting":       parsed.get("setting", ""),
            "tone":          parsed.get("tone", "标准冒险"),
            "plot_summary":  parsed.get("plot_summary", ""),
            "current_scene": self.session.current_scene or "",
            # 当前场景相关的 NPC（全量，RAG 实现后可改为按场景过滤）
            "npcs":          parsed.get("npcs", []),
            # 怪物信息（战斗中 AI 用来查攻击列表和战术）
            "monsters":      parsed.get("monsters", []),
            "magic_items":   parsed.get("magic_items", []),
        }
        return json.dumps(context, ensure_ascii=False)

    # ─────────────────────────────────────────────
    # campaign_memory：战役长期记忆（来自 checkpoint 存档）
    # 近期对话历史由 Dify Chatflow 原生维护，不在此处理
    # ─────────────────────────────────────────────

    def _build_campaign_memory(self) -> str:
        campaign_state = getattr(self.session, "campaign_state", None)
        if not campaign_state:
            return ""

        cs = campaign_state if isinstance(campaign_state, dict) else {}
        parts = []

        if cs.get("completed_scenes"):
            parts.append(f"已完成场景：{', '.join(cs['completed_scenes'])}")
        if cs.get("key_decisions"):
            parts.append("关键决定：" + "; ".join(cs["key_decisions"][:6]))
        if cs.get("quest_log"):
            active = [q for q in cs["quest_log"] if q.get("status") == "active"]
            if active:
                parts.append("进行中任务：" + "; ".join(q["quest"] for q in active))
        if cs.get("npc_registry"):
            npc_notes = []
            for name, info in list(cs["npc_registry"].items())[:5]:
                npc_notes.append(f"{name}（{info.get('relationship','未知')}）")
            parts.append("已知NPC：" + ", ".join(npc_notes))
        if cs.get("world_flags"):
            flags = [k for k, v in cs["world_flags"].items() if v][:6]
            if flags:
                parts.append("世界事件：" + ", ".join(flags))

        return "\n".join(parts) if parts else ""

    # ─────────────────────────────────────────────
    # retrieved_context：RAG 检索内容（扩展点）
    # ─────────────────────────────────────────────

    async def _build_retrieved_context(self, player_action: str) -> str:
        """
        当前：RagService 存根，返回空字符串。
        启用 RAG 后：自动检索模组原文片段 + 相关历史事件。
        调用方无需任何改动。
        """
        if not player_action:
            return ""
        try:
            return await self.rag_service.retrieve(
                query=player_action,
                module_id=self.module.id,
                session_id=self.session.id,
            )
        except Exception as e:
            logger.warning(f"RAG 检索异常（已忽略）: {e}")
            return ""
