"""
api.combat.info — 战斗状态查询 / 技能栏 / 命中率预测

从原 combat.py (单体 5368 行) 按功能域拆出，逻辑未改动。
"""
import uuid
import random
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, Session, GameLog, CombatState, Module
from api.deps import (
    get_session_or_404, entity_snapshot, serialize_combat,
    get_user_id, assert_can_act, broadcast_to_session, current_turn_user_id,
)
from services.combat_service import CombatService
from services.spell_service import spell_service
from services.dnd_rules import roll_dice, _normalize_class
from services.combat_narrator import narrate_action, narrate_batch
from services.character_roster import CharacterRoster

from api.combat._shared import (
    _DEFAULT_TS, svc,
    _get_ts, _save_ts, _reset_ts,
    _broadcast_combat, _calc_entity_turn_limits,
    _chebyshev_dist, _check_attack_range, _ai_move_toward,
    _has_adjacent_enemy, _has_ally_adjacent_to,
    _do_concentration_check, _tick_conditions_char, _tick_conditions_enemy,
    _chebyshev, _resolve_opportunity_attacks,
)
from api.combat.schemas import (
    MoveRequest, ConditionRequest, CombatActionRequest, DeathSaveRequest,
    SmiteRequest, ClassFeatureRequest, ReactionRequest, GrappleShoveRequest,
    AttackRollRequest, DamageRollRequest, SpellRequest, SpellRollRequest,
    SpellConfirmRequest, ManeuverRequest,
)

router = APIRouter(prefix="/game", tags=["combat"])


# ── 获取战斗状态 ──────────────────────────────────────────

