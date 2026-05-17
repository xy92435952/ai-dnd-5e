"""
ContextBuilder — 将数据库状态序列化为 DM Agent 输入。

旧调用入口保留在这里；具体状态快照、多人上下文、模组/记忆/RAG 拼装
拆到相邻模块，方便之后单人 DM 与多人 DM 继续分层演进。
"""

import json
from typing import Optional

from models.character import Character
from models.module import Module
from models.session import CombatState, Session
from services.context_builder_memory import (
    build_campaign_memory as _build_campaign_memory_text,
    build_module_context as _build_module_context_payload,
    build_retrieved_context as _build_retrieved_context_text,
)
from services.context_builder_multiplayer import build_multiplayer_context as _build_multiplayer_context_payload
from services.context_builder_snapshots import (
    CHAR_FIELDS as _CHAR_FIELDS,
    ENEMY_FIELDS as _ENEMY_FIELDS,
    build_game_state_json as _build_game_state_json,
    build_game_state_payload as _build_game_state_payload,
)
from services.rag_service import BaseRagService, get_rag_service


class ContextBuilder:
    """
    构建 LangGraph DM Agent 所需输入字段：
    - game_state: 当前局面快照
    - module_context: 模组静态上下文
    - campaign_memory: checkpoint 生成的长期记忆摘要
    - retrieved_context: RAG 检索片段
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
        self.rag_service: BaseRagService = rag_service or get_rag_service()

    async def build(self, player_action: str, current_actor_id: Optional[str] = None) -> dict:
        game_state = self._build_game_state(current_actor_id)
        module_context = self._build_module_context()
        campaign_memory = self._build_campaign_memory()
        retrieved_context = await self._build_retrieved_context(player_action)

        return {
            "player_action": player_action,
            "game_state": game_state,
            "module_context": module_context,
            "campaign_memory": campaign_memory,
            "retrieved_context": retrieved_context,
        }

    def _build_game_state(self, current_actor_id: Optional[str] = None) -> str:
        return _build_game_state_json(
            session=self.session,
            characters=self.characters,
            combat_state=self.combat_state,
            current_actor_id=current_actor_id,
        )

    def _build_multiplayer_context(self, current_actor_id: Optional[str] = None) -> dict:
        return _build_multiplayer_context_payload(
            session=self.session,
            characters=self.characters,
            current_actor_id=current_actor_id,
        )

    def _build_module_context(self) -> str:
        return json.dumps(
            _build_module_context_payload(module=self.module, session=self.session),
            ensure_ascii=False,
        )

    def _build_campaign_memory(self) -> str:
        return _build_campaign_memory_text(self.session)

    async def _build_retrieved_context(self, player_action: str) -> str:
        return await _build_retrieved_context_text(
            rag_service=self.rag_service,
            module=self.module,
            session=self.session,
            player_action=player_action,
        )
