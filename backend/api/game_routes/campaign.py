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
    get_effective_hp_base,
    get_effective_hp_max,
    apply_character_healing,
    get_class_resource_defaults,
    roll_dice,
)
from services.langgraph_client import langgraph_client

router = APIRouter(prefix="/game", tags=["game"])

LONG_REST_REDUCED_CONDITIONS = {
    "exhaustion",
    "poisoned",
    "frightened",
    "charmed",
    "unconscious",
    "stunned",
    "restrained",
    "grappled",
    "prone",
    "incapacitated",
    "paralyzed",
}
LONG_REST_PERSISTENT_CONDITIONS = {
    "blinded",
    "deafened",
    "petrified",
    "invisible",
}
LONG_REST_TRANSIENT_RESOURCE_FLAGS = {
    "raging",
    "wild_shape_active",
    "wild_shape_hp",
    "symbiotic_entity_active",
    "portent_value",
}


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
    base_hp_max = get_effective_hp_base(character, derived)
    hp_max = get_effective_hp_max(character, base_hp_max)
    hit_die = derived.get("hit_die", HIT_DICE.get(_normalize_class(character.char_class), 8))
    con_mod = derived.get("ability_modifiers", {}).get("con", 0)
    caster_type = derived.get("caster_type")
    slots_max = dict(derived.get("spell_slots_max", {}))
    old_hp = character.hp_current
    if character.hit_dice_remaining is None:
        character.hit_dice_remaining = character.level

    if rest_type == "long":
        return _apply_long_rest_to_character(
            character=character,
            old_hp=old_hp,
            hp_max=hp_max,
            base_hp_max=base_hp_max,
            slots_max=slots_max,
        )

    return _apply_short_rest_to_character(
        character=character,
        old_hp=old_hp,
        hp_max=hp_max,
        base_hp_max=base_hp_max,
        hit_die=hit_die,
        con_mod=con_mod,
        caster_type=caster_type,
        slots_max=slots_max,
    )


