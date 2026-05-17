import logging

logger = logging.getLogger(__name__)


def build_module_context(*, module, session) -> dict:
    parsed = module.parsed_content or {}
    return {
        "module_name": module.name,
        "setting": parsed.get("setting", ""),
        "tone": parsed.get("tone", "标准冒险"),
        "plot_summary": parsed.get("plot_summary", ""),
        "current_scene": session.current_scene or "",
        "npcs": parsed.get("npcs", []),
        "monsters": parsed.get("monsters", []),
        "magic_items": parsed.get("magic_items", []),
    }


def build_campaign_memory(session) -> str:
    campaign_state = getattr(session, "campaign_state", None)
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


async def build_retrieved_context(
    *,
    rag_service,
    module,
    session,
    player_action: str,
) -> str:
    if not player_action:
        return ""
    try:
        return await rag_service.retrieve(
            query=player_action,
            module_id=module.id,
            session_id=session.id,
        )
    except Exception as e:
        logger.warning(f"RAG 检索异常（已忽略）: {e}")
        return ""
