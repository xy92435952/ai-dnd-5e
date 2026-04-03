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


langgraph_client = LangGraphClient()
