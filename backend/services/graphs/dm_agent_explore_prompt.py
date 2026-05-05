"""Exploration-mode system prompt for the DM agent."""

from services.graphs.dm_agent_explore_companion_prompt import EXPLORE_COMPANION_SECTION
from services.graphs.dm_agent_explore_core_prompt import EXPLORE_CORE_SECTION
from services.graphs.dm_agent_explore_mechanics_prompt import EXPLORE_MECHANICS_SECTION
from services.graphs.dm_agent_explore_output_prompt import EXPLORE_OUTPUT_SECTION
from services.graphs.dm_agent_safety import SAFETY_BLOCK

EXPLORE_COMPANION_HANDOFF_SECTION = """

## FINAL OVERRIDE FOR COMPANION OUTPUT
- This step owns the main DM narration, rules, checks, state changes, and player choices only.
- Return `companion_reactions` as an empty string.
- Do not draft companion lines here, even in important scenes.
- Instead return a short `companion_brief` object with this shape:
  {
    "enabled": true|false,
    "scene_type": "quiet|tense|reveal|danger|aftermath",
    "emotion": "curious|uneasy|warm|grim|relieved",
    "focus": "one-sentence summary of what companions should react to",
    "speaker_limit": 0-2,
    "max_words": 0-120
  }
- If no companion beat is needed, set `enabled` to false and keep `companion_reactions` empty.
"""

EXPLORE_SYSTEM = (
    "你是一个精通DnD 5e规则的地下城主，当前处于探索/叙事模式。\n"
    + SAFETY_BLOCK
    + EXPLORE_CORE_SECTION
    + EXPLORE_COMPANION_SECTION
    + EXPLORE_MECHANICS_SECTION
    + EXPLORE_OUTPUT_SECTION
    + EXPLORE_COMPANION_HANDOFF_SECTION
)
