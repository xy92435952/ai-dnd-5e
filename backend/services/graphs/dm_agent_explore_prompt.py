"""Exploration-mode system prompt for the DM agent."""

from services.graphs.dm_agent_explore_companion_prompt import EXPLORE_COMPANION_SECTION
from services.graphs.dm_agent_explore_core_prompt import EXPLORE_CORE_SECTION
from services.graphs.dm_agent_explore_mechanics_prompt import EXPLORE_MECHANICS_SECTION
from services.graphs.dm_agent_explore_output_prompt import EXPLORE_OUTPUT_SECTION
from services.graphs.dm_agent_safety import SAFETY_BLOCK

EXPLORE_SYSTEM = (
    "你是一个精通DnD 5e规则的地下城主，当前处于探索/叙事模式。\n"
    + SAFETY_BLOCK
    + EXPLORE_CORE_SECTION
    + EXPLORE_COMPANION_SECTION
    + EXPLORE_MECHANICS_SECTION
    + EXPLORE_OUTPUT_SECTION
)