def _apply_long_rest_to_character(
    *,
    character,
    old_hp: int,
    hp_max: int,
    base_hp_max: int,
    slots_max: dict,
) -> dict:
    cls_key = _normalize_class(character.char_class)
    hit_dice_before = character.hit_dice_remaining or 0
    restored_dice_budget = max(1, character.level // 2)
    hit_dice_after = min(character.level, hit_dice_before + restored_dice_budget)
    conditions_before = list(character.conditions or [])
    durations_before = dict(character.condition_durations or {})
    exhaustion_before = int(durations_before.get("exhaustion_level", 0) or 0)
    death_saves_before = dict(character.death_saves or {})

    exhaustion_after = max(0, exhaustion_before - 1)
    durations_after = dict(durations_before)
    if exhaustion_before:
        durations_after["exhaustion_level"] = exhaustion_after
    if exhaustion_after == 0:
        durations_after.pop("exhaustion_level", None)

    conditions_after = _long_rest_conditions_after(
        conditions_before=conditions_before,
        exhaustion_after=exhaustion_after,
    )
    conditions_removed = [cond for cond in conditions_before if cond not in conditions_after]
    for condition in conditions_removed:
        if condition != "exhaustion":
            durations_after.pop(condition, None)

    character.conditions = conditions_after
    character.condition_durations = durations_after
    effective_hp_max = get_effective_hp_max(character, base_hp_max)
    character.hp_current = effective_hp_max
    character.spell_slots = slots_max
    character.concentration = None
    character.death_saves = None
    character.hit_dice_remaining = hit_dice_after
    character.class_resources = _long_rest_class_resources(character, cls_key)
    _flag_character_json_fields(character)

    return {
        "name": character.name,
        "hp_recovered": effective_hp_max - old_hp,
        "hp_current": effective_hp_max,
        "hp_max": effective_hp_max,
        "base_hp_max": base_hp_max,
        "slots_restored": slots_max,
        "hit_dice_remaining": character.hit_dice_remaining,
        "hit_dice_total": character.level,
        "hit_dice_restored": hit_dice_after - hit_dice_before,
        "conditions_removed": conditions_removed,
        "exhaustion_level_before": exhaustion_before,
        "exhaustion_level_after": exhaustion_after,
        "death_saves_reset": bool(death_saves_before),
        "class_resources": character.class_resources,
    }


def _long_rest_conditions_after(*, conditions_before: list[str], exhaustion_after: int) -> list[str]:
    result = []
    for condition in conditions_before:
        if condition == "exhaustion":
            if exhaustion_after > 0:
                result.append(condition)
            continue
        if condition in LONG_REST_REDUCED_CONDITIONS:
            continue
        if condition in LONG_REST_PERSISTENT_CONDITIONS:
            result.append(condition)
            continue
        # Unknown conditions are usually exploration/encounter effects; keep them
        # until a rule, item, or scene explicitly removes them.
        result.append(condition)
    return result


def _long_rest_class_resources(character, cls_key: str) -> dict:
    resources = get_class_resource_defaults(cls_key, character.level, subclass=character.subclass)
    resources.update(_rest_calculated_resource_values(character, cls_key))
    for key in LONG_REST_TRANSIENT_RESOURCE_FLAGS:
        resources.pop(key, None)
    return resources


def _apply_short_rest_to_character(
    *,
    character,
    old_hp: int,
    hp_max: int,
    base_hp_max: int,
    hit_die: int,
    con_mod: int,
    caster_type: str | None,
    slots_max: dict,
) -> dict:
    hd_remaining = character.hit_dice_remaining or 0
    hit_roll_result = None
    hit_dice_spent = 0
    if hd_remaining > 0 and character.hp_current < hp_max:
        hit_roll = roll_dice(f"1d{hit_die}")
        heal_amt = max(1, hit_roll["total"] + con_mod)
        apply_character_healing(character, heal_amt)
        character.hit_dice_remaining = hd_remaining - 1
        hit_roll_result = hit_roll["rolls"][0]
        hit_dice_spent = 1

    if caster_type == "pact":
        character.spell_slots = slots_max

    class_resources = dict(character.class_resources or {})
    changed = _restore_short_rest_class_resources(character, class_resources)
    if changed:
        character.class_resources = class_resources
    _flag_character_json_fields(character)

    return {
        "name": character.name,
        "hit_die_roll": hit_roll_result,
        "con_mod": con_mod,
        "hp_recovered": character.hp_current - old_hp,
        "hp_current": character.hp_current,
        "hp_max": hp_max,
        "base_hp_max": base_hp_max,
        "slots_restored": slots_max if caster_type == "pact" else {},
        "hit_dice_remaining": character.hit_dice_remaining,
        "hit_dice_total": character.level,
        "hit_dice_spent": hit_dice_spent,
        "no_hit_dice": hd_remaining <= 0 and character.hp_current < hp_max,
        "no_healing_needed": old_hp >= hp_max,
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
        if sub_effects.get("samurai"):
            class_resources["fighting_spirit_remaining"] = sub_effects.get("fighting_spirit_uses", 1)
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
        class_resources["wild_shape_remaining"] = 2
        class_resources.pop("wild_shape_active", None)
        class_resources.pop("wild_shape_hp", None)
        class_resources.pop("symbiotic_entity_active", None)
        _restore_druid_natural_recovery(character)
        return True

    if cls_key == "Warlock":
        return False

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


def _rest_calculated_resource_values(character, cls_key: str) -> dict:
    sub_effects = (character.derived or {}).get("subclass_effects", {})
    ability_mods = (character.derived or {}).get("ability_modifiers", {})
    values = {}
    if cls_key == "Fighter" and sub_effects.get("samurai"):
        values["fighting_spirit_remaining"] = sub_effects.get(
            "fighting_spirit_uses",
            max(1, ability_mods.get("wis", 1)),
        )
    if cls_key == "Bard":
        values["bardic_inspiration_remaining"] = max(1, ability_mods.get("cha", 3))
    if cls_key == "Cleric" and sub_effects.get("war_domain"):
        values["war_priest_remaining"] = max(1, ability_mods.get("wis", 1))
    if cls_key == "Wizard" and sub_effects.get("divination"):
        values["portent_remaining"] = sub_effects.get("portent_count", 3 if character.level >= 14 else 2)
    return values


def _flag_character_json_fields(character) -> None:
    for field in (
        "spell_slots",
        "conditions",
        "condition_durations",
        "death_saves",
        "class_resources",
    ):
        flag_modified(character, field)
