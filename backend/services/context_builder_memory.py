import logging

from config import settings

logger = logging.getLogger(__name__)


def _shorten(value, max_chars: int):
    if value is None:
        return value
    text = str(value)
    return text if len(text) <= max_chars else text[:max_chars].rstrip() + "..."


def _find_current_scene(scenes: list, current_scene: str, description_chars: int = 1800) -> dict:
    if not isinstance(scenes, list) or not current_scene:
        return {}
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        title = str(scene.get("title") or scene.get("name") or "")
        if title and (title == current_scene or title in current_scene or current_scene in title):
            return {
                "title": title,
                "description": _shorten(scene.get("description", ""), description_chars),
            }
    return {}


def _slim_entities(items: list, limit: int, fields: tuple[str, ...]) -> list:
    slimmed = []
    for item in (items or [])[:limit]:
        if not isinstance(item, dict):
            continue
        slimmed.append({
            field: _shorten(item.get(field, ""), 160)
            for field in fields
            if item.get(field) not in (None, "", [])
        })
    return slimmed


def _trim_entity_fields(items: list, limit: int, max_chars: int) -> list:
    trimmed = []
    for item in (items or [])[:limit]:
        if not isinstance(item, dict):
            continue
        trimmed.append({
            key: _shorten(value, max_chars)
            for key, value in item.items()
            if value not in (None, "", [])
        })
    return trimmed


def _with_omitted(payload: dict, reason: str) -> dict:
    omitted = list(payload.get("module_context_omitted") or [])
    if reason not in omitted:
        omitted.append(reason)
    return {**payload, "module_context_omitted": omitted}


def _apply_budget_profile(
    payload: dict,
    *,
    setting_chars: int,
    plot_chars: int,
    scene_chars: int,
    entity_chars: int,
    npc_limit: int,
    monster_limit: int,
    item_limit: int,
) -> dict:
    compact = _with_omitted(payload, "truncated_to_prompt_budget")
    scene = compact.get("scene") if isinstance(compact.get("scene"), dict) else {}
    compact["setting"] = _shorten(compact.get("setting", ""), setting_chars)
    compact["plot_summary"] = _shorten(compact.get("plot_summary", ""), plot_chars)
    compact["current_scene"] = _shorten(compact.get("current_scene", ""), scene_chars)
    compact["scene"] = {
        key: _shorten(value, scene_chars)
        for key, value in scene.items()
        if value not in (None, "", [])
    }
    compact["npcs"] = _trim_entity_fields(compact.get("npcs", []), npc_limit, entity_chars)
    compact["monsters"] = _trim_entity_fields(compact.get("monsters", []), monster_limit, entity_chars)
    compact["magic_items"] = _trim_entity_fields(compact.get("magic_items", []), item_limit, entity_chars)
    return compact


def _fit_payload(payload: dict, max_chars: int) -> dict:
    encoded = json_dumps(payload)
    if len(encoded) <= max_chars:
        return payload

    profiles = (
        dict(setting_chars=320, plot_chars=420, scene_chars=320, entity_chars=120, npc_limit=2, monster_limit=2, item_limit=1),
        dict(setting_chars=220, plot_chars=280, scene_chars=200, entity_chars=80, npc_limit=1, monster_limit=1, item_limit=1),
        dict(setting_chars=140, plot_chars=180, scene_chars=120, entity_chars=60, npc_limit=1, monster_limit=0, item_limit=0),
        dict(setting_chars=90, plot_chars=120, scene_chars=80, entity_chars=40, npc_limit=0, monster_limit=0, item_limit=0),
    )
    for profile in profiles:
        compact = _apply_budget_profile(payload, **profile)
        if len(json_dumps(compact)) <= max_chars:
            return compact

    return _apply_budget_profile(
        payload,
        setting_chars=60,
        plot_chars=80,
        scene_chars=50,
        entity_chars=30,
        npc_limit=0,
        monster_limit=0,
        item_limit=0,
    )


def json_dumps(payload: dict) -> str:
    import json
    return json.dumps(payload, ensure_ascii=False)


def build_module_context(*, module, session) -> dict:
    parsed = module.parsed_content or {}
    scenes = parsed.get("scenes", [])
    omitted = []
    for key, limit in (("npcs", 3), ("monsters", 3), ("magic_items", 2)):
        if len(parsed.get(key, []) or []) > limit:
            omitted.append(f"{key}:{len(parsed.get(key, [])) - limit}")

    payload = {
        "module_name": module.name,
        "setting": _shorten(parsed.get("setting", ""), 400),
        "tone": parsed.get("tone", "标准冒险"),
        "plot_summary": _shorten(parsed.get("plot_summary", ""), 700),
        "current_scene": session.current_scene or "",
        "scene": _find_current_scene(scenes, session.current_scene or ""),
        "npcs": _slim_entities(parsed.get("npcs", []), 3, ("name", "role", "summary", "description", "personality")),
        "monsters": _slim_entities(parsed.get("monsters", []), 3, ("name", "type", "cr", "summary", "description")),
        "magic_items": _slim_entities(parsed.get("magic_items", []), 2, ("name", "summary", "effect", "description")),
    }
    if omitted:
        payload["module_context_omitted"] = omitted
    return _fit_payload(payload, settings.module_context_max_chars)


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
