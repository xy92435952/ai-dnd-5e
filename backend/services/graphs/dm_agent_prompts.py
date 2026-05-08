"""Compatibility exports for DM agent prompt constants."""

from services.graphs.dm_agent_combat_prompt import COMBAT_SYSTEM
from services.graphs.dm_agent_explore_prompt import EXPLORE_SYSTEM
from services.graphs.dm_campaign_prompt import CAMPAIGN_STATE_PROMPT

__all__ = ["COMBAT_SYSTEM", "EXPLORE_SYSTEM", "CAMPAIGN_STATE_PROMPT"]