@router.get("/combat/{session_id}")
async def get_combat_state(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取当前战斗状态（含完整实体数据）"""
    result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = result.scalars().first()
    if not combat:
        raise HTTPException(404, "当前没有进行中的战斗")

    session = await get_session_or_404(session_id, db)
    await db.refresh(session)  # 确保读取最新的 game_state
    state   = session.game_state or {}
    enemies = state.get("enemies", [])
    entities: dict = {}

    roster = CharacterRoster(db, session)
    for c in await roster.party():
        entities[c.id] = entity_snapshot(c, is_enemy=False)

    for e in enemies:
        entities[e["id"]] = {
            "id":         e["id"],
            "name":       e["name"],
            "is_player":  False,
            "is_enemy":   True,
            "hp_current": e.get("hp_current", 0),
            "hp_max":     e.get("derived", {}).get("hp_max", 10),
            "ac":         e.get("derived", {}).get("ac", 10),
            "conditions": e.get("conditions", []),
        }

    return {**serialize_combat(combat), "entities": entities, "turn_states": combat.turn_states or {}}


# ═══════════════════════════════════════════════════════════
# v0.10 新增：技能栏 + 命中率预测
# ═══════════════════════════════════════════════════════════

class PredictRequest(BaseModel):
    attacker_id: str
    target_id:   str
    action_key:  str = "atk"      # atk / smite / shove / bless / heal / lay / dash / disg / pot / ...
    is_ranged:   bool = False


# ── 技能栏（基于当前玩家职业动态生成） ──────────────────────

def _build_skill_bar(player: Character) -> list[dict]:
    """
    根据玩家职业 / 等级 / 法术位 / 资源动态生成 10 格技能栏。
    key 1-9+0 对应位置 0-9。
    """
    derived = player.derived or {}
    cls = _normalize_class(player.char_class or "")
    level = player.level or 1
    slots = player.spell_slots or {}
    has_slot_1 = (slots.get("1st", 0) > 0)
    has_slot_2 = (slots.get("2nd", 0) > 0)
    resources  = derived.get("class_resources", {}) or {}

    bar: list[dict] = []

    # 所有职业通用 — 攻击
    bar.append({
        "k": "atk", "label": "普通攻击", "glyph": "⚔", "cost": "动作",
        "key": "1", "kind": "attack", "available": True,
    })

    # 职业特化的主力技能（位置 2）
    if cls == "Paladin":
        bar.append({
            "k": "smite", "label": "神圣斩击", "glyph": "✦",
            "cost": "附赠·1环", "key": "2", "kind": "spell",
            "available": has_slot_1,
            "reason": None if has_slot_1 else "需要 1 环法术位",
            "dmg_hint": f"+2d8 光耀",
        })
    elif cls == "Rogue":
        bar.append({
            "k": "sneak", "label": "偷袭", "glyph": "✧",
            "cost": "被动", "key": "2", "kind": "attack",
            "available": True,
            "dmg_hint": f"+{(level + 1) // 2}d6（优势或盟友相邻）",
        })
    elif cls == "Fighter":
        as_left = resources.get("action_surge_remaining", 1 if level >= 2 else 0)
        bar.append({
            "k": "action_surge", "label": "行动激发", "glyph": "⚡",
            "cost": "免费", "key": "2", "kind": "bonus",
            "available": as_left > 0,
            "reason": None if as_left > 0 else "本长休已用完",
        })
    elif cls == "Barbarian":
        rage_left = resources.get("rage_remaining", 2)
        bar.append({
            "k": "rage", "label": "狂暴", "glyph": "☠",
            "cost": "附赠", "key": "2", "kind": "bonus",
            "available": rage_left > 0,
            "reason": None if rage_left > 0 else "本长休已用完",
        })
    elif cls == "Wizard":
        bar.append({
            "k": "firebolt", "label": "火焰射线", "glyph": "✴",
            "cost": "动作（戏法）", "key": "2", "kind": "spell",
            "available": True,
            "dmg_hint": "1d10 火焰",
        })
    elif cls == "Cleric":
        bar.append({
            "k": "sacred_flame", "label": "神焰", "glyph": "✶",
            "cost": "动作（戏法）", "key": "2", "kind": "spell",
            "available": True,
            "dmg_hint": "1d8 光耀",
        })
    elif cls == "Monk":
        ki_left = resources.get("ki_remaining", 0)
        bar.append({
            "k": "ki_flurry", "label": "连击飞拳", "glyph": "✥",
            "cost": "附赠·1气", "key": "2", "kind": "bonus",
            "available": ki_left > 0,
            "reason": None if ki_left > 0 else "需要 1 气",
        })
    else:
        bar.append({
            "k": "off_attack", "label": "副手攻击", "glyph": "⚔",
            "cost": "附赠", "key": "2", "kind": "bonus",
            "available": True,
        })

    # 位置 3：通用防御 / 控制
    bar.append({
        "k": "shove", "label": "猛力推撞", "glyph": "↦",
        "cost": "动作", "key": "3", "kind": "attack", "available": True,
    })

    # 位置 4：施法者的治疗 / 增益
    if cls in ("Cleric", "Paladin", "Bard", "Druid"):
        bar.append({
            "k": "bless", "label": "祝福", "glyph": "✧",
            "cost": "动作·1环", "key": "4", "kind": "spell",
            "available": has_slot_1,
            "reason": None if has_slot_1 else "需要 1 环法术位",
        })
    elif cls == "Wizard":
        bar.append({
            "k": "shield", "label": "护盾术", "glyph": "✡",
            "cost": "反应·1环", "key": "4", "kind": "spell",
            "available": has_slot_1,
            "reason": None if has_slot_1 else "需要 1 环法术位",
        })
    else:
        bar.append({
            "k": "dodge", "label": "闪避", "glyph": "⊙",
            "cost": "动作", "key": "4", "kind": "bonus", "available": True,
        })

    # 位置 5：治疗
    if cls == "Paladin":
        lay_left = resources.get("lay_on_hands_pool", level * 5)
        bar.append({
            "k": "lay", "label": "治疗魔掌", "glyph": "☩",
            "cost": "动作", "key": "5", "kind": "bonus",
            "available": lay_left > 0,
            "reason": None if lay_left > 0 else "已用完本日",
            "dmg_hint": f"剩余 {lay_left} HP",
        })
    elif cls in ("Cleric", "Druid", "Bard"):
        bar.append({
            "k": "heal", "label": "治疗伤口", "glyph": "✚",
            "cost": "动作·1环", "key": "5", "kind": "spell",
            "available": has_slot_1,
            "reason": None if has_slot_1 else "需要 1 环法术位",
            "dmg_hint": "1d8 + 施法能力",
        })
    elif cls == "Fighter":
        sw_left = resources.get("second_wind_remaining", 1)
        bar.append({
            "k": "second_wind", "label": "再接再厉", "glyph": "✚",
            "cost": "附赠", "key": "5", "kind": "bonus",
            "available": sw_left > 0,
            "reason": None if sw_left > 0 else "本短休已用完",
            "dmg_hint": "1d10 + 等级",
        })
    else:
        bar.append({
            "k": "pot", "label": "治疗药剂", "glyph": "⚱",
            "cost": "动作", "key": "5", "kind": "bonus", "available": True,
            "dmg_hint": "2d4 + 2",
        })

    # 位置 6：职业可选特性
    if cls == "Paladin" and level >= 3:
        bar.append({
            "k": "divine_sense", "label": "神性感知", "glyph": "◉",
            "cost": "动作", "key": "6", "kind": "bonus", "available": True,
        })
    elif cls == "Rogue":
        bar.append({
            "k": "cunning_action", "label": "狡诈行动", "glyph": "⊿",
            "cost": "附赠", "key": "6", "kind": "bonus", "available": True,
        })
    elif cls == "Wizard" and level >= 2:
        bar.append({
            "k": "portent", "label": "预言之兆", "glyph": "☄",
            "cost": "免费", "key": "6", "kind": "bonus",
            "available": bool(resources.get("portent_dice", [])),
        })
    else:
        bar.append({
            "k": "help", "label": "协助", "glyph": "☉",
            "cost": "动作", "key": "6", "kind": "bonus", "available": True,
        })

    # 位置 7-8：通用
    bar.append({
        "k": "dash", "label": "冲刺", "glyph": "»",
        "cost": "动作", "key": "7", "kind": "move", "available": True,
    })
    bar.append({
        "k": "disg", "label": "脱离接战", "glyph": "↶",
        "cost": "动作", "key": "8", "kind": "move", "available": True,
    })

    # 位置 9：空位（保留扩展）
    bar.append({
        "k": "empty", "label": "", "glyph": "", "cost": "",
        "key": "9", "kind": "empty", "available": False,
    })

    # 位置 0：药剂
    bar.append({
        "k": "pot_heal", "label": "治疗药剂", "glyph": "⚱",
        "cost": "动作", "key": "0", "kind": "bonus", "available": True,
    })

    return bar[:10]


@router.get("/combat/{session_id}/skill-bar")
async def get_skill_bar_endpoint(
    session_id: str,
    entity_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    获取当前玩家的 10 格技能栏配置（v0.10 新增）。
    entity_id 可选，默认使用当前用户绑定的角色。
    """
    session = await get_session_or_404(session_id, db)

    # 解析目标角色
    if entity_id:
        player = await db.get(Character, entity_id)
    elif session.is_multiplayer:
        from models import SessionMember
        mem = await db.execute(
            select(SessionMember).where(
                SessionMember.session_id == session_id,
                SessionMember.user_id == user_id,
            )
        )
        m = mem.scalar_one_or_none()
        if m and m.character_id:
            player = await db.get(Character, m.character_id)
        else:
            player = None
    else:
        player = await db.get(Character, session.player_character_id)

    if not player:
        raise HTTPException(404, "未找到角色")

    return {
        "entity_id": player.id,
        "class": player.char_class,
        "level": player.level,
        "bar": _build_skill_bar(player),
    }


# ── 命中率预测 ──────────────────────────────────────────

@router.post("/combat/{session_id}/predict")
async def predict_action_endpoint(
    session_id: str,
    req: PredictRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    预测一次行动的命中率 / 暴击率 / 期望伤害（v0.10 新增）。
    纯算数，不掷骰、不消耗资源、不改状态。
    仅作为 UI 参考值展示；实际战斗仍以 /attack-roll / /spell-roll 为准。
    """
    session = await get_session_or_404(session_id, db)
    attacker = await db.get(Character, req.attacker_id)
    if not attacker:
        raise HTTPException(404, "攻击者不存在")

    a_derived = attacker.derived or {}

    # 解析目标（角色 or 敌人）
    state = session.game_state or {}
    enemies = state.get("enemies", [])
    target_ac = 10
    target_name = "?"
    target_hp = target_hp_max = 0
    target_conditions: list[str] = []

    tgt_char = await db.get(Character, req.target_id)
    if tgt_char:
        target_ac = (tgt_char.derived or {}).get("ac", 10)
        target_name = tgt_char.name
        target_hp = tgt_char.hp_current
        target_hp_max = (tgt_char.derived or {}).get("hp_max", tgt_char.hp_current)
        target_conditions = tgt_char.conditions or []
    else:
        enemy = next((e for e in enemies if e.get("id") == req.target_id), None)
        if enemy:
            target_ac = (enemy.get("derived") or {}).get("ac", enemy.get("ac", 10))
            target_name = enemy.get("name", "敌人")
            target_hp = enemy.get("hp_current", 0)
            target_hp_max = (enemy.get("derived") or {}).get("hp_max", target_hp)
            target_conditions = enemy.get("conditions", [])

    # 优势/劣势判断
    atk_adv, atk_dis = svc.get_attack_modifiers(attacker.conditions or [])
    def_adv, def_dis = svc.get_defense_modifiers(target_conditions)

    # 攻击修正
    if req.is_ranged:
        atk_bonus = a_derived.get("ranged_attack_bonus", a_derived.get("attack_bonus", 0))
    else:
        atk_bonus = a_derived.get("attack_bonus", 0)

    # 计算命中率（单次 d20 命中概率）
    # 需要 d20+mod >= AC，即 d20 >= AC - mod
    threshold = target_ac - atk_bonus
    if threshold <= 2:
        base_hit = 0.95  # 除自然1
    elif threshold >= 20:
        base_hit = 0.05  # 只有自然20
    else:
        # (20 - threshold + 1) / 20
        base_hit = max(0.05, min(0.95, (21 - threshold) / 20.0))

    # 优劣势下的命中率
    final_adv = (atk_adv or def_adv) and not (atk_dis or def_dis)
    final_dis = (atk_dis or def_dis) and not (atk_adv or def_adv)
    if final_adv:
        hit_rate = 1 - (1 - base_hit) ** 2
    elif final_dis:
        hit_rate = base_hit ** 2
    else:
        hit_rate = base_hit

    # 暴击率（自然 20）
    if final_adv:
        crit_rate = 1 - (19 / 20) ** 2
    elif final_dis:
        crit_rate = (1 / 20) ** 2
    else:
        crit_rate = 1 / 20

    # 期望伤害（简化：基于 action_key）
    action_map = {
        "atk":    {"dice": "1d8", "avg": 4.5,  "type": "切割", "bonus": a_derived.get("ability_modifiers", {}).get("str", 0)},
        "smite":  {"dice": "1d8+2d8", "avg": 4.5 + 9.0, "type": "光耀", "bonus": a_derived.get("ability_modifiers", {}).get("str", 0)},
        "sneak":  {"dice": "1d6", "avg": 3.5,  "type": "切割", "bonus": a_derived.get("ability_modifiers", {}).get("dex", 0)},
        "firebolt": {"dice": "1d10", "avg": 5.5, "type": "火焰", "bonus": 0},
        "sacred_flame": {"dice": "1d8", "avg": 4.5, "type": "光耀", "bonus": 0},
        "shove":  {"dice": "—", "avg": 0.0, "type": "力量对抗", "bonus": 0},
    }
    info = action_map.get(req.action_key, action_map["atk"])

    # 期望伤害 = hit_rate * (dice_avg + bonus) + crit_rate * dice_avg（近似）
    dmg_avg = info["avg"] + info["bonus"]
    expected_damage = round(hit_rate * dmg_avg + crit_rate * info["avg"], 1)

    # 修正标签
    modifiers = []
    if final_adv: modifiers.append("优势")
    if final_dis: modifiers.append("劣势")
    if req.is_ranged: modifiers.append("远程")
    if atk_adv and not atk_dis: modifiers.append("攻击者状态+")
    if def_adv and not def_dis: modifiers.append("目标状态+")

    return {
        "target": {
            "name": target_name,
            "hp": target_hp,
            "hp_max": target_hp_max,
            "ac": target_ac,
        },
        "hit_rate": round(hit_rate, 2),
        "crit_rate": round(crit_rate, 3),
        "expected_damage": expected_damage,
        "damage_dice": info["dice"],
        "damage_type": info["type"],
        "attack_bonus": atk_bonus,
        "modifiers": modifiers,
    }


# ── 玩家战斗行动 ──────────────────────────────────────────

