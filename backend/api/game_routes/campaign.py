from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.deps import assert_session_access, can_user_see_log, get_session_or_404, get_user_id
from database import get_db
from models import GameLog, Module
from schemas.game_responses import RestResponse
from services.character_roster import CharacterRoster
from services.dnd_rules import (
    HIT_DICE,
    _normalize_class,
    get_class_resource_defaults,
    roll_dice,
)
from services.langgraph_client import langgraph_client

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/sessions/{session_id}/journal")
async def generate_journal(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """生成本次冒险的叙事日志摘要（调用 DM Agent Chatflow，独立新对话）"""
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    module = await db.get(Module, session.module_id)
    log_result = await db.execute(
        select(GameLog)
        .where(GameLog.session_id == session_id)
        .order_by(GameLog.created_at.asc())
        .limit(80)
    )
    logs = [log for log in log_result.scalars().all() if can_user_see_log(log, user_id)]
    if not logs:
        return {"journal": "还没有冒险记录可以生成日志。"}

    log_text = "\n".join(f"[{log.role}] {log.content}" for log in logs if log.content)
    module_summary = (module.parsed_content or {}).get("plot_summary", "") if module else ""
    try:
        from langchain_core.messages import HumanMessage as _HM, SystemMessage as _SM
        from services.llm import get_llm

        llm = get_llm(temperature=0.8, max_tokens=800)
        resp = await llm.ainvoke([
            _SM(content="你是一位文笔出众的 DnD 5e 编年史作者，擅长将冒险记录改写为史诗般的战役日志。"),
            _HM(content=(
                f"## 模组背景\n{module_summary}\n\n"
                f"## 冒险记录\n{log_text[-3000:]}\n\n"
                "请以第三人称叙事风格，为这段冒险旅程写一篇简短的战役日志（300字左右）。"
                "包含：英雄们的行动、遭遇的危险、关键事件和转折。"
                "语气史诗而充满感情，像一部奇幻小说的章节摘要。"
                "直接输出日志正文，不要有任何前缀、标签或JSON格式。"
            )),
        ])
        journal_text = resp.content.strip()
        if not journal_text or len(journal_text) < 20:
            journal_text = "日志生成失败"
    except Exception as exc:
        journal_text = f"（AI日志生成失败：{exc}）\n\n以下为原始记录节选：\n\n{log_text[:800]}"

    state = dict(session.game_state or {})
    state["last_journal"] = journal_text
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
    return {"journal": journal_text, "log_count": len(logs)}


@router.post("/sessions/{session_id}/checkpoint")
async def save_checkpoint(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """将当前会话的冒险记录压缩为结构化 Campaign State JSON 并存档。"""
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    module = await db.get(Module, session.module_id)
    log_result = await db.execute(
        select(GameLog)
        .where(GameLog.session_id == session_id)
        .where(GameLog.log_type.in_(["narrative", "companion", "combat"]))
        .order_by(GameLog.created_at.asc())
        .limit(120)
    )
    logs = [log for log in log_result.scalars().all() if can_user_see_log(log, user_id)]
    if not logs:
        return {"ok": False, "message": "没有可以存档的内容"}

    log_text = "\n".join(f"[{log.role}] {log.content}" for log in logs if log.content)
    module_summary = (module.parsed_content or {}).get("plot_summary", "") if module else ""
    try:
        new_campaign_state = await langgraph_client.generate_campaign_state(
            log_text=log_text[-4000:],
            module_summary=module_summary,
            existing_state=session.campaign_state or {},
        )
    except Exception as exc:
        raise HTTPException(502, f"档案生成失败: {exc}") from exc

    session.campaign_state = new_campaign_state
    await db.commit()
    return {"ok": True, "campaign_state": new_campaign_state}


@router.get("/sessions/{session_id}/checkpoint")
async def get_checkpoint(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """获取当前战役档案（用于前端展示存档详情）"""
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    return {
        "session_id": session_id,
        "campaign_state": session.campaign_state or {},
        "has_checkpoint": session.campaign_state is not None,
    }


@router.post("/sessions/{session_id}/rest", response_model=RestResponse)
async def take_rest(
    session_id: str,
    rest_type: str = "long",
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """长休/短休，恢复 HP、法术位、生命骰和职业资源。"""
    if rest_type not in ("long", "short"):
        raise HTTPException(400, "rest_type 必须为 'long' 或 'short'")

    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    roster = CharacterRoster(db, session)
    results = []
    for character in await roster.party():
        results.append(_apply_rest_to_character(character, rest_type))

    rest_label = "长休" if rest_type == "long" else "短休"
    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=(
            f"🌙 队伍完成了{rest_label}。"
            + ("HP和法术位已完全恢复。" if rest_type == "long" else "消耗了一颗生命骰。")
        ),
        log_type="system",
    ))
    await db.commit()
    return {"rest_type": rest_type, "characters": results}


def _apply_rest_to_character(character, rest_type: str) -> dict:
    derived = character.derived or {}
    hp_max = derived.get("hp_max", character.hp_current)
    hit_die = derived.get("hit_die", HIT_DICE.get(_normalize_class(character.char_class), 8))
    con_mod = derived.get("ability_modifiers", {}).get("con", 0)
    caster_type = derived.get("caster_type")
    slots_max = dict(derived.get("spell_slots_max", {}))
    old_hp = character.hp_current
    if character.hit_dice_remaining is None:
        character.hit_dice_remaining = character.level

    if rest_type == "long":
        cls_key = _normalize_class(character.char_class)
        restored_dice = max(1, character.level // 2)
        character.hp_current = hp_max
        character.spell_slots = slots_max
        character.conditions = []
        character.concentration = None
        character.hit_dice_remaining = min(character.level, (character.hit_dice_remaining or 0) + restored_dice)
        character.class_resources = get_class_resource_defaults(cls_key, character.level, subclass=character.subclass)
        return {
            "name": character.name,
            "hp_recovered": hp_max - old_hp,
            "hp_current": hp_max,
            "slots_restored": slots_max,
            "hit_dice_remaining": character.hit_dice_remaining,
        }

    return _apply_short_rest_to_character(
        character=character,
        old_hp=old_hp,
        hp_max=hp_max,
        hit_die=hit_die,
        con_mod=con_mod,
        caster_type=caster_type,
        slots_max=slots_max,
    )


def _apply_short_rest_to_character(
    *,
    character,
    old_hp: int,
    hp_max: int,
    hit_die: int,
    con_mod: int,
    caster_type: str | None,
    slots_max: dict,
) -> dict:
    hd_remaining = character.hit_dice_remaining or 0
    hit_roll_result = None
    if hd_remaining > 0:
        hit_roll = roll_dice(f"1d{hit_die}")
        heal_amt = max(1, hit_roll["total"] + con_mod)
        character.hp_current = min(hp_max, character.hp_current + heal_amt)
        character.hit_dice_remaining = hd_remaining - 1
        hit_roll_result = hit_roll["rolls"][0]

    if caster_type == "pact":
        character.spell_slots = slots_max

    class_resources = dict(character.class_resources or {})
    changed = _restore_short_rest_class_resources(character, class_resources)
    if changed:
        character.class_resources = class_resources

    return {
        "name": character.name,
        "hit_die_roll": hit_roll_result,
        "con_mod": con_mod,
        "hp_recovered": character.hp_current - old_hp,
        "hp_current": character.hp_current,
        "slots_restored": slots_max if caster_type == "pact" else {},
        "hit_dice_remaining": character.hit_dice_remaining,
        "no_hit_dice": hd_remaining <= 0,
        "class_resources": class_resources if changed else None,
    }


def _restore_short_rest_class_resources(character, class_resources: dict) -> bool:
    cls_key = _normalize_class(character.char_class)
    if cls_key == "Fighter":
        class_resources["second_wind_used"] = False
        if character.level >= 2:
            class_resources["action_surge_used"] = False
        sub_effects = (character.derived or {}).get("subclass_effects", {})
        if sub_effects.get("battle_master"):
            class_resources["superiority_dice_remaining"] = sub_effects.get("superiority_dice_max", 4)
        return True

    if cls_key == "Monk" and character.level >= 2:
        class_resources["ki_remaining"] = (character.derived or {}).get("subclass_effects", {}).get("ki_max", character.level)
        return True

    if cls_key == "Bard" and character.level >= 5:
        cha_mod = (character.derived or {}).get("ability_modifiers", {}).get("cha", 3)
        class_resources["bardic_inspiration_remaining"] = max(1, cha_mod)
        return True

    if cls_key in {"Cleric", "Paladin"}:
        class_resources["channel_divinity_used"] = False
        return True

    if cls_key == "Druid":
        _restore_druid_natural_recovery(character)
        return True

    return False


def _restore_druid_natural_recovery(character) -> None:
    sub_effects = (character.derived or {}).get("subclass_effects", {})
    if not (sub_effects.get("circle_of_land") and sub_effects.get("natural_recovery")):
        return

    max_slot_level = (character.level + 1) // 2
    slots_max = (character.derived or {}).get("spell_slots_max", {})
    current_slots = dict(character.spell_slots or {})
    recovery_budget = (character.level + 1) // 2
    for level in range(1, min(max_slot_level + 1, 6)):
        slot_key = ["1st", "2nd", "3rd", "4th", "5th"][level - 1]
        cap = slots_max.get(slot_key, 0)
        current = current_slots.get(slot_key, 0)
        if current < cap and recovery_budget >= level:
            current_slots[slot_key] = current + 1
            recovery_budget -= level
    character.spell_slots = current_slots
