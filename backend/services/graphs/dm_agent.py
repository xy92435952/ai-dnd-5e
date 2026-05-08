"""
WF3 — DM Agent LangGraph 图
四层链路：input_layer → pre_roll_dice → rules_layer → memory_layer
        → [combat_dm | explore_dm] → parse_validate
支持 SQLite（本地开发）和 PostgreSQL（生产环境）持久化对话记忆
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from services.graphs.dm_agent_nodes import (
    combat_dm,
    explore_dm,
    input_layer,
    memory_layer,
    parse_validate,
    pre_roll_dice,
    refuse_and_end,
    route_after_guard,
    route_by_mode,
    rules_layer,
)
from services.graphs.dm_agent_memory import get_memory_saver, initialize_memory
from services.graphs.dm_agent_runtime import (
    build_initial_state,
    wrap_final_state,
)
from services.graphs.dm_agent_state import DMAgentState, add_messages
from services.graphs.dm_agent_utils import (
    build_input_meta,
    build_memory_context,
    build_rules_context,
)
from services.graphs.dm_campaign_state import _merge_campaign_states, run_campaign_state_generator


# Backward-compatible aliases for older unit tests / internal imports.
_add_messages = add_messages
_build_rules_context = build_rules_context
_build_memory_context = build_memory_context
_build_input_meta = build_input_meta


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Build graph
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def build_dm_agent_graph():
    checkpointer = await get_memory_saver()

    g = StateGraph(DMAgentState)
    g.add_node("input_layer", input_layer)
    g.add_node("refuse_and_end", refuse_and_end)
    g.add_node("rules_layer", rules_layer)
    g.add_node("pre_roll_dice", pre_roll_dice)
    g.add_node("combat_dm", combat_dm)
    g.add_node("explore_dm", explore_dm)
    g.add_node("memory_layer", memory_layer)
    g.add_node("parse_validate", parse_validate)

    g.set_entry_point("input_layer")
    g.add_conditional_edges("input_layer", route_after_guard, {
        "proceed": "pre_roll_dice",
        "refuse": "refuse_and_end",
    })
    g.add_edge("refuse_and_end", END)
    g.add_edge("pre_roll_dice", "rules_layer")
    g.add_edge("rules_layer", "memory_layer")
    g.add_conditional_edges("memory_layer", route_by_mode, {
        "combat_dm": "combat_dm",
        "explore_dm": "explore_dm",
    })
    g.add_edge("combat_dm", "parse_validate")
    g.add_edge("explore_dm", "parse_validate")
    g.add_edge("parse_validate", END)

    return g.compile(checkpointer=checkpointer)


async def run_dm_agent(
    player_action: str,
    game_state: str,
    module_context: str,
    campaign_memory: str = "",
    retrieved_context: str = "",
    action_source: str = "human_input",
    session_id: str | None = None,
) -> dict:
    """
    Run the DM Agent graph.
    Returns dict compatible with DifyClient.call_dm_agent() output format.
    """
    graph = await build_dm_agent_graph()

    initial_state = build_initial_state(
        player_action=player_action,
        game_state=game_state,
        module_context=module_context,
        campaign_memory=campaign_memory,
        retrieved_context=retrieved_context,
        action_source=action_source,
    )
    config = {"configurable": {"thread_id": session_id or "default"}}
    final_state = await graph.ainvoke(initial_state, config=config)
    return wrap_final_state(final_state, session_id=session_id)
