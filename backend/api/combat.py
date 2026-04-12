"""
战斗路由 — 所有 /game/combat/* 端点
业务逻辑委托给 CombatService 和 SpellService
"""
import uuid
import random
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models import Character, Session, GameLog, CombatState, Module
from api.deps import get_session_or_404, entity_snapshot, serialize_combat
from services.combat_service import CombatService
from services.spell_service import spell_service
from services.dnd_rules import roll_dice, _normalize_class
from services.combat_narrator import narrate_action, narrate_batch
from sqlalchemy.orm.attributes import flag_modified

router = APIRouter(prefix="/game", tags=["combat"])
svc = CombatService()


# ── 回合行动配额（Turn State）────────────────────────────────

_DEFAULT_TS: dict = {
    "action_used":       False,
    "bonus_action_used": False,
    "reaction_used":     False,
    "movement_used":     0,
    "movement_max":      6,    # 30ft = 6 tiles
    "disengaged":        False,
    "being_helped":      False,
    "attacks_made":      0,    # Extra Attack 追踪
    "attacks_max":       1,    # 默认 1 次（Extra Attack 可增加）
}


def _get_ts(combat: CombatState, entity_id: str) -> dict:
    """取实体当前回合状态，不存在则返回默认值。"""
    states = combat.turn_states or {}
    return dict(states.get(str(entity_id), _DEFAULT_TS))


def _save_ts(combat: CombatState, entity_id: str, ts: dict) -> None:
    states = dict(combat.turn_states or {})
    states[str(entity_id)] = ts
    combat.turn_states = states
    flag_modified(combat, "turn_states")


def _reset_ts(combat: CombatState, entity_id: str,
              attacks_max: int = 1, movement_max: int = 6) -> None:
    ts = dict(_DEFAULT_TS)
    ts["attacks_max"] = attacks_max
    ts["movement_max"] = movement_max
    _save_ts(combat, entity_id, ts)


async def _calc_entity_turn_limits(db, session, entity_id: str) -> tuple:
    """计算实体的每回合攻击次数和移动格数。返回 (attacks_max, movement_max)。"""
    # 检查是否为角色（玩家/队友）
    char = await db.get(Character, entity_id)
    if char:
        derived = char.derived or {}
        cls = _normalize_class(char.char_class)
        level = char.level or 1
        attacks_max = svc.get_attack_count(derived, level, cls)
        speed = 30  # 默认 30ft
        if char.equipment:
            # 重甲对某些种族减速，暂不处理
            pass
        movement_max = speed // 5  # 转为格数
        return attacks_max, movement_max

    # 检查是否为敌人
    state = session.game_state or {}
    for e in state.get("enemies", []):
        if str(e.get("id")) == str(entity_id):
            raw_speed = e.get("speed", 30)
            # speed 可能是字符串如 "30ft" 或数字 30
            if isinstance(raw_speed, str):
                import re as _re
                m = _re.search(r'(\d+)', str(raw_speed))
                raw_speed = int(m.group(1)) if m else 30
            speed = max(int(raw_speed or 30), 20)
            movement_max = speed // 5
            return 1, movement_max  # 怪物默认 1 次攻击

    return 1, 6  # 兜底默认值


def _chebyshev_dist(pos_a: dict, pos_b: dict) -> int:
    """两个格子间的 Chebyshev 距离（对角线=1）"""
    if not pos_a or not pos_b: return 999
    return max(abs(pos_a.get("x",0) - pos_b.get("x",0)), abs(pos_a.get("y",0) - pos_b.get("y",0)))


def _check_attack_range(atk_pos: dict, tgt_pos: dict, is_ranged: bool, weapon_range: int = 0) -> tuple:
    """
    检查攻击距离是否合法。
    Returns: (in_range: bool, distance: int, error_msg: str|None)
    """
    dist = _chebyshev_dist(atk_pos, tgt_pos)
    if is_ranged:
        max_range = max(weapon_range // 5, 24) if weapon_range else 24  # 默认120ft=24格
        if dist < 1:
            return True, dist, None  # 近距离远程（有劣势但允许）
        if dist > max_range:
            return False, dist, f"目标超出射程（距离{dist*5}ft，最大{max_range*5}ft）"
        return True, dist, None
    else:
        # 近战：必须相邻（Chebyshev ≤ 1，即5ft触及）
        if dist > 1:
            return False, dist, f"目标不在近战范围内（距离{dist*5}ft，需要5ft内）。请先移动到目标旁边"
        return True, dist, None


def _ai_move_toward(actor_pos: dict, target_pos: dict, move_budget: int,
                     positions: dict, actor_id: str) -> dict | None:
    """
    AI 自动向目标移动，最多 move_budget 格。
    返回新位置 dict {x, y}，或 None 表示无法/不需要移动。
    使用简单贪心：每步走向目标，跳过被占据的格子。
    """
    if not actor_pos or not target_pos or move_budget <= 0:
        return None

    occupied = set()
    for eid, pos in positions.items():
        if str(eid) != str(actor_id):
            occupied.add((pos.get("x", -1), pos.get("y", -1)))

    cx, cy = actor_pos["x"], actor_pos["y"]
    tx, ty = target_pos["x"], target_pos["y"]
    steps_taken = 0

    for _ in range(move_budget):
        # 已经相邻（Chebyshev ≤ 1），停止
        if max(abs(cx - tx), abs(cy - ty)) <= 1:
            break

        # 计算方向
        dx = 0 if cx == tx else (1 if tx > cx else -1)
        dy = 0 if cy == ty else (1 if ty > cy else -1)

        # 尝试对角移动 → 水平 → 垂直
        candidates = [(cx + dx, cy + dy)]
        if dx != 0 and dy != 0:
            candidates += [(cx + dx, cy), (cx, cy + dy)]
        elif dx != 0:
            candidates += [(cx + dx, cy + 1), (cx + dx, cy - 1)]
        else:
            candidates += [(cx + 1, cy + dy), (cx - 1, cy + dy)]

        moved = False
        for nx, ny in candidates:
            if 0 <= nx < 20 and 0 <= ny < 12 and (nx, ny) not in occupied:
                cx, cy = nx, ny
                steps_taken += 1
                moved = True
                break

        if not moved:
            break

    if steps_taken == 0:
        return None
    return {"x": cx, "y": cy, "steps": steps_taken}


def _has_adjacent_enemy(entity_id: str, enemies: list, positions: dict) -> bool:
    """判断实体是否与存活敌人相邻（Chebyshev ≤ 1，即 5ft 内）。"""
    pos = positions.get(str(entity_id))
    if not pos:
        return False
    px, py = pos.get("x", -99), pos.get("y", -99)
    for e in enemies:
        if e.get("hp_current", 0) <= 0:
            continue
        ep = positions.get(str(e["id"]))
        if not ep:
            continue
        if max(abs(ep["x"] - px), abs(ep["y"] - py)) <= 1:
            return True
    return False


def _has_ally_adjacent_to(target_id: str, attacker_id: str,
                          allies: list, positions: dict) -> bool:
    """Check if any ally (other than attacker) is adjacent to the target (Chebyshev <= 1)."""
    tpos = positions.get(str(target_id))
    if not tpos:
        return False
    for ally in allies:
        aid = str(ally.get("id", ""))
        if aid == str(attacker_id):
            continue
        if ally.get("hp_current", 0) <= 0:
            continue
        apos = positions.get(aid)
        if not apos:
            continue
        if max(abs(apos["x"] - tpos["x"]), abs(apos["y"] - tpos["y"])) <= 1:
            return True
    return False


# ── 共享辅助 ──────────────────────────────────────────────

async def _do_concentration_check(
    char: "Character",
    damage: int,
    session_id: str,
) -> "Optional[GameLog]":
    """
    受伤后的专注中断检定。
    - 若无专注或伤害为0，直接返回 None
    - 失败则清除 char.concentration
    - 返回需要写入 DB 的 GameLog，调用方负责 db.add()
    """
    if not char.concentration or damage <= 0:
        return None

    check = svc.check_concentration(
        character_dict={
            "concentration":    char.concentration,
            "derived":          char.derived or {},
            "proficient_saves": char.proficient_saves or [],
        },
        damage=damage,
    )
    if not check:
        return None

    r          = check["roll_result"]
    spell_name = check["spell_name"]
    wc_tag = "（战争施法者·优势）" if check.get("war_caster") else ""
    if check["broke"]:
        char.concentration = None
        msg = (f"💔 {char.name} 失去了【{spell_name}】的专注！"
               f" CON豁免{wc_tag} DC{check['dc']}：d20={r['d20']}+{r['modifier']}={r['total']} ❌")
    else:
        msg = (f"🧘 {char.name} 维持了【{spell_name}】的专注。"
               f" CON豁免{wc_tag} DC{check['dc']}：d20={r['d20']}+{r['modifier']}={r['total']} ✅")

    return GameLog(
        session_id  = session_id,
        role        = "system",
        content     = msg,
        log_type    = "dice",
        dice_result = {
            "type": "concentration", "dc": check["dc"],
            "broke": check["broke"], **r,
        },
    )


# ── 条件持续时间辅助 ──────────────────────────────────────

def _tick_conditions_char(char: "Character") -> list[str]:
    """回合开始时递减角色状态持续时间，到期自动移除。返回已移除的条件列表。"""
    durations  = dict(char.condition_durations or {})
    conditions = list(char.conditions or [])
    removed    = []
    for cond in list(durations.keys()):
        durations[cond] -= 1
        if durations[cond] <= 0:
            durations.pop(cond)
            conditions = [c for c in conditions if c != cond]
            removed.append(cond)
    char.condition_durations = durations
    char.conditions          = conditions
    return removed


def _tick_conditions_enemy(enemy: dict) -> list[str]:
    """回合开始时递减敌人状态持续时间。"""
    durations  = dict(enemy.get("condition_durations", {}))
    conditions = list(enemy.get("conditions", []))
    removed    = []
    for cond in list(durations.keys()):
        durations[cond] -= 1
        if durations[cond] <= 0:
            durations.pop(cond)
            conditions = [c for c in conditions if c != cond]
            removed.append(cond)
    enemy["condition_durations"] = durations
    enemy["conditions"]          = conditions
    return removed


# ── 借机攻击辅助 ──────────────────────────────────────────

def _chebyshev(pos_a: dict, pos_b: dict) -> int:
    """Chebyshev 距离（5ft = 1格，对角也算 1 格）。"""
    return max(abs(pos_a["x"] - pos_b["x"]), abs(pos_a["y"] - pos_b["y"]))


async def _resolve_opportunity_attacks(
    db,
    session,
    combat: "CombatState",
    moving_id: str,
    old_pos: dict,
    new_pos: dict,
    positions: dict,
) -> list[dict]:
    """
    检查并解析因移动触发的借机攻击（Opportunity Attack，5e PHB p.195）。

    规则：
      - 移动方未脱离接战（disengaged=False）
      - 从威胁者的临近格（Chebyshev≤1）移入非临近格
      - 威胁者本轮 reaction 尚未使用

    触发方向：
      - 移动的是玩家/队友 → 相邻的存活敌人可借机攻击
      - 移动的是敌人      → 玩家及相邻存活队友可借机攻击

    返回：每次借机攻击结果 dict（含 log、attacker、result）。
    """
    state   = session.game_state or {}
    enemies = list(state.get("enemies", []))
    results = []
    is_enemy_moving = moving_id in {e["id"] for e in enemies}

    if not is_enemy_moving:
        # ── 移动的是玩家/队友：相邻存活敌人发动借机攻击 ──
        moving_char = await db.get(Character, moving_id)
        if not moving_char:
            return results

        for enemy in enemies:
            if enemy.get("hp_current", 0) <= 0:
                continue
            ep = positions.get(str(enemy["id"]))
            if not ep:
                continue
            if _chebyshev(ep, old_pos) <= 1 and _chebyshev(ep, new_pos) > 1:
                e_ts = _get_ts(combat, enemy["id"])
                if e_ts.get("reaction_used"):
                    continue
                result = svc.resolve_melee_attack(
                    attacker_derived = enemy.get("derived", {}),
                    target_derived   = moving_char.derived or {},
                )
                e_ts["reaction_used"] = True
                _save_ts(combat, enemy["id"], e_ts)

                if result.attack_roll["hit"]:
                    moving_char.hp_current = svc.apply_damage(
                        moving_char.hp_current, result.damage,
                        (moving_char.derived or {}).get("hp_max", moving_char.hp_current),
                    )
                    conc_log = await _do_concentration_check(
                        moving_char, result.damage, session.id
                    )
                    if conc_log:
                        db.add(conc_log)

                narration = svc._build_narration(
                    enemy["name"], moving_char.name,
                    result.attack_roll, result.damage,
                )
                results.append({
                    "attacker": enemy["name"],
                    "target":   moving_char.name,
                    "log": GameLog(
                        session_id  = session.id,
                        role        = "system",
                        content     = f"⚔️ 借机攻击！{narration}",
                        log_type    = "combat",
                        dice_result = {
                            "attack": result.attack_roll,
                            "damage": result.damage,
                            "opportunity": True,
                        },
                    ),
                    "result": result.to_dict(),
                })

    else:
        # ── 移动的是敌人：玩家和相邻队友发动借机攻击 ──
        moving_enemy = next((e for e in enemies if e["id"] == moving_id), None)
        if not moving_enemy:
            return results

        # 玩家
        player = await db.get(Character, session.player_character_id)
        if player and player.hp_current > 0:
            pp = positions.get(str(session.player_character_id))
            if pp and _chebyshev(pp, old_pos) <= 1 and _chebyshev(pp, new_pos) > 1:
                p_ts = _get_ts(combat, session.player_character_id)
                if not p_ts.get("reaction_used"):
                    result = svc.resolve_melee_attack(
                        attacker_derived = player.derived or {},
                        target_derived   = moving_enemy.get("derived", {}),
                    )
                    p_ts["reaction_used"] = True
                    _save_ts(combat, session.player_character_id, p_ts)

                    if result.attack_roll["hit"]:
                        moving_enemy["hp_current"] = svc.apply_damage(
                            moving_enemy.get("hp_current", 0), result.damage,
                            moving_enemy.get("derived", {}).get("hp_max", 10),
                        )
                        state["enemies"]   = enemies
                        session.game_state = dict(state); flag_modified(session, "game_state")

                    narration = svc._build_narration(
                        player.name, moving_enemy["name"],
                        result.attack_roll, result.damage,
                    )
                    results.append({
                        "attacker": player.name,
                        "target":   moving_enemy["name"],
                        "log": GameLog(
                            session_id  = session.id,
                            role        = "player",
                            content     = f"⚔️ 借机攻击！{narration}",
                            log_type    = "combat",
                            dice_result = {
                                "attack": result.attack_roll,
                                "damage": result.damage,
                                "opportunity": True,
                            },
                        ),
                        "result": result.to_dict(),
                    })

        # 队友
        for cid in state.get("companion_ids", []):
            companion = await db.get(Character, cid)
            if not companion or companion.hp_current <= 0:
                continue
            cp = positions.get(str(cid))
            if not cp:
                continue
            if _chebyshev(cp, old_pos) <= 1 and _chebyshev(cp, new_pos) > 1:
                c_ts = _get_ts(combat, cid)
                if c_ts.get("reaction_used"):
                    continue
                result = svc.resolve_melee_attack(
                    attacker_derived = companion.derived or {},
                    target_derived   = moving_enemy.get("derived", {}),
                )
                c_ts["reaction_used"] = True
                _save_ts(combat, cid, c_ts)

                if result.attack_roll["hit"]:
                    moving_enemy["hp_current"] = svc.apply_damage(
                        moving_enemy.get("hp_current", 0), result.damage,
                        moving_enemy.get("derived", {}).get("hp_max", 10),
                    )
                    state["enemies"]   = enemies
                    session.game_state = dict(state); flag_modified(session, "game_state")

                narration = svc._build_narration(
                    companion.name, moving_enemy["name"],
                    result.attack_roll, result.damage,
                )
                results.append({
                    "attacker": companion.name,
                    "target":   moving_enemy["name"],
                    "log": GameLog(
                        session_id  = session.id,
                        role        = f"companion_{companion.name}",
                        content     = f"⚔️ 借机攻击！{narration}",
                        log_type    = "combat",
                        dice_result = {
                            "attack": result.attack_roll,
                            "damage": result.damage,
                            "opportunity": True,
                        },
                    ),
                    "result": result.to_dict(),
                })

    return results


# ── Schemas ───────────────────────────────────────────────

class MoveRequest(BaseModel):
    entity_id: str
    to_x: int
    to_y: int


class ConditionRequest(BaseModel):
    entity_id:   str              # character_id 或 enemy["id"]
    condition:   str              # e.g. "poisoned"
    is_enemy:    bool = False     # True → 在 game_state.enemies 中查找
    rounds:      Optional[int] = None  # 持续回合数；None = 永久（需手动移除）


class CombatActionRequest(BaseModel):
    action_text: str = "普通攻击"
    target_id:   Optional[str] = None
    is_ranged:   bool = False
    is_offhand:  bool = False   # 副手攻击（附赠行动，需先完成主手攻击）


class DeathSaveRequest(BaseModel):
    character_id: str
    d20_value: Optional[int] = None  # Frontend 3D dice result


class SmiteRequest(BaseModel):
    slot_level:       int = 1           # 使用的法术位等级
    target_is_undead: bool = False      # 目标是否为亡灵/邪魔
    damage_values:    Optional[list[int]] = None  # 前端骰子物理结果
    target_id:        Optional[str] = None        # 斩击目标（前端传入）


class ClassFeatureRequest(BaseModel):
    feature_name: str                   # "second_wind" | "action_surge" | "rage" | "cunning_action_dash" | ...
    target_id:    Optional[str] = None  # 部分能力需要目标


class ReactionRequest(BaseModel):
    reaction_type: str      # "shield" | "uncanny_dodge" | "hellish_rebuke" | "opportunity_attack"
    target_id: Optional[str] = None  # For hellish_rebuke / opportunity_attack


class GrappleShoveRequest(BaseModel):
    action_type: str        # "grapple" | "shove"
    target_id: str
    shove_type: str = "prone"  # "prone" | "push" (only for shove)


class AttackRollRequest(BaseModel):
    entity_id:   str
    target_id:   str
    action_type: str = "melee"       # "melee" | "ranged"
    is_offhand:  bool = False
    d20_value:   Optional[int] = None  # Frontend 3D dice result


class DamageRollRequest(BaseModel):
    pending_attack_id: str
    damage_values: Optional[list[int]] = None  # Frontend 3D dice results [3, 5, 2]


class SpellRequest(BaseModel):
    caster_id:   str
    spell_name:  str
    spell_level: int = 1
    target_id:   Optional[str]       = None   # 单目标（向后兼容）
    target_ids:  Optional[list[str]] = None   # AoE 多目标列表


class SpellRollRequest(BaseModel):
    caster_id:   str
    spell_name:  str
    spell_level: int = 1
    target_id:   Optional[str]       = None
    target_ids:  Optional[list[str]] = None


class SpellConfirmRequest(BaseModel):
    pending_spell_id: str
    damage_values: Optional[list[int]] = None  # Frontend 3D spell dice results


class ManeuverRequest(BaseModel):
    maneuver_name: str
    target_id: str


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
    state         = session.game_state or {}
    enemies       = state.get("enemies", [])
    companion_ids = state.get("companion_ids", [])
    entities: dict = {}

    player = await db.get(Character, session.player_character_id)
    if player:
        entities[player.id] = entity_snapshot(player, is_enemy=False)

    for cid in companion_ids:
        c = await db.get(Character, cid)
        if c:
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


# ── 玩家战斗行动 ──────────────────────────────────────────

@router.post("/combat/{session_id}/action")
async def combat_action(
    session_id: str,
    req:        CombatActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    玩家战斗行动（攻击 / 闪避 / 冲刺 / 脱离接战 / 协助）。
    本端点不再自动推进回合——玩家需明确调用 /end-turn 结束回合。
    """
    action_text = req.action_text
    target_id   = req.target_id
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    await db.refresh(session)  # 确保读取最新 game_state
    player      = await db.get(Character, session.player_character_id)
    player_id   = session.player_character_id
    player_name = player.name if player else "你"
    state       = session.game_state or {}
    enemies     = list(state.get("enemies", []))

    # ── 获取并检查行动配额 ────────────────────────────────
    ts = _get_ts(combat, player_id)

    # ── 分支：冲刺 ───────────────────────────────────────
    if "冲刺" in action_text:
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"]  = True
        ts["movement_max"] = ts["movement_max"] * 2   # 30ft → 60ft = 12格
        _save_ts(combat, player_id, ts)
        db.add(GameLog(
            session_id=session_id, role="player",
            content=f"{player_name} 使用「冲刺」行动，本回合移动力翻倍！",
            log_type="combat",
        ))
        await db.commit()
        return {
            "action": "dash", "narration": f"{player_name} 使用「冲刺」，移动力翻倍！",
            "turn_state": ts, "combat_over": False, "outcome": None,
        }

    # ── 分支：脱离接战 ────────────────────────────────────
    if "脱离" in action_text or "disengage" in action_text.lower():
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"] = True
        ts["disengaged"]  = True
        _save_ts(combat, player_id, ts)
        db.add(GameLog(
            session_id=session_id, role="player",
            content=f"{player_name} 「脱离接战」，本回合移动不会触发借机攻击。",
            log_type="combat",
        ))
        await db.commit()
        return {
            "action": "disengage", "narration": f"{player_name} 脱离接战。",
            "turn_state": ts, "combat_over": False, "outcome": None,
        }

    # ── 分支：协助 ────────────────────────────────────────
    if "协助" in action_text or "help" in action_text.lower():
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"] = True
        _save_ts(combat, player_id, ts)

        # 给目标队友设置 being_helped
        helped_name = "队友"
        if target_id:
            t_ts = _get_ts(combat, target_id)
            t_ts["being_helped"] = True
            _save_ts(combat, target_id, t_ts)
            tchar = await db.get(Character, target_id)
            if tchar:
                helped_name = tchar.name
        else:
            # 自动选最低 HP 的队友
            companion_ids = state.get("companion_ids", [])
            best_cid, best_hp_pct = None, 1.1
            for cid in companion_ids:
                c = await db.get(Character, cid)
                if c and c.hp_current > 0:
                    pct = c.hp_current / max(1, (c.derived or {}).get("hp_max", 1))
                    if pct < best_hp_pct:
                        best_hp_pct = pct
                        best_cid = cid
                        helped_name = c.name
            if best_cid:
                t_ts = _get_ts(combat, best_cid)
                t_ts["being_helped"] = True
                _save_ts(combat, best_cid, t_ts)

        db.add(GameLog(
            session_id=session_id, role="player",
            content=f"{player_name} 「协助」{helped_name}，对方下次攻击具有优势！",
            log_type="combat",
        ))
        await db.commit()
        return {
            "action": "help", "narration": f"{player_name} 协助 {helped_name}。",
            "turn_state": ts, "combat_over": False, "outcome": None,
        }

    # ── 分支：闪避 ────────────────────────────────────────
    is_dodge = "闪避" in action_text or "dodge" in action_text.lower()
    if is_dodge:
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"] = True
        _save_ts(combat, player_id, ts)
        narration = f"{player_name} 采取了闪避姿态，专注于躲避攻击。"
        db.add(GameLog(session_id=session_id, role="player",
                       content=narration, log_type="combat"))
        await db.commit()
        return {
            "action": "dodge", "narration": narration,
            "turn_state": ts, "combat_over": False, "outcome": None,
        }

    # ── 分支：副手攻击（附赠行动，双武器战斗）─────────────
    is_offhand_attack = req.is_offhand or "副手" in action_text or "offhand" in action_text.lower()
    if is_offhand_attack:
        if not ts["action_used"]:
            raise HTTPException(400, "副手攻击需要先完成本回合的主手攻击")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        # 解析目标（与普通攻击相同逻辑）
        offhand_target_id    = req.target_id
        offhand_target_name  = ""
        offhand_target_deriv = {}
        offhand_target_enemy = False

        if offhand_target_id:
            otchar = await db.get(Character, offhand_target_id)
            if otchar:
                offhand_target_name, offhand_target_deriv, offhand_target_enemy = (
                    otchar.name, otchar.derived or {}, False
                )
            else:
                oenemy = next((e for e in enemies if e["id"] == offhand_target_id), None)
                if oenemy:
                    offhand_target_name, offhand_target_deriv, offhand_target_enemy = (
                        oenemy["name"], oenemy.get("derived", {}), True
                    )

        if not offhand_target_name:
            alive = [e for e in enemies if e.get("hp_current", 0) > 0]
            if alive:
                offhand_target_name  = alive[0]["name"]
                offhand_target_deriv = alive[0].get("derived", {})
                offhand_target_enemy = True
                offhand_target_id    = alive[0]["id"]

        if not offhand_target_name:
            raise HTTPException(400, "没有可攻击的目标")

        # 副手攻击：is_offhand=True 使伤害不加属性修正（除非有双武器战斗特技）
        offhand_result = svc.resolve_melee_attack(
            attacker_derived = player.derived or {} if player else {},
            target_derived   = offhand_target_deriv,
            is_offhand       = True,
        )

        offhand_conc_log  = None
        offhand_new_hp    = None
        if offhand_result.attack_roll["hit"]:
            if offhand_target_enemy:
                for e in enemies:
                    if e["id"] == offhand_target_id:
                        e["hp_current"] = svc.apply_damage(
                            e.get("hp_current", 0), offhand_result.damage,
                            e.get("derived", {}).get("hp_max", 10),
                        )
                        offhand_new_hp = e["hp_current"]
                state["enemies"]   = enemies
                session.game_state = dict(state); flag_modified(session, "game_state")
            else:
                otchar2 = await db.get(Character, offhand_target_id)
                if otchar2:
                    otchar2.hp_current = svc.apply_damage(
                        otchar2.hp_current, offhand_result.damage,
                        (otchar2.derived or {}).get("hp_max", otchar2.hp_current),
                    )
                    offhand_new_hp   = otchar2.hp_current
                    offhand_conc_log = await _do_concentration_check(
                        otchar2, offhand_result.damage, session_id
                    )

        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)

        offhand_narration = (
            f"【副手攻击】" +
            svc._build_narration(
                player_name, offhand_target_name,
                offhand_result.attack_roll, offhand_result.damage,
            )
        )
        db.add(GameLog(
            session_id  = session_id,
            role        = "player",
            content     = offhand_narration,
            log_type    = "combat",
            dice_result = {
                "attack": offhand_result.attack_roll,
                "damage": offhand_result.damage_roll,
                "offhand": True,
            },
        ))
        if offhand_conc_log:
            db.add(offhand_conc_log)

        offhand_over, offhand_outcome = svc.check_combat_over(
            enemies, (await db.get(Character, session.player_character_id)).hp_current
            if session.player_character_id else 0
        )
        if offhand_over:
            session.combat_active = False

        await db.commit()
        return {
            "action":              "offhand_attack",
            "narration":           offhand_narration,
            "attack_result":       offhand_result.attack_roll,
            "damage":              offhand_result.damage,
            "target_id":           offhand_target_id,
            "target_new_hp":       offhand_new_hp,
            "concentration_check": offhand_conc_log.dice_result if offhand_conc_log else None,
            "turn_state":          ts,
            "combat_over":         offhand_over,
            "outcome":             offhand_outcome,
        }

    # ── 分支：普通攻击 / 远程攻击（含 Extra Attack / Sneak Attack / Fighting Style / Damage Resistance）──
    p_derived   = player.derived or {} if player else {}
    p_class     = _normalize_class(player.char_class) if player else ""
    p_level     = player.level if player else 1

    # Extra Attack: 计算允许的攻击次数
    max_attacks = svc.get_attack_count(p_derived, p_level, p_class)
    ts.setdefault("attacks_made", 0)
    ts["attacks_max"] = max_attacks

    if ts["attacks_made"] >= max_attacks:
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽，请使用「结束回合」")
        raise HTTPException(400, "本回合攻击次数已达上限")

    # 解析目标
    target_derived     = {}
    target_name        = ""
    target_is_enemy    = False
    resolved_target_id = target_id

    if target_id:
        tchar = await db.get(Character, target_id)
        if tchar:
            target_name, target_derived, target_is_enemy = tchar.name, tchar.derived or {}, False
        else:
            enemy = next((e for e in enemies if e["id"] == target_id), None)
            if enemy:
                target_name, target_derived, target_is_enemy = enemy["name"], enemy.get("derived", {}), True

    if not target_name:
        alive = [e for e in enemies if e.get("hp_current", 0) > 0]
        if alive:
            target_name, target_derived, target_is_enemy = alive[0]["name"], alive[0].get("derived", {}), True
            resolved_target_id = alive[0]["id"]

    if not target_name:
        raise HTTPException(400, "没有可攻击的目标")

    # 状态条件对攻击的影响
    p_conditions = list(player.conditions or []) if player else []
    if target_is_enemy:
        t_enemy      = next((e for e in enemies if e["id"] == resolved_target_id), {})
        t_conditions = t_enemy.get("conditions", [])
    else:
        tchar2       = await db.get(Character, resolved_target_id) if resolved_target_id else None
        t_conditions = list(tchar2.conditions or []) if tchar2 else []

    atk_adv, atk_dis = svc.get_attack_modifiers(p_conditions)
    def_adv, def_dis = svc.get_defense_modifiers(t_conditions)

    # 「被协助」→ 攻击优势
    if ts.get("being_helped"):
        atk_adv = True
        ts["being_helped"] = False

    # 远程攻击：相邻敌人存在 → 劣势
    ranged_penalty = False
    cover_bonus = 0
    positions = dict(combat.entity_positions or {})
    if req.is_ranged:
        if _has_adjacent_enemy(player_id, enemies, positions):
            # Sharpshooter: ignore close-range disadvantage? No, that's Crossbow Expert.
            # Crossbow Expert feat negates adjacent enemy disadvantage
            has_crossbow_expert = p_derived.get("feat_effects", {}).get("Crossbow Expert", {}).get("crossbow_expert", False)
            if not has_crossbow_expert:
                atk_dis        = True
                ranged_penalty = True

    # ── Cover bonus (P0-8) ────────────────────────────────
    grid_data = dict(combat.grid_data or {})
    atk_pos = positions.get(str(player_id))
    tgt_pos = positions.get(str(resolved_target_id))
    if atk_pos and tgt_pos:
        cover_bonus = svc.get_cover_bonus(grid_data, atk_pos, tgt_pos)
        # Sharpshooter ignores half and three-quarters cover
        has_sharpshooter = bool(p_derived.get("feat_effects", {}).get("Sharpshooter"))
        if has_sharpshooter and req.is_ranged:
            cover_bonus = 0

    # ── GWM / Sharpshooter feat power attack (P1-2) ────────
    feat_power_attack = False
    feat_power_bonus_dmg = 0
    feat_power_hit_penalty = 0
    feat_effects = p_derived.get("feat_effects", {})

    # GWM: -5 hit / +10 damage with heavy melee weapons
    if not req.is_ranged and feat_effects.get("Great Weapon Master"):
        # Check if weapon has "heavy" property
        equipped_type = p_derived.get("equipped_weapon_type", "")
        if "heavy" in str(equipped_type).lower() or "two-handed" in str(equipped_type).lower():
            # Auto-apply if target AC is relatively low
            effective_ac = target_derived.get("ac", 13) + cover_bonus
            attack_bonus = p_derived.get("attack_bonus", 3)
            # Apply if we'd still have ~50% hit chance
            if attack_bonus - 5 + 10 >= effective_ac:
                feat_power_attack = True
                feat_power_hit_penalty = 5
                feat_power_bonus_dmg = 10

    # Sharpshooter: -5 hit / +10 damage with ranged weapons
    if req.is_ranged and feat_effects.get("Sharpshooter"):
        effective_ac = target_derived.get("ac", 13) + cover_bonus
        attack_bonus = p_derived.get("ranged_attack_bonus", 3)
        if attack_bonus - 5 + 10 >= effective_ac:
            feat_power_attack = True
            feat_power_hit_penalty = 5
            feat_power_bonus_dmg = 10

    # Apply cover bonus to target AC for this attack
    attack_target_derived = dict(target_derived)
    if cover_bonus > 0:
        attack_target_derived["ac"] = target_derived.get("ac", 10) + cover_bonus

    # Apply feat hit penalty to attacker
    attack_attacker_derived = dict(p_derived)
    if feat_power_attack:
        bonus_key = "ranged_attack_bonus" if req.is_ranged else "attack_bonus"
        attack_attacker_derived[bonus_key] = p_derived.get(bonus_key, 3) - feat_power_hit_penalty

    # 狂暴攻击优势（鲁莽攻击，简化）
    class_res = player.class_resources or {} if player else {}
    is_raging = class_res.get("raging", False)

    # ── Assassinate: first round, advantage vs targets that haven't acted ──
    assassinate_active = False
    p_sub_effects = p_derived.get("subclass_effects", {})
    if p_sub_effects.get("assassinate") and combat.round_number == 1:
        # Check if target hasn't acted yet (its turn_order index > current_turn_index)
        turn_order = list(combat.turn_order or [])
        target_turn_idx = next((i for i, t in enumerate(turn_order) if t.get("character_id") == resolved_target_id), None)
        if target_turn_idx is not None and target_turn_idx >= combat.current_turn_index:
            atk_adv = True
            assassinate_active = True

    attack_result_obj = svc.resolve_melee_attack(
        attacker_derived = attack_attacker_derived,
        target_derived   = attack_target_derived,
        advantage        = atk_adv or def_adv,
        disadvantage     = atk_dis or def_dis,
        is_ranged        = req.is_ranged,
    )
    attack_result_dict = attack_result_obj.attack_roll
    damage             = attack_result_obj.damage
    damage_roll        = attack_result_obj.damage_roll

    # Assassinate auto-crit: if assassinate is active and hit, force crit
    if assassinate_active and attack_result_dict["hit"] and not attack_result_dict["is_crit"]:
        attack_result_dict["is_crit"] = True
        # Add extra crit damage (one extra die)
        hit_die = p_derived.get("hit_die", 8)
        extra_crit = roll_dice(f"1d{hit_die}")
        damage += extra_crit["total"]
        extra_damage_notes.append(f"暗杀暴击+{extra_crit['total']}")
    extra_damage_notes = []

    # ── GWM / Sharpshooter +10 damage ──
    if attack_result_dict["hit"] and feat_power_attack:
        damage += feat_power_bonus_dmg
        feat_name = "巨武器大师" if not req.is_ranged else "神射手"
        extra_damage_notes.append(f"{feat_name}+{feat_power_bonus_dmg}")

    # ── Fighting Style: Dueling bonus ──
    if attack_result_dict["hit"] and not req.is_ranged:
        melee_bonus = p_derived.get("melee_damage_bonus", 0)
        if melee_bonus > 0:
            damage += melee_bonus
            extra_damage_notes.append(f"决斗+{melee_bonus}")

    # ── Rage bonus damage ──
    if attack_result_dict["hit"] and is_raging and not req.is_ranged:
        rage_bonus = svc.get_rage_bonus(p_level)
        damage += rage_bonus
        extra_damage_notes.append(f"狂暴+{rage_bonus}")

    # ── Zealot Divine Fury (first hit per turn while raging) ──
    if attack_result_dict["hit"] and is_raging and p_sub_effects.get("divine_fury") and ts.get("attacks_made", 0) <= 1:
        fury_roll = roll_dice(f"1d6+{p_level // 2}")
        damage += fury_roll["total"]
        extra_damage_notes.append(f"神圣狂怒+{fury_roll['total']}")

    # ── Sneak Attack ──
    sneak_attack_applied = False
    sneak_attack_damage  = 0
    if attack_result_dict["hit"] and p_class == "Rogue":
        has_adv = atk_adv or def_adv
        # Check ally adjacent to target
        companion_ids = state.get("companion_ids", [])
        ally_list = [{"id": session.player_character_id, "hp_current": player.hp_current if player else 0}]
        for cid in companion_ids:
            c = await db.get(Character, cid)
            if c:
                ally_list.append({"id": c.id, "hp_current": c.hp_current})
        ally_adj = _has_ally_adjacent_to(resolved_target_id, player_id, ally_list, positions)

        # Swashbuckler: check if no other enemy is adjacent to target
        is_swashbuckler = p_sub_effects.get("swashbuckler", False)
        no_other_enemy_adj = False
        if is_swashbuckler:
            other_enemies_adj = [e for e in enemies if e["id"] != resolved_target_id and e.get("hp_current", 0) > 0]
            no_other_enemy_adj = not _has_ally_adjacent_to(player_id, resolved_target_id, other_enemies_adj, positions)

        if svc.check_sneak_attack(p_class, has_adv, ally_adj, swashbuckler=is_swashbuckler, no_other_enemy_adjacent=no_other_enemy_adj) and ts.get("attacks_made", 0) == 0:
            # Sneak attack only once per turn
            sa_dice = svc.calc_sneak_attack_dice(p_level)
            sa_roll = roll_dice(f"{sa_dice}d6")
            sneak_attack_damage = sa_roll["total"]
            damage += sneak_attack_damage
            sneak_attack_applied = True
            extra_damage_notes.append(f"偷袭{sa_dice}d6={sneak_attack_damage}")

    # ── Damage Resistance ──
    damage_type = p_derived.get("damage_type", "钝击")
    if attack_result_dict["hit"] and target_is_enemy:
        t_enemy_data = next((e for e in enemies if e["id"] == resolved_target_id), {})
        resistances    = t_enemy_data.get("resistances", [])
        immunities     = t_enemy_data.get("immunities", [])
        vulnerabilities = t_enemy_data.get("vulnerabilities", [])
        damage = svc.apply_damage_with_resistance(damage, damage_type, resistances, immunities, vulnerabilities)

    mechanical_narration = svc._build_narration(player_name, target_name, attack_result_dict, damage)
    if ranged_penalty:
        mechanical_narration = f"（相邻敌人，远程劣势）{mechanical_narration}"
    if extra_damage_notes:
        mechanical_narration += f"（{', '.join(extra_damage_notes)}）"

    # LLM vivid narration for old-path attack
    vivid = await narrate_action(
        actor_name=player_name, actor_class=_normalize_class(player.char_class),
        target_name=target_name, action_type="attack",
        hit=attack_result_dict["hit"], is_crit=attack_result_dict["is_crit"],
        is_fumble=attack_result_dict["is_fumble"], damage=damage,
        damage_type=p_derived.get("damage_type", ""),
        extra_details=", ".join(extra_damage_notes) if extra_damage_notes else "",
    )
    narration = vivid if vivid else mechanical_narration

    # 更新 HP
    conc_log      = None
    target_new_hp = None
    if attack_result_dict["hit"]:
        if target_is_enemy:
            for e in enemies:
                if e["id"] == resolved_target_id:
                    e["hp_current"] = svc.apply_damage(e.get("hp_current", 0), damage, e.get("derived", {}).get("hp_max", 10))
                    target_new_hp   = e["hp_current"]
            state["enemies"]   = enemies
            session.game_state = dict(state); flag_modified(session, "game_state")
        else:
            tchar3 = await db.get(Character, resolved_target_id)
            if tchar3:
                tchar3.hp_current = svc.apply_damage(tchar3.hp_current, damage, (tchar3.derived or {}).get("hp_max", tchar3.hp_current))
                target_new_hp     = tchar3.hp_current
                conc_log          = await _do_concentration_check(tchar3, damage, session_id)

    # ── Dark One's Blessing: Warlock gains temp HP on kill ──
    if target_new_hp is not None and target_new_hp <= 0 and target_is_enemy:
        if p_sub_effects.get("dark_ones_blessing"):
            cha_mod_val = p_derived.get("ability_modifiers", {}).get("cha", 0)
            temp_hp = cha_mod_val + p_level
            extra_damage_notes.append(f"黑暗祝福+{temp_hp}临时HP")

    # 更新攻击计数
    ts["attacks_made"] = ts.get("attacks_made", 0) + 1
    if ts["attacks_made"] >= max_attacks:
        ts["action_used"] = True
    _save_ts(combat, player_id, ts)

    # Extra Attack 提示
    attacks_remaining = max_attacks - ts["attacks_made"]

    db.add(GameLog(
        session_id  = session_id,
        role        = "player",
        content     = narration,
        log_type    = "combat",
        dice_result = {
            "attack": attack_result_dict, "damage": damage_roll,
            "sneak_attack": sneak_attack_damage if sneak_attack_applied else None,
            "extra_damage": extra_damage_notes if extra_damage_notes else None,
        },
    ))
    if conc_log:
        db.add(conc_log)

    # 检查战斗是否结束（不推进回合）
    player_check         = await db.get(Character, session.player_character_id)
    combat_over, outcome = svc.check_combat_over(enemies, player_check.hp_current if player_check else 0)
    if combat_over:
        session.combat_active = False
        # 清理战斗状态记录，防止下次战斗残留旧数据
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs: await db.delete(_old_cs)
        except Exception: pass

    await db.commit()
    return {
        "action":               "attack",
        "narration":            narration,
        "attack_result":        attack_result_dict,
        "damage":               damage,
        "target_id":            resolved_target_id,
        "target_new_hp":        target_new_hp,
        "ranged_penalty":       ranged_penalty,
        "cover_bonus":          cover_bonus,
        "feat_power_attack":    feat_power_attack,
        "sneak_attack":         sneak_attack_applied,
        "sneak_attack_damage":  sneak_attack_damage,
        "extra_damage_notes":   extra_damage_notes,
        "attacks_made":         ts["attacks_made"],
        "attacks_max":          max_attacks,
        "attacks_remaining":    attacks_remaining,
        "concentration_check":  conc_log.dice_result if conc_log else None,
        "turn_state":           ts,
        "next_turn_index":      combat.current_turn_index,
        "round_number":         combat.round_number,
        "combat_over":          combat_over,
        "outcome":              outcome,
    }


# ── 攻击检定（仅 d20，不掷伤害）──────────────────────────────

@router.post("/combat/{session_id}/attack-roll")
async def attack_roll(
    session_id: str,
    req:        AttackRollRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    两步攻击流程 Step 1：仅掷 d20 攻击检定，判定命中/未中/暴击/大失手。
    不掷伤害骰、不扣 HP。结果暂存到 turn_states.pending_attack 供 /damage-roll 使用。
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    await db.refresh(session)
    player    = await db.get(Character, req.entity_id)
    if not player:
        raise HTTPException(404, "攻击者不存在")
    player_id   = req.entity_id
    player_name = player.name
    state       = session.game_state or {}
    enemies     = list(state.get("enemies", []))

    # ── 行动配额检查 ──
    ts = _get_ts(combat, player_id)

    p_derived = player.derived or {}
    p_class   = _normalize_class(player.char_class)
    p_level   = player.level

    # Extra Attack
    max_attacks = svc.get_attack_count(p_derived, p_level, p_class)
    ts.setdefault("attacks_made", 0)
    ts["attacks_max"] = max_attacks

    if ts["attacks_made"] >= max_attacks:
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽，请使用「结束回合」")
        raise HTTPException(400, "本回合攻击次数已达上限")

    # ── 副手攻击检查 ──
    is_offhand = req.is_offhand
    if is_offhand:
        if not ts["action_used"]:
            raise HTTPException(400, "副手攻击需要先完成本回合的主手攻击")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

    # ── 解析目标 ──
    target_derived     = {}
    target_name        = ""
    target_is_enemy    = False
    resolved_target_id = req.target_id

    tchar = await db.get(Character, req.target_id)
    if tchar:
        target_name, target_derived, target_is_enemy = tchar.name, tchar.derived or {}, False
    else:
        enemy = next((e for e in enemies if e["id"] == req.target_id), None)
        if enemy:
            target_name, target_derived, target_is_enemy = enemy["name"], enemy.get("derived", {}), True

    if not target_name:
        raise HTTPException(400, "目标不存在")

    # ── 距离检查 ──
    positions = dict(combat.entity_positions or {})
    atk_pos   = positions.get(str(player_id))
    tgt_pos   = positions.get(str(resolved_target_id))
    is_ranged = req.action_type == 'ranged'
    in_range, dist, range_err = _check_attack_range(atk_pos, tgt_pos, is_ranged)
    if not in_range:
        raise HTTPException(400, range_err)

    # ── 攻击修正 ──
    is_ranged = req.action_type == "ranged"
    p_conditions = list(player.conditions or [])
    if target_is_enemy:
        t_enemy      = next((e for e in enemies if e["id"] == resolved_target_id), {})
        t_conditions = t_enemy.get("conditions", [])
    else:
        tchar2       = await db.get(Character, resolved_target_id) if resolved_target_id else None
        t_conditions = list(tchar2.conditions or []) if tchar2 else []

    atk_adv, atk_dis = svc.get_attack_modifiers(p_conditions)
    def_adv, def_dis = svc.get_defense_modifiers(t_conditions)

    if ts.get("being_helped"):
        atk_adv = True
        ts["being_helped"] = False

    ranged_penalty = False
    positions = dict(combat.entity_positions or {})
    if is_ranged:
        has_crossbow_expert = p_derived.get("feat_effects", {}).get("Crossbow Expert", {}).get("crossbow_expert", False)
        if _has_adjacent_enemy(player_id, enemies, positions) and not has_crossbow_expert:
            atk_dis        = True
            ranged_penalty = True

    # Cover
    grid_data = dict(combat.grid_data or {})
    atk_pos = positions.get(str(player_id))
    tgt_pos = positions.get(str(resolved_target_id))
    cover_bonus = 0
    if atk_pos and tgt_pos:
        cover_bonus = svc.get_cover_bonus(grid_data, atk_pos, tgt_pos)
        has_sharpshooter = bool(p_derived.get("feat_effects", {}).get("Sharpshooter"))
        if has_sharpshooter and is_ranged:
            cover_bonus = 0

    # GWM / Sharpshooter power attack
    feat_power_attack = False
    feat_power_hit_penalty = 0
    feat_power_bonus_dmg = 0
    feat_effects = p_derived.get("feat_effects", {})

    if not is_ranged and feat_effects.get("Great Weapon Master"):
        equipped_type = p_derived.get("equipped_weapon_type", "")
        if "heavy" in str(equipped_type).lower() or "two-handed" in str(equipped_type).lower():
            effective_ac = target_derived.get("ac", 13) + cover_bonus
            attack_bonus = p_derived.get("attack_bonus", 3)
            if attack_bonus - 5 + 10 >= effective_ac:
                feat_power_attack = True
                feat_power_hit_penalty = 5
                feat_power_bonus_dmg = 10

    if is_ranged and feat_effects.get("Sharpshooter"):
        effective_ac = target_derived.get("ac", 13) + cover_bonus
        attack_bonus = p_derived.get("ranged_attack_bonus", 3)
        if attack_bonus - 5 + 10 >= effective_ac:
            feat_power_attack = True
            feat_power_hit_penalty = 5
            feat_power_bonus_dmg = 10

    # Build modified derived dicts for the roll
    attack_target_derived = dict(target_derived)
    if cover_bonus > 0:
        attack_target_derived["ac"] = target_derived.get("ac", 10) + cover_bonus

    attack_attacker_derived = dict(p_derived)
    if feat_power_attack:
        bonus_key = "ranged_attack_bonus" if is_ranged else "attack_bonus"
        attack_attacker_derived[bonus_key] = p_derived.get(bonus_key, 3) - feat_power_hit_penalty

    # Rage reckless attack (simplified)
    class_res = player.class_resources or {}
    is_raging = class_res.get("raging", False)

    # ── Roll ONLY d20 (via roll_attack from dnd_rules) ──
    crit_threshold = attack_attacker_derived.get("crit_threshold", 20)
    from services.dnd_rules import roll_attack as _roll_attack
    final_adv = atk_adv or def_adv
    final_dis = atk_dis or def_dis
    attack_roll_result = _roll_attack(
        attacker  = {"derived": attack_attacker_derived},
        target    = {"derived": attack_target_derived},
        is_ranged = is_ranged,
        advantage = final_adv,
        disadvantage = final_dis,
        crit_threshold = crit_threshold,
    )

    # Frontend dice override: use 3D physics result instead of server roll
    if req.d20_value is not None:
        d20_ov = req.d20_value
        atk_bonus_ov = attack_roll_result["attack_bonus"]
        new_total_ov = d20_ov + atk_bonus_ov
        target_ac_ov = attack_roll_result["target_ac"]
        is_crit_ov = d20_ov >= crit_threshold
        is_fumble_ov = d20_ov == 1
        hit_ov = (not is_fumble_ov) and (is_crit_ov or new_total_ov >= target_ac_ov)
        attack_roll_result = {
            **attack_roll_result,
            "d20": d20_ov,
            "attack_total": new_total_ov,
            "hit": hit_ov,
            "is_crit": is_crit_ov,
            "is_fumble": is_fumble_ov,
        }

    # ── Compute damage dice expression (使用装备武器的 damage_dice) ──
    equipment = player.equipment or {}
    equipped_weapons = equipment.get("weapons", [])
    weapon_damage = None
    weapon_hit_die = p_derived.get("hit_die", 8)
    if equipped_weapons:
        # 使用第一把装备的武器（equipped=true 优先）
        equipped = next((w for w in equipped_weapons if w.get("equipped")), equipped_weapons[0] if equipped_weapons else None)
        if equipped:
            weapon_damage = equipped.get("damage", f"1d{weapon_hit_die}")
    hit_die = weapon_hit_die  # fallback for crit calculation
    mods    = p_derived.get("ability_modifiers", {})
    raw_mod = mods.get("dex", 0) if is_ranged else mods.get("str", 0)
    if is_offhand and not p_derived.get("two_weapon_fighting", False):
        dmg_mod = 0
    else:
        dmg_mod = raw_mod
    if weapon_damage:
        # 装备武器: "1d8" + modifier
        damage_dice = f"{weapon_damage}+{dmg_mod}" if dmg_mod >= 0 else f"{weapon_damage}{dmg_mod}"
    else:
        # 无武器: 使用 hit_die (徒手 1d4 or fallback)
        damage_dice = f"1d{hit_die}+{dmg_mod}" if dmg_mod >= 0 else f"1d{hit_die}{dmg_mod}"

    # ── Generate a pending_attack_id and store in turn_states ──
    pending_id = str(uuid.uuid4())
    pending_attack = {
        "pending_attack_id": pending_id,
        "attacker_id":       player_id,
        "target_id":         resolved_target_id,
        "target_name":       target_name,
        "target_is_enemy":   target_is_enemy,
        "attacker_name":     player_name,
        "attack_roll":       attack_roll_result,
        "is_ranged":         is_ranged,
        "is_offhand":        is_offhand,
        "is_crit":           attack_roll_result["is_crit"],
        "hit":               attack_roll_result["hit"],
        "cover_bonus":       cover_bonus,
        "ranged_penalty":    ranged_penalty,
        "feat_power_attack": feat_power_attack,
        "feat_power_bonus_dmg": feat_power_bonus_dmg,
        "advantage":         final_adv,
        "disadvantage":      final_dis,
        "is_raging":         is_raging,
        "damage_dice":       damage_dice,
        "hit_die":           hit_die,
        "dmg_mod":           dmg_mod,
    }

    # Increment attack count
    ts["attacks_made"] = ts.get("attacks_made", 0) + 1
    if ts["attacks_made"] >= max_attacks:
        ts["action_used"] = True
    if is_offhand:
        ts["bonus_action_used"] = True

    ts["pending_attack"] = pending_attack
    _save_ts(combat, player_id, ts)

    # Generate vivid narration for miss / fumble (hit narration done in damage-roll)
    miss_narration = ""
    if not attack_roll_result["hit"]:
        vivid = await narrate_action(
            actor_name=player_name, actor_class=p_class, target_name=target_name,
            action_type="attack", hit=False,
            is_fumble=attack_roll_result["is_fumble"],
        )
        if vivid:
            miss_narration = vivid
        else:
            miss_narration = svc._build_narration(player_name, target_name, attack_roll_result, 0)
        # Log miss
        db.add(GameLog(
            session_id=session_id, role="player",
            content=miss_narration, log_type="combat",
            dice_result={"attack": attack_roll_result},
        ))

    await db.commit()

    return {
        "d20":              attack_roll_result["d20"],
        "attack_bonus":     attack_roll_result["attack_bonus"],
        "attack_total":     attack_roll_result["attack_total"],
        "target_ac":        attack_roll_result["target_ac"],
        "hit":              attack_roll_result["hit"],
        "is_crit":          attack_roll_result["is_crit"],
        "is_fumble":        attack_roll_result["is_fumble"],
        "cover_bonus":      cover_bonus,
        "advantage":        final_adv,
        "disadvantage":     final_dis,
        "target_name":      target_name,
        "attacker_name":    player_name,
        "attacks_made":     ts["attacks_made"],
        "attacks_max":      max_attacks,
        "damage_dice":      damage_dice,
        "pending_attack_id": pending_id,
        "turn_state":       ts,
        "narration":        miss_narration,
    }


# ── 伤害骰（读取 pending_attack，掷伤害，扣 HP）──────────────

@router.post("/combat/{session_id}/damage-roll")
async def damage_roll(
    session_id: str,
    req:        DamageRollRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    两步攻击流程 Step 2：掷伤害骰，应用伤害/偷袭/狂暴/专长/抗性，扣 HP。
    必须在 /attack-roll 命中后调用。
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    await db.refresh(session)
    state   = session.game_state or {}
    enemies = list(state.get("enemies", []))

    # ── 读取暂存的 pending_attack ──
    # Scan all turn_states to find the matching pending_attack
    all_ts = dict(combat.turn_states or {})
    attacker_entity_id = None
    pending = None
    for eid, ets in all_ts.items():
        pa = ets.get("pending_attack")
        if pa and pa.get("pending_attack_id") == req.pending_attack_id:
            pending = pa
            attacker_entity_id = eid
            break

    if not pending:
        raise HTTPException(404, "未找到待处理的攻击检定，可能已过期或 ID 错误")

    if not pending["hit"]:
        # Miss — just clean up pending and return
        ts = _get_ts(combat, attacker_entity_id)
        ts.pop("pending_attack", None)
        _save_ts(combat, attacker_entity_id, ts)
        await db.commit()
        raise HTTPException(400, "该攻击未命中，无法掷伤害骰")

    player = await db.get(Character, attacker_entity_id)
    if not player:
        raise HTTPException(404, "攻击者角色不存在")

    p_derived = player.derived or {}
    p_class   = _normalize_class(player.char_class)
    p_level   = player.level
    player_name = player.name

    target_id       = pending["target_id"]
    target_name     = pending["target_name"]
    target_is_enemy = pending["target_is_enemy"]
    is_crit         = pending["is_crit"]
    is_ranged       = pending["is_ranged"]
    is_offhand      = pending["is_offhand"]
    hit_die         = pending["hit_die"]
    dmg_mod         = pending["dmg_mod"]
    attack_roll_result = pending["attack_roll"]

    # ── Roll damage ──
    damage_dice_expr = f"1d{hit_die}+{dmg_mod}" if dmg_mod >= 0 else f"1d{hit_die}{dmg_mod}"
    damage_roll_result = roll_dice(damage_dice_expr)
    damage = damage_roll_result["total"]
    damage_rolls = damage_roll_result.get("rolls", [])

    # Frontend dice override: use 3D physics results
    if req.damage_values:
        damage_rolls = req.damage_values
        damage_roll_result["rolls"] = req.damage_values
        damage_roll_result["total"] = sum(req.damage_values) + dmg_mod
        damage = damage_roll_result["total"]

    # Crit: double dice
    crit_extra = 0
    if is_crit:
        extra = roll_dice(f"1d{hit_die}")
        crit_extra = extra["total"]
        damage += crit_extra

    extra_damage_notes = []

    # GWM / Sharpshooter +10
    feat_power_bonus_dmg = pending.get("feat_power_bonus_dmg", 0)
    if pending.get("feat_power_attack") and feat_power_bonus_dmg > 0:
        damage += feat_power_bonus_dmg
        feat_name = "巨武器大师" if not is_ranged else "神射手"
        extra_damage_notes.append(f"{feat_name}+{feat_power_bonus_dmg}")

    # Fighting Style: Dueling bonus
    dueling_bonus = 0
    if not is_ranged:
        melee_bonus = p_derived.get("melee_damage_bonus", 0)
        if melee_bonus > 0:
            damage += melee_bonus
            dueling_bonus = melee_bonus
            extra_damage_notes.append(f"决斗+{melee_bonus}")

    # Rage bonus
    rage_bonus = 0
    if pending.get("is_raging") and not is_ranged:
        rage_bonus = svc.get_rage_bonus(p_level)
        damage += rage_bonus
        extra_damage_notes.append(f"狂暴+{rage_bonus}")

    # Zealot Divine Fury (first hit per turn while raging)
    p_sub_effects = p_derived.get("subclass_effects", {})
    if pending.get("is_raging") and p_sub_effects.get("divine_fury"):
        ts_check_fury = _get_ts(combat, attacker_entity_id)
        if ts_check_fury.get("attacks_made", 1) <= 1:
            fury_roll = roll_dice(f"1d6+{p_level // 2}")
            damage += fury_roll["total"]
            extra_damage_notes.append(f"神圣狂怒+{fury_roll['total']}")

    # Sneak Attack
    sneak_attack_applied = False
    sneak_attack_damage  = 0
    sneak_attack_dice    = ""
    if p_class == "Rogue":
        positions = dict(combat.entity_positions or {})
        has_adv = pending.get("advantage", False)
        companion_ids = state.get("companion_ids", [])
        ally_list = [{"id": session.player_character_id, "hp_current": player.hp_current}]
        for cid in companion_ids:
            c = await db.get(Character, cid)
            if c:
                ally_list.append({"id": c.id, "hp_current": c.hp_current})
        ally_adj = _has_ally_adjacent_to(target_id, attacker_entity_id, ally_list, positions)

        # Swashbuckler: check if no other enemy is adjacent to attacker
        is_swashbuckler = p_sub_effects.get("swashbuckler", False)
        no_other_enemy_adj = False
        if is_swashbuckler:
            other_enemies_adj = [e for e in enemies if e["id"] != target_id and e.get("hp_current", 0) > 0]
            no_other_enemy_adj = not _has_ally_adjacent_to(attacker_entity_id, target_id, other_enemies_adj, positions)

        # Sneak attack only once per turn — check by looking at ts
        ts_check = _get_ts(combat, attacker_entity_id)
        attacks_before = ts_check.get("attacks_made", 1) - 1  # was incremented in attack-roll
        if svc.check_sneak_attack(p_class, has_adv, ally_adj, swashbuckler=is_swashbuckler, no_other_enemy_adjacent=no_other_enemy_adj) and attacks_before == 0:
            sa_dice_count = svc.calc_sneak_attack_dice(p_level)
            sa_roll = roll_dice(f"{sa_dice_count}d6")
            sneak_attack_damage = sa_roll["total"]
            sneak_attack_dice = f"{sa_dice_count}d6"
            damage += sneak_attack_damage
            sneak_attack_applied = True
            extra_damage_notes.append(f"偷袭{sa_dice_count}d6={sneak_attack_damage}")

    # Damage Resistance
    damage_type = p_derived.get("damage_type", "钝击")
    if target_is_enemy:
        t_enemy_data = next((e for e in enemies if e["id"] == target_id), {})
        resistances    = t_enemy_data.get("resistances", [])
        immunities     = t_enemy_data.get("immunities", [])
        vulnerabilities = t_enemy_data.get("vulnerabilities", [])
        damage = svc.apply_damage_with_resistance(damage, damage_type, resistances, immunities, vulnerabilities)

    total_damage = damage

    # Build narration (mechanical fallback)
    mechanical_narration = svc._build_narration(player_name, target_name, attack_roll_result, total_damage)
    if pending.get("ranged_penalty"):
        mechanical_narration = f"（相邻敌人，远程劣势）{mechanical_narration}"
    if extra_damage_notes:
        mechanical_narration += f"（{', '.join(extra_damage_notes)}）"

    # LLM vivid narration (async, fallback to mechanical)
    damage_type = p_derived.get("damage_type", "")
    vivid = await narrate_action(
        actor_name=player_name, actor_class=p_class, target_name=target_name,
        action_type="attack", hit=True, is_crit=is_crit,
        damage=total_damage, damage_type=damage_type,
        extra_details=", ".join(extra_damage_notes) if extra_damage_notes else "",
    )
    narration = vivid if vivid else mechanical_narration

    # ── Apply HP ──
    conc_log      = None
    target_new_hp = None
    if target_is_enemy:
        for e in enemies:
            if e["id"] == target_id:
                e["hp_current"] = svc.apply_damage(
                    e.get("hp_current", 0), total_damage,
                    e.get("derived", {}).get("hp_max", 10),
                )
                target_new_hp = e["hp_current"]
        state["enemies"]   = enemies
        session.game_state = dict(state)
        flag_modified(session, "game_state")
    else:
        tchar = await db.get(Character, target_id)
        if tchar:
            tchar.hp_current = svc.apply_damage(
                tchar.hp_current, total_damage,
                (tchar.derived or {}).get("hp_max", tchar.hp_current),
            )
            target_new_hp = tchar.hp_current
            conc_log = await _do_concentration_check(tchar, total_damage, session_id)

    # ── Dark One's Blessing: Warlock gains temp HP on kill ──
    if target_new_hp is not None and target_new_hp <= 0 and target_is_enemy:
        if p_sub_effects.get("dark_ones_blessing"):
            cha_mod_val = p_derived.get("ability_modifiers", {}).get("cha", 0)
            temp_hp = cha_mod_val + p_level
            extra_damage_notes.append(f"黑暗祝福+{temp_hp}临时HP")

    # ── Clear pending_attack ──
    ts = _get_ts(combat, attacker_entity_id)
    ts.pop("pending_attack", None)
    _save_ts(combat, attacker_entity_id, ts)

    # ── GameLog ──
    db.add(GameLog(
        session_id  = session_id,
        role        = "player",
        content     = narration,
        log_type    = "combat",
        dice_result = {
            "attack": attack_roll_result,
            "damage": damage_roll_result,
            "sneak_attack": sneak_attack_damage if sneak_attack_applied else None,
            "extra_damage": extra_damage_notes if extra_damage_notes else None,
        },
    ))
    if conc_log:
        db.add(conc_log)

    # ── Check combat over ──
    player_check         = await db.get(Character, session.player_character_id)
    combat_over, outcome = svc.check_combat_over(enemies, player_check.hp_current if player_check else 0)
    if combat_over:
        session.combat_active = False
        # 清理战斗状态记录，防止下次战斗残留旧数据
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs: await db.delete(_old_cs)
        except Exception: pass

    await db.commit()

    # Check if paladin can smite
    can_smite = p_class in ("Paladin",) and not combat_over

    return {
        "damage_dice":          damage_dice_expr,
        "damage_rolls":         damage_rolls,
        "damage_modifier":      dmg_mod,
        "damage_total":         damage_roll_result["total"],
        "crit_extra":           crit_extra,
        "damage_type":          damage_type,
        "sneak_attack_dice":    sneak_attack_dice if sneak_attack_applied else None,
        "sneak_attack_damage":  sneak_attack_damage if sneak_attack_applied else 0,
        "dueling_bonus":        dueling_bonus,
        "rage_bonus":           rage_bonus,
        "feat_bonus":           feat_power_bonus_dmg,
        "extra_damage_notes":   extra_damage_notes,
        "total_damage":         total_damage,
        "target_new_hp":        target_new_hp,
        "target_id":            target_id,
        "target_name":          target_name,
        "narration":            narration,
        "combat_over":          combat_over,
        "outcome":              outcome,
        "can_smite":            can_smite,
        "concentration_check":  conc_log.dice_result if conc_log else None,
        "turn_state":           ts,
    }


# ── 结束玩家回合（明确���进回合）────────────────────────────

@router.post("/combat/{session_id}/end-turn")
async def end_player_turn(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    玩家明确结束回合。
    - 对当前实体执行条件倒计时
    - 推进 current_turn_index
    - 重置下一实体的回合状态
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    turn_order = combat.turn_order or []
    current    = turn_order[combat.current_turn_index] if turn_order else {}

    # ── 当前实体条件倒计时 ────────────────────────────────
    tick_logs = []
    if current.get("is_player"):
        player = await db.get(Character, session.player_character_id)
        if player:
            removed = _tick_conditions_char(player)
            for c in removed:
                tick_logs.append(GameLog(
                    session_id=session_id, role="system",
                    content=f"[{player.name}] 的【{c}】状态到期解除",
                    log_type="system",
                ))

    # ── 推进回合 ──────────────────────────────────────────
    next_index = (combat.current_turn_index + 1) % max(len(turn_order), 1)
    combat.current_turn_index = next_index
    if next_index == 0:
        combat.round_number += 1

    # ── 重置下一实体的回合状态（根据角色实际数据）────────
    if turn_order:
        next_entity_id = turn_order[next_index]["character_id"]
        next_atk_max, next_move_max = await _calc_entity_turn_limits(db, session, next_entity_id)
        _reset_ts(combat, next_entity_id, attacks_max=next_atk_max, movement_max=next_move_max)

    # ── 检查战斗结束 ──────────────────────────────────────
    state   = session.game_state or {}
    enemies = list(state.get("enemies", []))
    player_check         = await db.get(Character, session.player_character_id)
    combat_over, outcome = svc.check_combat_over(enemies, player_check.hp_current if player_check else 0)
    if combat_over:
        session.combat_active = False
        # 清理战斗状态记录，防止下次战斗残留旧数据
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs: await db.delete(_old_cs)
        except Exception: pass

    for tl in tick_logs:
        db.add(tl)
    await db.commit()
    return {
        "next_turn_index":    next_index,
        "round_number":       combat.round_number,
        "expired_conditions": [tl.content for tl in tick_logs],
        "combat_over":        combat_over,
        "outcome":            outcome,
    }


# ── 反应 (Reaction System, P0-6) ─────────────────────────

@router.post("/combat/{session_id}/reaction")
async def use_reaction(
    session_id: str,
    req: ReactionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Player uses reaction during enemy turn.
    reaction_type: "shield" | "uncanny_dodge" | "hellish_rebuke" | "opportunity_attack"
    Called by frontend when enemy attacks player and player has reaction available.
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    player = await db.get(Character, session.player_character_id)
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    player_id = session.player_character_id
    ts = _get_ts(combat, player_id)
    if ts.get("reaction_used"):
        raise HTTPException(400, "本回合反应已用尽")

    p_class = _normalize_class(player.char_class)
    p_level = player.level
    derived = player.derived or {}
    state = session.game_state or {}
    enemies = list(state.get("enemies", []))
    narration = ""
    reaction_effect = {}
    reaction_target_name = ""

    if req.reaction_type == "shield":
        # Shield spell: AC+5 until next turn, costs 1st level slot
        known = set(player.known_spells or []) | set(player.prepared_spells or [])
        if "Shield" not in known and "shield" not in known:
            raise HTTPException(400, "你没有学会「护盾术」")
        slots = dict(player.spell_slots or {})
        if slots.get("1st", 0) <= 0:
            raise HTTPException(400, "没有可用的1环法术位")
        slots["1st"] -= 1
        player.spell_slots = slots

        ts["reaction_used"] = True
        _save_ts(combat, player_id, ts)

        # Temporarily boost AC (tracked in conditions until next turn)
        conditions = list(player.conditions or [])
        if "shield_spell" not in conditions:
            conditions.append("shield_spell")
        player.conditions = conditions
        durations = dict(player.condition_durations or {})
        durations["shield_spell"] = 1  # Expires at start of next turn
        player.condition_durations = durations

        old_ac = derived.get("ac", 10)
        new_ac = old_ac + 5
        narration = f"🛡️ {player.name} 用反应施放「护盾术」！AC {old_ac} → {new_ac}（持续至下回合）"
        reaction_effect = {"ac_bonus": 5, "new_ac": new_ac, "slot_used": "1st"}

    elif req.reaction_type == "uncanny_dodge":
        # Rogue 5+: halve incoming damage
        if p_class != "Rogue":
            raise HTTPException(400, "只有游荡者可以使用灵巧闪避")
        if p_level < 5:
            raise HTTPException(400, "需要游荡者5级以上才能使用灵巧闪避")

        ts["reaction_used"] = True
        _save_ts(combat, player_id, ts)

        # Mark for damage halving (frontend applies before confirming damage)
        narration = f"⚡ {player.name} 使用「灵巧闪避」！本次受到的伤害减半！"
        reaction_effect = {"damage_halved": True}

    elif req.reaction_type == "hellish_rebuke":
        # Tiefling racial / Warlock: deal 2d10 fire damage to attacker
        slots = dict(player.spell_slots or {})
        if slots.get("1st", 0) <= 0:
            raise HTTPException(400, "没有可用的1环法术位")
        slots["1st"] -= 1
        player.spell_slots = slots

        ts["reaction_used"] = True
        _save_ts(combat, player_id, ts)

        rebuke_roll = roll_dice("2d10")
        rebuke_damage = rebuke_roll["total"]

        # Apply damage to the attacking enemy
        target_name = "攻击者"
        if req.target_id:
            for e in enemies:
                if e["id"] == req.target_id and e.get("hp_current", 0) > 0:
                    e["hp_current"] = svc.apply_damage(
                        e["hp_current"], rebuke_damage,
                        e.get("derived", {}).get("hp_max", 10),
                    )
                    target_name = e["name"]
            state["enemies"] = enemies
            session.game_state = dict(state); flag_modified(session, "game_state")

        reaction_target_name = target_name
        narration = f"🔥 {player.name} 使用「地狱斥责」！2d10={rebuke_damage} 火焰伤害反击 {target_name}！"
        reaction_effect = {"damage_dealt": rebuke_damage, "target": target_name}

    else:
        raise HTTPException(400, f"未知反应类型：{req.reaction_type}")

    # LLM vivid narration for reactions
    vivid = await narrate_action(
        actor_name=player.name, actor_class=p_class,
        target_name=reaction_target_name,
        action_type="reaction",
        extra_details=narration,
    )
    if vivid:
        narration = vivid

    db.add(GameLog(
        session_id=session_id, role="player",
        content=narration, log_type="combat",
        dice_result={"type": "reaction", "reaction_type": req.reaction_type, **reaction_effect},
    ))
    await db.commit()

    # 反应骰子动画
    reaction_dice = None
    if req.reaction_type == "hellish_rebuke":
        reaction_dice = {"faces": 10, "result": reaction_effect.get("damage_dealt", 0), "label": "地狱斥责 2d10", "count": 2}

    return {
        "action": "reaction",
        "reaction_type": req.reaction_type,
        "narration": narration,
        "turn_state": ts,
        "reaction_effect": reaction_effect,
        "dice_roll": reaction_dice,
    }


# ── 擒抱/推撞 (Grapple/Shove, P1-4) ────────────────────────

@router.post("/combat/{session_id}/grapple-shove")
async def grapple_shove(
    session_id: str,
    req: GrappleShoveRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Grapple or Shove action. Replaces one attack.
    Grapple: contested Athletics check, success → target grappled (speed=0)
    Shove: contested Athletics check, success → target prone or pushed 5ft
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    player = await db.get(Character, session.player_character_id)
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    player_id = session.player_character_id
    ts = _get_ts(combat, player_id)

    # Uses one attack (or the action if no attacks remain)
    max_attacks = svc.get_attack_count(player.derived or {}, player.level, _normalize_class(player.char_class))
    ts.setdefault("attacks_made", 0)
    ts["attacks_max"] = max_attacks
    if ts["attacks_made"] >= max_attacks:
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        raise HTTPException(400, "本回合攻击次数已达上限")

    state = session.game_state or {}
    enemies = list(state.get("enemies", []))

    # Get target
    target_name = ""
    target_derived = {}
    target_is_enemy = False
    target_skills = []

    tchar = await db.get(Character, req.target_id)
    if tchar:
        target_name = tchar.name
        target_derived = tchar.derived or {}
        target_skills = tchar.proficient_skills or []
    else:
        enemy = next((e for e in enemies if e["id"] == req.target_id), None)
        if enemy:
            target_name = enemy["name"]
            target_derived = enemy.get("derived", {})
            target_is_enemy = True

    if not target_name:
        raise HTTPException(404, "目标不存在")

    p_derived = player.derived or {}
    p_skills = player.proficient_skills or []

    if req.action_type == "grapple":
        result = svc.resolve_grapple(p_derived, target_derived, p_skills, target_skills)
        if result["success"]:
            # Apply grappled condition
            if target_is_enemy:
                for e in enemies:
                    if e["id"] == req.target_id:
                        conds = list(e.get("conditions", []))
                        if "grappled" not in conds:
                            conds.append("grappled")
                        e["conditions"] = conds
                state["enemies"] = enemies
                session.game_state = dict(state); flag_modified(session, "game_state")
            else:
                conds = list(tchar.conditions or [])
                if "grappled" not in conds:
                    conds.append("grappled")
                tchar.conditions = conds

            narration = f"🤼 {player.name} 成功擒抱 {target_name}！{target_name} 速度降为0！"
        else:
            narration = f"🤼 {player.name} 尝试擒抱 {target_name}，但失败了！"

    elif req.action_type == "shove":
        result = svc.resolve_shove(p_derived, target_derived, p_skills, target_skills, req.shove_type)
        if result["success"]:
            if req.shove_type == "prone":
                if target_is_enemy:
                    for e in enemies:
                        if e["id"] == req.target_id:
                            conds = list(e.get("conditions", []))
                            if "prone" not in conds:
                                conds.append("prone")
                            e["conditions"] = conds
                    state["enemies"] = enemies
                    session.game_state = dict(state); flag_modified(session, "game_state")
                else:
                    conds = list(tchar.conditions or [])
                    if "prone" not in conds:
                        conds.append("prone")
                    tchar.conditions = conds
                narration = f"💥 {player.name} 成功推倒 {target_name}！{target_name} 陷入倒地状态！"
            else:
                # Push 5ft away
                positions = dict(combat.entity_positions or {})
                p_pos = positions.get(str(player_id))
                t_pos = positions.get(str(req.target_id))
                if p_pos and t_pos:
                    dx = t_pos["x"] - p_pos["x"]
                    dy = t_pos["y"] - p_pos["y"]
                    # Normalize direction and push 1 tile
                    push_x = t_pos["x"] + (1 if dx > 0 else (-1 if dx < 0 else 0))
                    push_y = t_pos["y"] + (1 if dy > 0 else (-1 if dy < 0 else 0))
                    push_x = max(0, min(19, push_x))
                    push_y = max(0, min(11, push_y))
                    positions[str(req.target_id)] = {"x": push_x, "y": push_y}
                    combat.entity_positions = positions; flag_modified(combat, "entity_positions")
                narration = f"💥 {player.name} 推开 {target_name}！{target_name} 被推后5英尺！"
        else:
            narration = f"💥 {player.name} 尝试推撞 {target_name}，但失败了！"
    else:
        raise HTTPException(400, f"未知动作类型：{req.action_type}")

    # Count as one attack
    ts["attacks_made"] = ts.get("attacks_made", 0) + 1
    if ts["attacks_made"] >= max_attacks:
        ts["action_used"] = True
    _save_ts(combat, player_id, ts)

    # LLM vivid narration for grapple/shove
    vivid = await narrate_action(
        actor_name=player.name, actor_class=_normalize_class(player.char_class),
        target_name=target_name, action_type=req.action_type,
        hit=result["success"],
    )
    if vivid:
        narration = vivid

    db.add(GameLog(
        session_id=session_id, role="player",
        content=narration, log_type="combat",
        dice_result={
            "type": req.action_type,
            "success": result["success"],
            "attacker_roll": result["attacker_roll"],
            "target_roll": result["target_roll"],
        },
    ))
    await db.commit()

    return {
        "action": req.action_type,
        "success": result["success"],
        "narration": narration,
        "attacker_roll": result["attacker_roll"],
        "target_roll": result["target_roll"],
        "turn_state": ts,
        "combat_over": False,
        "outcome": None,
    }


# ── 神圣斩击 (Divine Smite) ───────────────────────────────

@router.post("/combat/{session_id}/smite")
async def divine_smite(
    session_id: str,
    req: SmiteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Paladin Divine Smite -- 成功命中后追加辐光伤害。
    前端在攻击命中后弹出选择，玩家决定消耗法术位。
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    player = await db.get(Character, session.player_character_id)
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    p_class = _normalize_class(player.char_class)
    if p_class != "Paladin":
        raise HTTPException(400, "只有圣武士可以使用神圣斩击")

    # 消耗法术位
    slot_key = ["1st", "2nd", "3rd", "4th", "5th"][min(req.slot_level - 1, 4)]
    current_slots = dict(player.spell_slots or {})
    available = current_slots.get(slot_key, 0)
    if available <= 0:
        raise HTTPException(400, f"没有可用的{slot_key}环法术位")
    current_slots[slot_key] = available - 1
    player.spell_slots = current_slots

    # 计算斩击伤害
    smite = svc.calc_divine_smite_damage(req.slot_level, req.target_is_undead)

    # 前端骰子物理结果覆盖
    if req.damage_values:
        smite["damage"] = sum(req.damage_values)

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()

    state   = session.game_state or {}
    enemies = list(state.get("enemies", []))

    # 确定斩击目标：优先用前端传入的 target_id
    smite_target_id = req.target_id
    if not smite_target_id:
        # Fallback：从 pending_attack 或最近日志推断
        if combat:
            all_ts = dict(combat.turn_states or {})
            player_ts = all_ts.get(str(session.player_character_id), {})
            smite_target_id = player_ts.get("last_attack_target")
        if not smite_target_id:
            # 最后兜底：第一个存活敌人
            for e in enemies:
                if e.get("hp_current", 0) > 0:
                    smite_target_id = e["id"]
                    break

    # 对目标施加伤害
    target_new_hp = None
    target_name   = "目标"
    smite_applied = False
    for e in enemies:
        if str(e.get("id")) != str(smite_target_id):
            continue
        if e.get("hp_current", 0) <= 0:
            continue
        e["hp_current"] = svc.apply_damage(
            e.get("hp_current", 0), smite["damage"],
            e.get("derived", {}).get("hp_max", 10),
        )
        target_new_hp = e["hp_current"]
        target_name   = e["name"]
        smite_applied = True
        break

    if not smite_applied:
        current_slots[slot_key] = available
        player.spell_slots = current_slots
        raise HTTPException(400, "没有可施加斩击的目标")

    state["enemies"]   = enemies
    session.game_state = dict(state); flag_modified(session, "game_state")

    undead_note = "（对亡灵/邪魔额外+1d8）" if req.target_is_undead else ""
    mechanical_narration = f"✨ {player.name} 释放神圣斩击！{smite['dice']}辐光伤害{undead_note}，对 {target_name} 造成 {smite['damage']} 点伤害！"

    vivid = await narrate_action(
        actor_name=player.name, actor_class=_normalize_class(player.char_class),
        target_name=target_name, action_type="smite",
        damage=smite["damage"], damage_type="辐光",
    )
    narration = vivid if vivid else mechanical_narration

    db.add(GameLog(
        session_id  = session_id,
        role        = "player",
        content     = narration,
        log_type    = "combat",
        dice_result = {"type": "divine_smite", "slot_level": req.slot_level, **smite},
    ))

    player_check         = await db.get(Character, session.player_character_id)
    combat_over, outcome = svc.check_combat_over(enemies, player_check.hp_current if player_check else 0)
    if combat_over:
        session.combat_active = False
        # 清理战斗状态记录，防止下次战斗残留旧数据
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs: await db.delete(_old_cs)
        except Exception: pass

    await db.commit()
    return {
        "action":          "divine_smite",
        "narration":       narration,
        "smite_damage":    smite["damage"],
        "smite_dice":      smite["dice"],
        "target_name":     target_name,
        "target_new_hp":   target_new_hp,
        "remaining_slots": current_slots,
        "combat_over":     combat_over,
        "outcome":         outcome,
    }


# ── 职业特性 (Class Features) ─────────────────────────────

@router.post("/combat/{session_id}/class-feature")
async def use_class_feature(
    session_id: str,
    req: ClassFeatureRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    使用职业战斗特性：
    - second_wind:  Fighter 1+, 恢复 1d10+level HP, 附赠行动, 每短休1次
    - action_surge: Fighter 2+, 本回合获得额外行动, 每短休1次
    - rage:         Barbarian 1+, 进入/退出狂暴, 附赠行动
    - cunning_action_dash: Rogue 2+, 附赠行动冲刺
    - cunning_action_disengage: Rogue 2+, 附赠行动脱离
    - cunning_action_hide: Rogue 2+, 附赠行动隐匿
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    player = await db.get(Character, session.player_character_id)
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    player_id = session.player_character_id
    ts = _get_ts(combat, player_id)
    p_class = _normalize_class(player.char_class)
    p_level = player.level
    derived = player.derived or {}
    class_res = dict(player.class_resources or {})

    feature = req.feature_name
    narration = ""
    dice_roll = None  # {faces, result, label} for frontend dice animation

    # ── Second Wind (Fighter) ─────────────────────────────
    if feature == "second_wind":
        if p_class != "Fighter":
            raise HTTPException(400, "只有战士可以使用活力恢复")
        if class_res.get("second_wind_used", False):
            raise HTTPException(400, "本次休息后已使用过活力恢复")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        heal_roll = roll_dice(f"1d10+{p_level}")
        heal_amt  = heal_roll["total"]
        hp_max    = derived.get("hp_max", player.hp_current)
        old_hp    = player.hp_current
        player.hp_current = min(hp_max, player.hp_current + heal_amt)

        class_res["second_wind_used"] = True
        player.class_resources = class_res
        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)

        narration = f"🛡️ {player.name} 使用「活力恢复」！1d10+{p_level}={heal_amt}，恢复 {player.hp_current - old_hp} HP（{player.hp_current}/{hp_max}）"
        dice_roll = {"faces": 10, "result": heal_amt, "label": f"活力恢复 1d10+{p_level}"}

    # ── Action Surge (Fighter) ────────────────────────────
    elif feature == "action_surge":
        if p_class != "Fighter":
            raise HTTPException(400, "只有战士可以使用行动奔涌")
        if p_level < 2:
            raise HTTPException(400, "需要战士2级以上才能使用行动奔涌")
        if class_res.get("action_surge_used", False):
            raise HTTPException(400, "本次休息后已使用过行动奔涌")

        class_res["action_surge_used"] = True
        player.class_resources = class_res
        # 重置行动配额（不重置移动力和附赠行动）
        ts["action_used"]  = False
        ts["attacks_made"]  = 0
        _save_ts(combat, player_id, ts)

        narration = f"⚡ {player.name} 使用「行动奔涌」！本回合获得额外一次完整行动！"

    # ── Rage (Barbarian) ──────────────────────────────────
    elif feature == "rage":
        if p_class != "Barbarian":
            raise HTTPException(400, "只有野蛮人可以使用狂暴")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        is_raging = class_res.get("raging", False)
        if is_raging:
            # 退出狂暴
            class_res["raging"] = False
            player.class_resources = class_res
            # 移除 rage 给的伤害抗性条件
            conditions = list(player.conditions or [])
            player.conditions = [c for c in conditions if c != "raging"]
            narration = f"😤 {player.name} 停止了狂暴。"
        else:
            # 进入狂暴
            rage_remaining = class_res.get("rage_remaining", svc.get_rage_uses(p_level))
            if rage_remaining <= 0:
                raise HTTPException(400, "狂暴次数已用尽（长休后恢复）")
            class_res["raging"] = True
            class_res["rage_remaining"] = rage_remaining - 1
            player.class_resources = class_res
            ts["bonus_action_used"] = True
            _save_ts(combat, player_id, ts)
            rage_bonus = svc.get_rage_bonus(p_level)
            narration = f"🔥 {player.name} 进入狂暴！近战伤害+{rage_bonus}，物理伤害抗性！（剩余{rage_remaining - 1}次）"

    # ── Cunning Action — Dash (Rogue) ─────────────────────
    elif feature == "cunning_action_dash":
        if p_class != "Rogue":
            raise HTTPException(400, "只有游荡者可以使用灵巧动作")
        if p_level < 2:
            raise HTTPException(400, "需要游荡者2级以上才能使用灵巧动作")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        ts["bonus_action_used"] = True
        ts["movement_max"]      = ts["movement_max"] * 2
        _save_ts(combat, player_id, ts)
        narration = f"💨 {player.name} 使用「灵巧动作-冲刺」！移动力翻倍！"

    # ── Cunning Action — Disengage (Rogue) ────────────────
    elif feature == "cunning_action_disengage":
        if p_class != "Rogue":
            raise HTTPException(400, "只有游荡者可以使用灵巧动作")
        if p_level < 2:
            raise HTTPException(400, "需要游荡者2级以上才能使用灵巧动作")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        ts["bonus_action_used"] = True
        ts["disengaged"]        = True
        _save_ts(combat, player_id, ts)
        narration = f"💨 {player.name} 使用「灵巧动作-脱离」！本回合移动不触发借机攻击。"

    # ── Cunning Action — Hide (Rogue) ─────────────────────
    elif feature == "cunning_action_hide":
        if p_class != "Rogue":
            raise HTTPException(400, "只有游荡者可以使用灵巧动作")
        if p_level < 2:
            raise HTTPException(400, "需要游荡者2级以上才能使用灵巧动作")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)
        # 添加隐匿条件（攻击时获得优势）
        conditions = list(player.conditions or [])
        if "hidden" not in conditions:
            conditions.append("hidden")
            player.conditions = conditions
        narration = f"🫥 {player.name} 使用「灵巧动作-隐匿」！下次攻击获得优势！"

    # ── Fighting Spirit (Samurai Fighter) ────────────────
    elif feature == "fighting_spirit":
        if not (p_class == "Fighter"):
            raise HTTPException(400, "非战士无法使用战意")
        fs_rem = class_res.get("fighting_spirit_remaining", 0)
        if fs_rem <= 0:
            raise HTTPException(400, "战意次数已用完")
        class_res["fighting_spirit_remaining"] = fs_rem - 1
        # Grant advantage on all attacks this turn + temp HP = fighter level
        ts["fighting_spirit_active"] = True
        _save_ts(combat, player_id, ts)
        player.class_resources = class_res
        narration = f"⚔️ {player.name} 集中精神，燃起不屈的战意！本回合所有攻击获得优势，获得 {player.level} 点临时生命值。"

    # ── Bardic Inspiration (Bard) ─────────────────────────
    elif feature == "bardic_inspiration":
        if not (p_class == "Bard"):
            raise HTTPException(400, "非吟游诗人无法使用灵感骰")
        bi_rem = class_res.get("bardic_inspiration_remaining", 0)
        if bi_rem <= 0:
            raise HTTPException(400, "灵感骰次数已用完")
        class_res["bardic_inspiration_remaining"] = bi_rem - 1
        derived = player.derived or {}
        die = derived.get("subclass_effects", {}).get("inspiration_die", "d6")
        bi_faces = int(die.replace("d", "")) if die.startswith("d") else 6
        bi_roll = roll_dice(die)
        player.class_resources = class_res
        narration = f"🎵 {player.name} 演奏了一段鼓舞人心的旋律！一名盟友获得 {die} 灵感骰（{bi_roll['rolls'][0]}）。"
        dice_roll = {"faces": bi_faces, "result": bi_roll["rolls"][0], "label": f"灵感骰 {die}"}

    # ── Ki: Flurry of Blows (Monk, 1 ki) ─────────────────
    elif feature == "ki_flurry":
        if not (p_class == "Monk"):
            raise HTTPException(400, "非武僧无法使用疾风连击")
        ki = class_res.get("ki_remaining", 0)
        if ki < 1:
            raise HTTPException(400, "气不足")
        class_res["ki_remaining"] = ki - 1
        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)
        # Roll 2 unarmed attacks
        d = player.derived or {}
        atk_mod = d.get("attack_bonus", 2)
        martial_die = "1d4" if player.level < 5 else ("1d6" if player.level < 11 else ("1d8" if player.level < 17 else "1d10"))
        results = []
        for i in range(2):
            atk = roll_dice("1d20")
            hit_total = atk["rolls"][0] + atk_mod
            results.append(f"攻击{i+1}: d20={atk['rolls'][0]}+{atk_mod}={hit_total}")
        player.class_resources = class_res
        narration = f"👊 {player.name} 以气驱动疾风连击！{' | '.join(results)}"
        dice_roll = {"faces": 20, "result": roll_dice("1d20")["rolls"][0], "label": "疾风连击"}

    # ── Ki: Stunning Strike (Monk, 1 ki) ──────────────────
    elif feature == "ki_stunning_strike":
        if not (p_class == "Monk"):
            raise HTTPException(400, "非武僧无法使用震慑打击")
        ki = class_res.get("ki_remaining", 0)
        if ki < 1:
            raise HTTPException(400, "气不足")
        class_res["ki_remaining"] = ki - 1
        player.class_resources = class_res
        ki_dc = 8 + derived.get("proficiency_bonus", 2) + derived.get("ability_modifiers", {}).get("wis", 0)
        narration = f"💥 {player.name} 将气灌注于一击之中！目标必须进行 DC{ki_dc} 体质豁免，失败则被震慑至你的下一回合结束。"
        dice_roll = {"faces": 20, "result": ki_dc, "label": f"震慑打击 DC{ki_dc}"}

    # ── Shadow Step (Shadow Monk, 2 ki) ───────────────────
    elif feature == "shadow_step":
        if not (p_class == "Monk"):
            raise HTTPException(400, "非武僧无法使用暗影步")
        ki = class_res.get("ki_remaining", 0)
        if ki < 2:
            raise HTTPException(400, "气不足（需要2点）")
        class_res["ki_remaining"] = ki - 2
        player.class_resources = class_res
        narration = f"🌑 {player.name} 融入阴影之中，瞬间出现在另一片黑暗处！下一次近战攻击获得优势。"
        dice_roll = {"faces": 20, "result": roll_dice("1d20")["rolls"][0], "label": "暗影步"}

    # ── Channel Divinity (Paladin) ────────────────────────
    elif feature == "channel_divinity":
        if not (p_class == "Paladin"):
            raise HTTPException(400, "非圣武士无法引导神力")
        if class_res.get("channel_divinity_used"):
            raise HTTPException(400, "引导神力已使用（每次短休恢复）")
        class_res["channel_divinity_used"] = True
        sub_effects = (player.derived or {}).get("subclass_effects", {})
        if sub_effects.get("devotion"):
            narration = f"✨ {player.name} 引导神力——神圣武器！武器散发圣光，攻击加上魅力修正，持续1分钟。"
        elif sub_effects.get("vengeance"):
            narration = f"⚔️ {player.name} 引导神力——仇敌誓约！标记一个目标，对其攻击获得优势，持续1分钟。"
            ts["vow_of_enmity_active"] = True
            _save_ts(combat, player_id, ts)
        elif sub_effects.get("ancients"):
            narration = f"🌿 {player.name} 引导神力——自然之怒！藤蔓缠绕目标使其束缚！"
        elif sub_effects.get("glory"):
            narration = f"🌟 {player.name} 引导神力——鼓舞冲锋！30尺内盟友移动速度+10尺，持续10分钟。"
        else:
            narration = f"✨ {player.name} 引导神力！"
        player.class_resources = class_res

    # ── Lay on Hands (Paladin) ────────────────────────────
    elif feature == "lay_on_hands":
        if not (p_class == "Paladin"):
            raise HTTPException(400, "非圣武士无法使用圣手")
        pool = class_res.get("lay_on_hands_remaining", 0)
        if pool <= 0:
            raise HTTPException(400, "圣手治疗池已耗尽")
        # Heal 5 HP (or remaining pool, whichever is less)
        heal_amount = min(5, pool)
        class_res["lay_on_hands_remaining"] = pool - heal_amount
        hp_max = (player.derived or {}).get("hp_max", player.hp_current)
        player.hp_current = min(hp_max, player.hp_current + heal_amount)
        player.class_resources = class_res
        narration = f"🤲 {player.name} 将圣光注入伤口，恢复了 {heal_amount} 点生命值！（剩余治疗池: {pool - heal_amount}）"
        dice_roll = {"faces": 20, "result": heal_amount, "label": f"圣手治疗 +{heal_amount}HP"}

    # ── War Priest Attack (War Cleric) ────────────────────
    elif feature == "war_priest_attack":
        if not (p_class == "Cleric"):
            raise HTTPException(400, "非牧师无法使用战争牧师")
        wp_rem = class_res.get("war_priest_remaining", 0)
        if wp_rem <= 0:
            raise HTTPException(400, "战争牧师额外攻击次数已用完")
        class_res["war_priest_remaining"] = wp_rem - 1
        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)
        player.class_resources = class_res
        narration = f"⚔️ {player.name} 以战神之名发动额外攻击！本回合可用附赠动作进行一次武器攻击。"

    # ── Destructive Wrath (Tempest Cleric) ────────────────
    elif feature == "destructive_wrath":
        if not (p_class == "Cleric"):
            raise HTTPException(400, "非牧师无法使用毁灭之怒")
        if class_res.get("channel_divinity_used"):
            raise HTTPException(400, "引导神力已使用")
        class_res["channel_divinity_used"] = True
        ts["destructive_wrath_active"] = True
        _save_ts(combat, player_id, ts)
        player.class_resources = class_res
        narration = f"⚡ {player.name} 引导神力——毁灭之怒！下一次闪电或雷鸣伤害将自动取最大值！"

    # ── Wild Shape (Moon Druid) ───────────────────────────
    elif feature == "wild_shape":
        if not (p_class == "Druid"):
            raise HTTPException(400, "非德鲁伊无法使用野性形态")
        ws_rem = class_res.get("wild_shape_remaining", 0)
        if ws_rem <= 0:
            raise HTTPException(400, "野性形态次数已用完")
        class_res["wild_shape_remaining"] = ws_rem - 1
        sub_effects = (player.derived or {}).get("subclass_effects", {})
        max_cr = sub_effects.get("wild_shape_max_cr", 0.25)
        # Default to Bear form
        from services.dnd_rules import WILD_SHAPE_FORMS
        form_name = "Bear" if max_cr >= 1 else "Wolf"
        form = WILD_SHAPE_FORMS.get(form_name, {})
        class_res["wild_shape_active"] = form_name
        class_res["wild_shape_hp"] = form.get("hp", 20)
        player.class_resources = class_res
        narration = f"🐻 {player.name} 的身体扭曲变化，化身为{form_name}！获得 {form.get('hp',20)} 点额外生命值，AC {form.get('ac',12)}。"
        dice_roll = {"faces": 20, "result": form.get("hp", 20), "label": f"野性形态·{form_name}"}

    # ── Symbiotic Entity (Spores Druid) ───────────────────
    elif feature == "symbiotic_entity":
        if not (p_class == "Druid"):
            raise HTTPException(400, "非德鲁伊无法激活共生实体")
        ws_rem = class_res.get("wild_shape_remaining", 0)
        if ws_rem <= 0:
            raise HTTPException(400, "需要消耗一次野性形态")
        class_res["wild_shape_remaining"] = ws_rem - 1
        temp_hp = (player.derived or {}).get("subclass_effects", {}).get("symbiotic_temp_hp", 4 * player.level)
        class_res["symbiotic_entity_active"] = True
        player.class_resources = class_res
        narration = f"🍄 {player.name} 激活共生实体！孢子覆盖全身，获得 {temp_hp} 点临时生命值，近战附加毒素伤害。"
        dice_roll = {"faces": 20, "result": temp_hp, "label": f"共生实体 +{temp_hp}临时HP"}

    # ── Tides of Chaos (Wild Magic Sorcerer) ──────────────
    elif feature == "tides_of_chaos":
        if not (p_class == "Sorcerer"):
            raise HTTPException(400, "非术士无法使用混沌之潮")
        if class_res.get("tides_of_chaos_used"):
            raise HTTPException(400, "混沌之潮已使用（每次长休恢复）")
        class_res["tides_of_chaos_used"] = True
        ts["tides_of_chaos_active"] = True  # Next d20 roll gets advantage
        _save_ts(combat, player_id, ts)
        player.class_resources = class_res
        narration = f"🌀 {player.name} 引导体内不稳定的魔法能量！下一次攻击/检定/豁免获得优势。但这可能触发野蛮魔法涌动..."

    # ── Portent (Divination Wizard) ───────────────────────
    elif feature == "portent":
        if not (p_class == "Wizard"):
            raise HTTPException(400, "非法师无法使用预言骰")
        p_rem = class_res.get("portent_remaining", 0)
        if p_rem <= 0:
            raise HTTPException(400, "预言骰已用完（每次长休恢复）")
        class_res["portent_remaining"] = p_rem - 1
        portent_roll = roll_dice("1d20")
        class_res["portent_value"] = portent_roll["rolls"][0]
        player.class_resources = class_res
        narration = f"🔮 {player.name} 预见了命运的走向——预言骰: {portent_roll['rolls'][0]}！可以用此值替换任意一次d20检定。"
        dice_roll = {"faces": 20, "result": portent_roll["rolls"][0], "label": "预言骰"}

    else:
        raise HTTPException(400, f"未知职业特性：{feature}")

    # LLM vivid narration for class features
    vivid = await narrate_action(
        actor_name=player.name, actor_class=p_class,
        target_name="",
        action_type="class_feature",
        extra_details=narration,
    )
    if vivid:
        narration = vivid

    db.add(GameLog(
        session_id  = session_id,
        role        = "player",
        content     = narration,
        log_type    = "combat",
        dice_result = {"type": "class_feature", "feature": feature},
    ))
    await db.commit()

    return {
        "action":          "class_feature",
        "feature":         feature,
        "narration":       narration,
        "turn_state":      ts,
        "class_resources": class_res,
        "hp_current":      player.hp_current,
        "hp_max":          derived.get("hp_max", player.hp_current),
        "dice_roll":       dice_roll,
    }


# ── AI 回合 ───────────────────────────────────────────────

@router.post("/combat/{session_id}/ai-turn")
async def ai_combat_turn(session_id: str, db: AsyncSession = Depends(get_db)):
    """处理当前 AI 实体的回合（队友或敌人）"""
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    turn_order = combat.turn_order or []
    if not turn_order:
        raise HTTPException(400, "先攻顺序为空")

    current    = turn_order[combat.current_turn_index]
    if current.get("is_player"):
        raise HTTPException(400, "当前是玩家回合，请使用 /action 接口")

    actor_id   = current.get("character_id", "")
    actor_name = current.get("name", "未知")
    state      = session.game_state or {}
    enemies    = list(state.get("enemies", []))
    is_enemy   = actor_id in [e["id"] for e in enemies]

    # ── 回合开始：重置施动者回合状态 ────────────────────────
    ai_atk_max, ai_move_max = await _calc_entity_turn_limits(db, session, actor_id)
    _reset_ts(combat, actor_id, attacks_max=ai_atk_max, movement_max=ai_move_max)

    # ── 获取施动者数据 ─────────────────────────────────────
    actor_derived = {}
    actor_hp      = 1
    ai_tick_logs  = []
    e     = None  # 敌人实体引用（供回合结束条件tick使用）
    achar = None  # 队友实体引用（供回合结束条件tick使用）
    if is_enemy:
        e = next((x for x in enemies if x["id"] == actor_id), None)
        if e:
            actor_derived = e.get("derived", {})
            actor_hp      = e.get("hp_current", 0)
    else:
        achar = await db.get(Character, actor_id)
        if achar:
            actor_derived = achar.derived or {}
            actor_hp      = achar.hp_current

    # 已死亡：跳过
    if actor_hp <= 0:
        next_index = (combat.current_turn_index + 1) % max(len(turn_order), 1)
        combat.current_turn_index = next_index
        if next_index == 0:
            combat.round_number += 1
        if turn_order:
            _ne = turn_order[next_index]["character_id"]
            _na, _nm = await _calc_entity_turn_limits(db, session, _ne)
            _reset_ts(combat, _ne, attacks_max=_na, movement_max=_nm)
        await db.commit()
        return {
            "actor_name": actor_name, "narration": f"{actor_name} 已倒下，跳过回合。",
            "attack_result": {}, "damage": 0, "target_id": None, "target_new_hp": None,
            "next_turn_index": next_index, "round_number": combat.round_number,
            "combat_over": False, "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        }

    # ── 计算下一回合索引（多处提前返回需要使用）────────────
    next_index = (combat.current_turn_index + 1) % max(len(turn_order), 1)

    # ── AI 决策：选择目标和行动 ─────────────────────────────
    from services.ai_combat_agent import get_ai_decision, calc_difficulty

    player = await db.get(Character, session.player_character_id)
    companions_alive = []
    for cid in state.get("companion_ids", []):
        c = await db.get(Character, cid)
        if c and c.hp_current > 0:
            companions_alive.append({
                "id": c.id, "name": c.name, "char_class": c.char_class, "level": c.level,
                "hp_current": c.hp_current, "hp_max": (c.derived or {}).get("hp_max", c.hp_current),
                "ac": (c.derived or {}).get("ac", 10), "derived": c.derived or {},
                "conditions": c.conditions or [], "concentration": c.concentration,
                "known_spells": c.known_spells or [], "cantrips": c.cantrips or [],
                "spell_slots": c.spell_slots or {}, "is_player": c.is_player,
                "equipment": c.equipment or {},
            })

    enemies_alive = [e for e in enemies if e.get("hp_current", 0) > 0]

    # 构建角色快照列表（玩家+队友）
    all_characters = []
    if player and player.hp_current > 0:
        all_characters.append({
            "id": player.id, "name": player.name, "char_class": player.char_class, "level": player.level,
            "hp_current": player.hp_current, "hp_max": (player.derived or {}).get("hp_max", player.hp_current),
            "ac": (player.derived or {}).get("ac", 10), "derived": player.derived or {},
            "conditions": player.conditions or [], "concentration": player.concentration,
            "is_player": True,
        })
    all_characters.extend(companions_alive)

    # 构建行动者数据
    actor_full = dict(actor_derived)
    actor_full["id"] = actor_id
    actor_full["name"] = actor_name
    if is_enemy and e:
        actor_full.update({
            "hp_current": e.get("hp_current", 0), "hp_max": e.get("hp_max", e.get("derived", {}).get("hp_max", 10)),
            "ac": e.get("ac", e.get("derived", {}).get("ac", 10)),
            "actions": e.get("actions", []), "speed": e.get("speed", 30),
            "tactics": e.get("tactics", ""), "type": e.get("type", ""),
        })
    elif achar:
        actor_full.update({
            "hp_current": achar.hp_current, "hp_max": (achar.derived or {}).get("hp_max", achar.hp_current),
            "ac": (achar.derived or {}).get("ac", 10), "char_class": achar.char_class, "level": achar.level,
            "known_spells": achar.known_spells or [], "cantrips": achar.cantrips or [],
            "spell_slots": achar.spell_slots or [], "speed": 30,
            "equipment": achar.equipment or {}, "personality": achar.personality or "",
            "actions": [{"name": w.get("name","武器"), "type": "melee_attack",
                         "damage_dice": w.get("damage","1d8"), "attack_bonus": actor_derived.get("attack_bonus",2)}
                        for w in (achar.equipment or {}).get("weapons", [])],
            "prepared_spells": achar.prepared_spells or [],
        })

    # 获取模组难度
    _module = await db.get(Module, session.module_id) if session.module_id else None
    _parsed = (_module.parsed_content or {}) if _module else {}
    _difficulty = calc_difficulty(_parsed)

    # 获取战术/性格
    _tactics = actor_full.get("tactics", "") if is_enemy else ""
    _personality = ""
    if not is_enemy and achar:
        _personality = f"{achar.personality or ''} 战斗偏好: {actor_derived.get('combat_preference', '平衡')}"

    # 调用 AI 决策
    decision = await get_ai_decision(
        actor=actor_full,
        actor_is_enemy=is_enemy,
        all_characters=all_characters,
        all_enemies=enemies_alive,
        positions=dict(combat.entity_positions or {}),
        module_difficulty=_difficulty,
        module_tactics=_tactics,
        actor_personality=_personality,
    )

    # 从决策中获取目标
    decided_target_id = decision.get("target_id")
    decided_action = decision.get("action_type", "attack")
    decided_reason = decision.get("reason", "")

    # ── 处理非攻击决策 ──
    if decided_action == "dodge":
        ts_dodge = _get_ts(combat, actor_id)
        ts_dodge["dodging"] = True
        _save_ts(combat, actor_id, ts_dodge)
        combat.current_turn_index = next_index
        if next_index == 0:
            combat.round_number += 1
        if turn_order:
            _ne = turn_order[next_index]["character_id"]
            _na, _nm = await _calc_entity_turn_limits(db, session, _ne)
            _reset_ts(combat, _ne, attacks_max=_na, movement_max=_nm)
        await db.commit()
        return {
            "actor_name": actor_name, "actor_id": actor_id,
            "narration": f"🛡️ {actor_name} 采取闪避动作。{decided_reason}",
            "attack_result": {}, "damage": 0, "target_id": None, "target_new_hp": None,
            "next_turn_index": next_index, "round_number": combat.round_number,
            "combat_over": False, "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        }

    if decided_action == "dash":
        # 双倍移动，不攻击
        if decided_target_id:
            dash_tgt_pos = positions.get(str(decided_target_id))
            dash_ts = _get_ts(combat, actor_id)
            dash_budget = (dash_ts["movement_max"] - dash_ts["movement_used"]) + dash_ts["movement_max"]
            dash_result = _ai_move_toward(positions.get(str(actor_id)), dash_tgt_pos, dash_budget, positions, actor_id)
            if dash_result:
                positions[str(actor_id)] = {"x": dash_result["x"], "y": dash_result["y"]}
                combat.entity_positions = positions
        combat.current_turn_index = next_index
        if next_index == 0:
            combat.round_number += 1
        if turn_order:
            _ne = turn_order[next_index]["character_id"]
            _na, _nm = await _calc_entity_turn_limits(db, session, _ne)
            _reset_ts(combat, _ne, attacks_max=_na, movement_max=_nm)
        await db.commit()
        return {
            "actor_name": actor_name, "actor_id": actor_id,
            "narration": f"🏃 {actor_name} 全力冲刺！{decided_reason}",
            "attack_result": {}, "damage": 0, "target_id": None, "target_new_hp": None,
            "next_turn_index": next_index, "round_number": combat.round_number,
            "combat_over": False, "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        }

    if decided_action == "disengage":
        ts_dis = _get_ts(combat, actor_id)
        ts_dis["disengaged"] = True
        _save_ts(combat, actor_id, ts_dis)
        combat.current_turn_index = next_index
        if next_index == 0:
            combat.round_number += 1
        if turn_order:
            _ne = turn_order[next_index]["character_id"]
            _na, _nm = await _calc_entity_turn_limits(db, session, _ne)
            _reset_ts(combat, _ne, attacks_max=_na, movement_max=_nm)
        await db.commit()
        return {
            "actor_name": actor_name, "actor_id": actor_id,
            "narration": f"🚪 {actor_name} 脱离战斗！{decided_reason}",
            "attack_result": {}, "damage": 0, "target_id": None, "target_new_hp": None,
            "next_turn_index": next_index, "round_number": combat.round_number,
            "combat_over": False, "outcome": None,
            "entity_positions": dict(combat.entity_positions or {}),
        }

    # ── AI 施法分支 ──
    if decided_action == "spell" and decision.get("action_name"):
        # AI 施法
        spell_name = decision["action_name"]
        spell_level = decision.get("spell_level") or 1
        spell_target = decided_target_id

        spell_data = spell_service.get(spell_name)
        if spell_data:
            from services.dnd_rules import roll_dice as _ai_roll
            derived_ai = actor_derived
            spell_mod = 0
            spell_abil = derived_ai.get("spell_ability")
            if spell_abil:
                spell_mod = derived_ai.get("ability_modifiers", {}).get(spell_abil, 0)
            spell_save_dc = derived_ai.get("spell_save_dc", 13)
            bonus_healing_ai = derived_ai.get("bonus_healing", False)

            is_cantrip = spell_data.get("level", 0) == 0
            is_aoe = spell_data.get("aoe", False)
            spell_type = spell_data.get("type", "damage")

            # Consume spell slot (if not cantrip and has character)
            if not is_cantrip and achar:
                slots = dict(achar.spell_slots or {})
                slot_key = ["1st","2nd","3rd","4th","5th","6th","7th","8th","9th"][min(spell_level-1, 8)]
                if slots.get(slot_key, 0) > 0:
                    slots[slot_key] = slots[slot_key] - 1
                    achar.spell_slots = slots
                else:
                    # No slot available, fall through to attack
                    spell_data = None

        if spell_data:
            # Resolve spell effect
            ai_spell_damage = 0
            ai_spell_heal = 0
            ai_spell_narration_parts = []
            target_new_hp = None
            target_name = ""

            if spell_type == "damage":
                total_dmg, dice_detail = spell_service.resolve_damage(spell_name, spell_level, spell_mod)

                if is_aoe:
                    # Hit all targets (enemies for companions, characters for enemies)
                    targets_list = []
                    if is_enemy:
                        # Enemy casts AoE on players
                        for c in all_characters:
                            if c.get("hp_current", 0) > 0:
                                targets_list.append(c)
                    else:
                        # Companion casts AoE on enemies
                        for en in enemies_alive:
                            targets_list.append(en)

                    save_ability = spell_data.get("save")
                    half_on_save = spell_data.get("half_on_save", True)

                    for tgt in targets_list[:4]:  # Max 4 targets
                        dmg_this = total_dmg
                        if save_ability:
                            t_derived = tgt.get("derived", {})
                            t_save_mod = t_derived.get("saving_throws", {}).get(save_ability,
                                t_derived.get("ability_modifiers", {}).get(save_ability, 0))
                            save_roll = _ai_roll("1d20")["rolls"][0]
                            if save_roll + t_save_mod >= spell_save_dc:
                                if half_on_save:
                                    dmg_this = dmg_this // 2
                                else:
                                    dmg_this = 0

                        tid = str(tgt.get("id", ""))
                        # Apply damage
                        if not is_enemy:  # Companion hits enemy
                            for e2 in enemies:
                                if str(e2.get("id")) == tid:
                                    e2["hp_current"] = svc.apply_damage(e2.get("hp_current", 0), dmg_this, e2.get("derived", {}).get("hp_max", 10))
                        else:  # Enemy hits character
                            tc = await db.get(Character, tid)
                            if tc:
                                tc.hp_current = svc.apply_damage(tc.hp_current, dmg_this, (tc.derived or {}).get("hp_max", tc.hp_current))
                        ai_spell_damage += dmg_this

                    state["enemies"] = enemies
                    session.game_state = dict(state)
                    flag_modified(session, "game_state")
                else:
                    # Single target damage
                    if spell_target:
                        target_enemy_sp = next((e2 for e2 in enemies if str(e2.get("id")) == str(spell_target)), None)
                        if target_enemy_sp:
                            save_ability = spell_data.get("save")
                            if save_ability:
                                t_saves = target_enemy_sp.get("derived", {}).get("saving_throws", {})
                                t_mod = t_saves.get(save_ability, 0)
                                sr = _ai_roll("1d20")["rolls"][0]
                                if sr + t_mod >= spell_save_dc:
                                    if spell_data.get("half_on_save"):
                                        total_dmg = total_dmg // 2
                                    else:
                                        total_dmg = 0
                            target_enemy_sp["hp_current"] = svc.apply_damage(target_enemy_sp.get("hp_current", 0), total_dmg, target_enemy_sp.get("derived", {}).get("hp_max", 10))
                            target_new_hp = target_enemy_sp["hp_current"]
                            target_name = target_enemy_sp.get("name", "敌人")
                            state["enemies"] = enemies
                            session.game_state = dict(state)
                            flag_modified(session, "game_state")
                        else:
                            tc = await db.get(Character, spell_target)
                            if tc:
                                tc.hp_current = svc.apply_damage(tc.hp_current, total_dmg, (tc.derived or {}).get("hp_max", tc.hp_current))
                                target_new_hp = tc.hp_current
                                target_name = tc.name
                        ai_spell_damage = total_dmg

            elif spell_type == "heal":
                total_heal, dice_detail = spell_service.resolve_heal(spell_name, spell_level, spell_mod, bonus_healing_ai)
                # Heal target
                if spell_target:
                    tc = await db.get(Character, spell_target)
                    if tc:
                        hp_max_t = (tc.derived or {}).get("hp_max", tc.hp_current)
                        tc.hp_current = min(hp_max_t, tc.hp_current + total_heal)
                        target_new_hp = tc.hp_current
                        target_name = tc.name
                ai_spell_heal = total_heal

            elif spell_type in ("control", "utility"):
                # Apply condition to target
                condition_map = {
                    "Hold Person": "paralyzed",
                    "定身术": "paralyzed",
                    "Entangle": "restrained",
                    "纠缠术": "restrained",
                    "Web": "restrained",
                    "蛛网": "restrained",
                    "Sleep": "unconscious",
                    "睡眠术": "unconscious",
                    "Command": "commanded",
                    "命令术": "commanded",
                    "Faerie Fire": "faerie_fire",
                    "妖火": "faerie_fire",
                    "Blindness/Deafness": "blinded",
                    "目盲/耳聋": "blinded",
                    "Fear": "frightened",
                    "恐惧术": "frightened",
                    "Silence": "silenced",
                    "沉默术": "silenced",
                }
                condition = condition_map.get(spell_name, "hexed")
                save_ability = spell_data.get("save")

                if spell_target and save_ability:
                    # Target makes save
                    target_enemy_ctrl = next((e2 for e2 in enemies if str(e2.get("id")) == str(spell_target)), None)
                    if target_enemy_ctrl:
                        t_scores = target_enemy_ctrl.get("ability_scores", {})
                        t_mod = (t_scores.get(save_ability, 10) - 10) // 2
                        sr = _ai_roll("1d20")["rolls"][0]
                        if sr + t_mod < spell_save_dc:
                            conds = target_enemy_ctrl.get("conditions", [])
                            if condition not in conds:
                                conds.append(condition)
                                target_enemy_ctrl["conditions"] = conds
                            ai_spell_narration_parts.append(f"{target_enemy_ctrl.get('name')} 未通过豁免，陷入{condition}状态！")
                        else:
                            ai_spell_narration_parts.append(f"{target_enemy_ctrl.get('name')} 通过了豁免！")
                        target_name = target_enemy_ctrl.get("name", "敌人")
                        state["enemies"] = enemies
                        session.game_state = dict(state)
                        flag_modified(session, "game_state")
                    else:
                        tc = await db.get(Character, spell_target)
                        if tc:
                            t_derived = tc.derived or {}
                            t_mod = t_derived.get("saving_throws", {}).get(save_ability, 0)
                            sr = _ai_roll("1d20")["rolls"][0]
                            if sr + t_mod < spell_save_dc:
                                conds = list(tc.conditions or [])
                                if condition not in conds:
                                    conds.append(condition)
                                    tc.conditions = conds
                                ai_spell_narration_parts.append(f"{tc.name} 未通过豁免，陷入{condition}状态！")
                            else:
                                ai_spell_narration_parts.append(f"{tc.name} 通过了豁免！")
                            target_name = tc.name

            # Concentration
            if spell_data.get("concentration") and achar:
                achar.concentration = spell_name

            # Build narration
            level_str = f"{spell_level}环" if not is_cantrip else "戏法"
            spell_narr = f"✨ {actor_name} 施放了【{spell_name}】（{level_str}）！"
            if ai_spell_damage > 0:
                spell_narr += f"造成 {ai_spell_damage} 点伤害！"
            if ai_spell_heal > 0:
                spell_narr += f"恢复 {ai_spell_heal} HP！"
            if ai_spell_narration_parts:
                spell_narr += " ".join(ai_spell_narration_parts)
            if decided_reason:
                spell_narr += f"（{decided_reason}）"

            # LLM narration
            ai_class_sp = _normalize_class(achar.char_class) if achar else actor_name
            vivid = await narrate_action(
                actor_name=actor_name, actor_class=ai_class_sp,
                target_name=target_name or "目标", action_type="spell",
                spell_name=spell_name, damage=ai_spell_damage, heal_amount=ai_spell_heal,
            )
            if vivid:
                spell_narr = vivid

            # Log
            db.add(GameLog(
                session_id=session_id, role="enemy" if is_enemy else f"companion_{actor_name}",
                content=spell_narr, log_type="combat",
            ))

            # Advance turn
            combat.current_turn_index = next_index
            if next_index == 0:
                combat.round_number += 1
            if turn_order:
                ne_id = turn_order[next_index]["character_id"]
                n_atk, n_mv = await _calc_entity_turn_limits(db, session, ne_id)
                _reset_ts(combat, ne_id, attacks_max=n_atk, movement_max=n_mv)

            flag_modified(session, "game_state")
            await db.commit()
            return {
                "actor_name": actor_name, "actor_id": actor_id,
                "narration": spell_narr,
                "attack_result": {}, "damage": ai_spell_damage,
                "target_id": str(spell_target) if spell_target else None,
                "target_new_hp": target_new_hp,
                "next_turn_index": next_index, "round_number": combat.round_number,
                "combat_over": False, "outcome": None,
                "entity_positions": dict(combat.entity_positions or {}),
            }

    # ── 攻击/法术：查找目标数据 ──
    # Fallback 目标选择（当 AI 决策失败或 target_id 无效时）
    target_data = None
    if decided_target_id:
        # 在敌人和角色中查找目标
        for t in enemies_alive:
            if str(t.get("id")) == str(decided_target_id):
                target_data = t
                break
        if not target_data:
            for t in all_characters:
                if str(t.get("id")) == str(decided_target_id):
                    target_data = t
                    break

    if not target_data:
        # AI 决策失败或 target_id 无效，回退到旧逻辑
        target_data = svc.choose_ai_target(
            actor_is_enemy=is_enemy,
            player={"id": player.id, "hp_current": player.hp_current, "derived": player.derived or {}} if player else None,
            allies=companions_alive,
            enemies_alive=enemies_alive,
        )

    # ── 解析攻击（含 Extra Attack / Sneak Attack / Rage for AI）──
    target_id       = None
    target_name     = ""
    target_new_hp   = None
    target_is_enemy = False
    total_damage    = 0
    all_narrations  = []
    positions       = dict(combat.entity_positions or {})

    # Determine AI actor's class/level for class features
    ai_class = ""
    ai_level = 1
    ai_class_res = {}
    if achar:
        ai_class = _normalize_class(achar.char_class)
        ai_level = achar.level
        ai_class_res = dict(achar.class_resources or {})

    # AI Barbarian: auto-rage if not already raging
    if achar and ai_class == "Barbarian" and not ai_class_res.get("raging", False):
        rage_rem = ai_class_res.get("rage_remaining", svc.get_rage_uses(ai_level))
        if rage_rem > 0:
            ai_class_res["raging"] = True
            ai_class_res["rage_remaining"] = rage_rem - 1
            achar.class_resources = ai_class_res
            all_narrations.append(f"🔥 {actor_name} 进入狂暴！")

    # Calculate number of attacks
    num_attacks = 1
    if achar:
        num_attacks = svc.get_attack_count(actor_derived, ai_level, ai_class)

    result_obj = None
    first_attack_roll = None

    if target_data:
        target_id      = target_data["id"]
        target_derived = target_data.get("derived", {})

        # Cover bonus for AI attacks (P0-8)
        ai_grid = dict(combat.grid_data or {})
        ai_atk_pos = positions.get(str(actor_id))
        ai_tgt_pos = positions.get(str(target_id))
        ai_cover = 0
        if ai_atk_pos and ai_tgt_pos:
            ai_cover = svc.get_cover_bonus(ai_grid, ai_atk_pos, ai_tgt_pos)
        ai_target_derived = dict(target_derived)
        if ai_cover > 0:
            ai_target_derived["ac"] = target_derived.get("ac", 10) + ai_cover

        # Shield spell AC bonus (P0-6): if target has shield_spell condition, +5 AC
        if not is_enemy:
            pass  # enemy attacks character - check character conditions
        target_char_for_shield = await db.get(Character, target_id) if target_id else None
        if target_char_for_shield and "shield_spell" in (target_char_for_shield.conditions or []):
            ai_target_derived["ac"] = ai_target_derived.get("ac", 10) + 5

        # ── AI 距离检查 + 自动移动 ─────────────────────────
        ai_is_ranged = False
        # 判断 AI 是否使用远程武器（从装备中检测）
        if achar and achar.equipment:
            ai_weapons = (achar.equipment or {}).get("weapons", [])
            for w in ai_weapons:
                wp = (w.get("properties") or "")
                if isinstance(wp, list):
                    wp = ",".join(wp)
                if "远程" in wp or "ranged" in wp.lower() or w.get("type", "") in ("简易远程武器", "军用远程武器"):
                    ai_is_ranged = True
                    break
        # 怪物默认近战（无 Character 对象时）
        if not achar:
            # 检查怪物数据中的 actions 判断是否远程
            for e in enemies:
                if str(e.get("id")) == str(actor_id):
                    for act in e.get("actions", []):
                        if "远程" in act.get("type", "") or "ranged" in act.get("type", "").lower():
                            ai_is_ranged = True
                    break

        in_range, ai_dist, _ = _check_attack_range(ai_atk_pos, ai_tgt_pos, ai_is_ranged)
        if not in_range and ai_atk_pos and ai_tgt_pos:
            # 尝试自动移动靠近目标
            actor_ts_pre = _get_ts(combat, actor_id)
            move_remaining = actor_ts_pre["movement_max"] - actor_ts_pre["movement_used"]
            move_result = _ai_move_toward(ai_atk_pos, ai_tgt_pos, move_remaining, positions, actor_id)
            if move_result:
                new_pos = {"x": move_result["x"], "y": move_result["y"]}
                positions[str(actor_id)] = new_pos
                combat.entity_positions = positions
                actor_ts_pre["movement_used"] += move_result["steps"]
                _save_ts(combat, actor_id, actor_ts_pre)
                all_narrations.append(f"🏃 {actor_name} 向目标移动了 {move_result['steps']*5}ft")
                # 重新检查距离
                in_range, ai_dist, _ = _check_attack_range(new_pos, ai_tgt_pos, ai_is_ranged)
                # 更新掩体计算
                if in_range:
                    ai_cover = svc.get_cover_bonus(ai_grid, new_pos, ai_tgt_pos)
                    if ai_cover > 0:
                        ai_target_derived["ac"] = target_derived.get("ac", 10) + ai_cover

        if not in_range:
            # 仍然不在攻击范围内，跳过攻击
            all_narrations.append(f"{actor_name} 无法到达目标（距离 {ai_dist*5}ft）")
            narrate_text = await narrate_batch(
                [{"actor": actor_name, "action": "移动", "target": "", "result": "移动但无法接近目标"}]
            )
            if narrate_text and narrate_text[0]:
                all_narrations.append(narrate_text[0])

            # 推进回合
            combat.current_turn_index = next_index
            if next_index == 0:
                combat.round_number += 1
            if turn_order:
                _ne = turn_order[next_index]["character_id"]
                _na, _nm = await _calc_entity_turn_limits(db, session, _ne)
                _reset_ts(combat, _ne, attacks_max=_na, movement_max=_nm)
            flag_modified(session, "game_state")
            flag_modified(combat, "entity_positions")
            flag_modified(combat, "turn_states")
            await db.commit()
            return {
                "actor_name": actor_name,
                "actor_id": actor_id,
                "narration": "\n".join(all_narrations),
                "attack_result": {}, "damage": 0,
                "target_id": str(target_id) if target_id else None,
                "target_new_hp": None,
                "next_turn_index": next_index, "round_number": combat.round_number,
                "combat_over": False, "outcome": None,
                "entity_positions": dict(combat.entity_positions or {}),
            }

        # 「被协助」→ 攻击优势
        actor_ts   = _get_ts(combat, actor_id)
        extra_adv  = actor_ts.get("being_helped", False)
        if extra_adv:
            actor_ts["being_helped"] = False
            _save_ts(combat, actor_id, actor_ts)

        for atk_idx in range(num_attacks):
            result_obj = svc.resolve_melee_attack(
                attacker_derived = actor_derived,
                target_derived   = ai_target_derived,
                advantage        = extra_adv if atk_idx == 0 else False,
            )
            if first_attack_roll is None:
                first_attack_roll = result_obj

            atk_damage = result_obj.damage

            # AI Rage bonus
            if result_obj.attack_roll["hit"] and achar and ai_class_res.get("raging", False):
                rage_bonus = svc.get_rage_bonus(ai_level)
                atk_damage += rage_bonus
                # Zealot Divine Fury (first hit per turn while raging)
                ai_sub_effects = actor_derived.get("subclass_effects", {})
                if ai_sub_effects.get("divine_fury") and atk_idx == 0:
                    fury_roll = roll_dice(f"1d6+{ai_level // 2}")
                    atk_damage += fury_roll["total"]

            # AI Sneak Attack (first hit only)
            if result_obj.attack_roll["hit"] and achar and ai_class == "Rogue" and atk_idx == 0:
                # Check ally adjacency for sneak attack
                ally_list_for_sa = [{"id": a["id"], "hp_current": a.get("hp_current", 0)} for a in enemies_alive] if not is_enemy else []
                if is_enemy:
                    pass  # enemies don't get sneak attack
                else:
                    p_data = {"id": player.id, "hp_current": player.hp_current} if player else None
                    ally_list_sa = [p_data] if p_data else []
                    ally_list_sa += [{"id": ca["id"], "hp_current": ca.get("hp_current", 0)} for ca in companions_alive]
                    ally_adj = _has_ally_adjacent_to(target_id, actor_id, ally_list_sa, positions)
                    has_adv = extra_adv if atk_idx == 0 else False
                    # Swashbuckler AI companion
                    ai_sub_sa = actor_derived.get("subclass_effects", {})
                    ai_swash = ai_sub_sa.get("swashbuckler", False)
                    ai_no_other = False
                    if ai_swash:
                        other_enemies_sa = [e for e in enemies if e["id"] != target_id and e.get("hp_current", 0) > 0]
                        ai_no_other = not _has_ally_adjacent_to(actor_id, target_id, other_enemies_sa, positions)
                    if svc.check_sneak_attack(ai_class, has_adv, ally_adj, swashbuckler=ai_swash, no_other_enemy_adjacent=ai_no_other):
                        sa_dice = svc.calc_sneak_attack_dice(ai_level)
                        sa_roll = roll_dice(f"{sa_dice}d6")
                        atk_damage += sa_roll["total"]

            if result_obj.attack_roll["hit"]:
                if not is_enemy:  # 队友攻击敌人
                    for e2 in enemies:
                        if e2["id"] == target_id:
                            e2["hp_current"] = svc.apply_damage(e2.get("hp_current", 0), atk_damage, e2.get("derived", {}).get("hp_max", 10))
                            target_new_hp   = e2["hp_current"]
                    state["enemies"]      = enemies
                    session.game_state = dict(state); flag_modified(session, "game_state")
                    target_name           = target_data.get("name", "敌人")
                else:  # 敌人攻击玩家/队友
                    tchar = await db.get(Character, target_id)
                    if tchar:
                        # Apply damage resistance for raging barbarian targets
                        final_dmg = atk_damage
                        if tchar and _normalize_class(tchar.char_class) == "Barbarian":
                            t_res = dict(tchar.class_resources or {})
                            if t_res.get("raging", False):
                                dmg_type = actor_derived.get("damage_type", "钝击")
                                t_sub_effects = (tchar.derived or {}).get("subclass_effects", {})
                                if t_sub_effects.get("bear_totem"):
                                    # Bear Totem: resist ALL damage except psychic
                                    if dmg_type not in ("心灵", "psychic"):
                                        final_dmg = final_dmg // 2
                                elif dmg_type in ("钝击", "穿刺", "挥砍", "bludgeoning", "piercing", "slashing"):
                                    final_dmg = final_dmg // 2
                        tchar.hp_current  = svc.apply_damage(tchar.hp_current, final_dmg, (tchar.derived or {}).get("hp_max", tchar.hp_current))
                        target_new_hp     = tchar.hp_current
                        target_name       = tchar.name

            total_damage += atk_damage
            all_narrations.append(svc._build_narration(actor_name, target_name or target_data.get("name", "?"), result_obj.attack_roll, atk_damage))

            # Dark One's Blessing: AI Warlock gains temp HP on kill
            if target_new_hp is not None and target_new_hp <= 0 and not is_enemy and achar:
                ai_sub_eff = actor_derived.get("subclass_effects", {})
                if ai_sub_eff.get("dark_ones_blessing"):
                    cha_val = actor_derived.get("ability_modifiers", {}).get("cha", 0)
                    _temp_hp = cha_val + ai_level
                    all_narrations.append(f"{actor_name} 获得 {_temp_hp} 临时HP（黑暗祝福）")

            # If target is dead, stop attacking
            if target_new_hp is not None and target_new_hp <= 0:
                break

    if not all_narrations:
        all_narrations.append(f"{actor_name} 没有找到目标，跳过回合。")

    mechanical_narration = " | ".join(all_narrations) if len(all_narrations) > 1 else all_narrations[0]
    # Use first_attack_roll for the response (backward compat)
    result_obj = first_attack_roll

    # ── LLM vivid narration for AI turn ──
    ai_actor_class = ai_class if achar else (e.get("name", "怪物") if e else "")
    batch_actions = [{
        "actor_name": actor_name,
        "actor_class": ai_actor_class,
        "target_name": target_name or "目标",
        "mechanical_desc": f"{mechanical_narration}" + (f"（战术：{decided_reason}）" if decided_reason and not decision.get("_fallback") else ""),
    }]
    vivid_results = await narrate_batch(batch_actions)
    narration = vivid_results[0] if vivid_results[0] else mechanical_narration

    # ── 专注中断检定（敌方命中友方角色时）────────────────
    conc_log = None
    if result_obj and result_obj.attack_roll.get("hit") and is_enemy and target_id:
        tchar_conc = await db.get(Character, target_id)
        if tchar_conc:
            conc_log = await _do_concentration_check(tchar_conc, total_damage, session_id)

    # ── 回合结束：条件倒计时（5e标准：在实体回合结束时tick）──
    if is_enemy and e:
        removed = _tick_conditions_enemy(e)
        for c in removed:
            ai_tick_logs.append(GameLog(
                session_id=session_id, role="system",
                content=f"🟢 {actor_name} 的【{c}】状态到期解除", log_type="system",
            ))
        state["enemies"] = enemies
        session.game_state = dict(state); flag_modified(session, "game_state")
    elif not is_enemy and achar:
        removed = _tick_conditions_char(achar)
        for c in removed:
            ai_tick_logs.append(GameLog(
                session_id=session_id, role="system",
                content=f"🟢 {actor_name} 的【{c}】状态到期解除", log_type="system",
            ))

    # ── 写日志 & 推进回合 ────────────────────────────────
    role_key = "enemy" if is_enemy else f"companion_{actor_name}"
    db.add(GameLog(
        session_id  = session_id,
        role        = role_key,
        content     = narration,
        log_type    = "combat",
        dice_result = {"attack": result_obj.attack_roll, "damage": total_damage} if result_obj else None,
    ))

    for tl in ai_tick_logs:
        db.add(tl)
    if conc_log:
        db.add(conc_log)

    next_index = (combat.current_turn_index + 1) % max(len(turn_order), 1)
    combat.current_turn_index = next_index
    if next_index == 0:
        combat.round_number += 1

    # 重置下一实体的回合状态（根据角色实际数据）
    if turn_order:
        next_entity_id = turn_order[next_index]["character_id"]
        next_atk_max, next_move_max = await _calc_entity_turn_limits(db, session, next_entity_id)
        _reset_ts(combat, next_entity_id, attacks_max=next_atk_max, movement_max=next_move_max)

    player_check         = await db.get(Character, session.player_character_id)
    combat_over, outcome = svc.check_combat_over(enemies, player_check.hp_current if player_check else 0)
    if combat_over:
        session.combat_active = False
        # 清理战斗状态记录，防止下次战斗残留旧数据
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs: await db.delete(_old_cs)
        except Exception: pass

    # ── Reaction info (P0-6): check if player was targeted and can react ──
    player_targeted = (is_enemy and target_id == session.player_character_id)
    player_can_react = False
    reaction_prompt = None
    if player_targeted and player_check:
        p_ts = _get_ts(combat, session.player_character_id)
        if not p_ts.get("reaction_used"):
            player_can_react = True
            p_derived_r = player_check.derived or {}
            p_cls = _normalize_class(player_check.char_class)
            p_level = player_check.level or 1
            # Build reaction prompt for frontend — enhanced with class/spell details
            known_spells = set(player_check.known_spells or []) | set(player_check.prepared_spells or [])
            p_slots = dict(player_check.spell_slots or {})
            available_reactions = []

            # Shield spell (Wizard/Sorcerer/Hexblade — costs 1st-level slot, +5 AC until next turn)
            if ("Shield" in known_spells or "shield" in known_spells) and p_slots.get("1st", 0) > 0:
                available_reactions.append({
                    "id": "shield",
                    "name": "Shield",
                    "type": "spell",
                    "cost": "1st-level spell slot",
                    "slot_level": "1st",
                    "slots_remaining": p_slots.get("1st", 0),
                    "effect": "+5 AC（持续到你的下个回合开始）",
                    "resulting_ac": p_derived_r.get("ac", 10) + 5,
                })

            # Uncanny Dodge (Rogue 5+, halve incoming damage)
            if p_cls == "Rogue" and p_level >= 5:
                available_reactions.append({
                    "id": "uncanny_dodge",
                    "name": "Uncanny Dodge",
                    "type": "class_feature",
                    "cost": "reaction",
                    "effect": f"将此次攻击的伤害减半（{total_damage} → {total_damage // 2}）",
                    "reduced_damage": total_damage // 2,
                })

            # Hellish Rebuke (Tiefling/Warlock — costs 1st-level slot, 2d10 fire)
            if ("Hellish Rebuke" in known_spells or "hellish_rebuke" in known_spells) and p_slots.get("1st", 0) > 0:
                available_reactions.append({
                    "id": "hellish_rebuke",
                    "name": "Hellish Rebuke",
                    "type": "spell",
                    "cost": "1st-level spell slot",
                    "slot_level": "1st",
                    "slots_remaining": p_slots.get("1st", 0),
                    "effect": "对攻击者造成 2d10 火焰伤害（DEX豁免成功减半）",
                    "damage_dice": "2d10",
                })

            # Absorb Elements (Ranger/Wizard/Sorcerer/Druid — 1st-level, elemental resistance)
            if ("Absorb Elements" in known_spells or "absorb_elements" in known_spells) and p_slots.get("1st", 0) > 0:
                available_reactions.append({
                    "id": "absorb_elements",
                    "name": "Absorb Elements",
                    "type": "spell",
                    "cost": "1st-level spell slot",
                    "slot_level": "1st",
                    "slots_remaining": p_slots.get("1st", 0),
                    "effect": "获得触发元素的伤害抗性（持续到下回合开始），下次近战+1d6该元素伤害",
                })

            # Counterspell (if the enemy action was a spell — basic support)
            if ("Counterspell" in known_spells or "counterspell" in known_spells) and p_slots.get("3rd", 0) > 0:
                available_reactions.append({
                    "id": "counterspell",
                    "name": "Counterspell",
                    "type": "spell",
                    "cost": "3rd-level spell slot",
                    "slot_level": "3rd",
                    "slots_remaining": p_slots.get("3rd", 0),
                    "effect": "反制敌人施放的法术（3环或以下自动成功，更高需检定）",
                })

            if available_reactions:
                reaction_prompt = {
                    "can_react": True,
                    "reaction_used": p_ts.get("reaction_used", False),
                    "attack_roll": result_obj.attack_roll.get("attack_total", 0) if result_obj else 0,
                    "player_ac": p_derived_r.get("ac", 10),
                    "incoming_damage": total_damage,
                    "attacker_name": actor_name,
                    "attacker_id": actor_id,
                    "spell_slots": p_slots,
                    "available_reactions": available_reactions,
                }

    await db.commit()
    return {
        "actor_name":           actor_name,
        "actor_id":             actor_id,
        "narration":            narration,
        "attack_result":        result_obj.attack_roll if result_obj else {},
        "damage":               total_damage,
        "target_id":            target_id,
        "target_new_hp":        target_new_hp,
        "concentration_check":  conc_log.dice_result if conc_log else None,
        "player_targeted":      player_targeted,
        "player_can_react":     player_can_react,
        "reaction_prompt":      reaction_prompt,
        "next_turn_index":      next_index,
        "round_number":         combat.round_number,
        "combat_over":          combat_over,
        "outcome":              outcome,
        "entity_positions":     dict(combat.entity_positions or {}),
    }


# ── 结束战斗 ──────────────────────────────────────────────

@router.post("/combat/{session_id}/end")
async def end_combat(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await get_session_or_404(session_id, db)
    session.combat_active = False
    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if combat:
        await db.delete(combat)
    db.add(GameLog(session_id=session_id, role="system",
                   content="⚔️ 战斗结束，队伍继续前进。", log_type="system"))
    await db.commit()
    return {"ok": True}


# ── 移动 ─────────────────────────────────────────────────

@router.post("/combat/{session_id}/move")
async def combat_move(session_id: str, req: MoveRequest, db: AsyncSession = Depends(get_db)):
    """在战斗格子上移动实体（每回合最多 6 格 = 30ft）"""
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    if not (0 <= req.to_x < 20 and 0 <= req.to_y < 12):
        raise HTTPException(400, "目标格子超出地图范围（20×12）")

    positions = dict(combat.entity_positions or {})
    for eid, pos in positions.items():
        if eid != req.entity_id and pos.get("x") == req.to_x and pos.get("y") == req.to_y:
            raise HTTPException(400, "目标格子已有其他实体")

    # ── 使用回合状态追踪移动力 ────────────────────────────
    ts  = _get_ts(combat, req.entity_id)
    cur = positions.get(str(req.entity_id))
    if cur:
        # Chebyshev 距离（对角移动和直线移动同等消耗，符合 5e 标准规则）
        dist      = max(abs(cur["x"] - req.to_x), abs(cur["y"] - req.to_y))
        remaining = ts["movement_max"] - ts["movement_used"]
        if dist > remaining:
            raise HTTPException(400, f"移动距离 {dist} 格超出剩余移动力（剩余 {remaining} 格）")

        # ── 借机攻击检查（移动前，使用旧位置计算相邻性）────
        # 脱离接战的实体不触发借机攻击
        opp_results = []
        if not ts.get("disengaged"):
            opp_results = await _resolve_opportunity_attacks(
                db       = db,
                session  = session,
                combat   = combat,
                moving_id = str(req.entity_id),
                old_pos  = cur,
                new_pos  = {"x": req.to_x, "y": req.to_y},
                positions = positions,
            )
        for opp in opp_results:
            if opp.get("log"):
                db.add(opp["log"])

        ts["movement_used"] += dist
        _save_ts(combat, req.entity_id, ts)

    positions[str(req.entity_id)] = {"x": req.to_x, "y": req.to_y}
    combat.entity_positions        = positions

    # 借机攻击后检查战斗是否结束
    opp_combat_over, opp_outcome = False, None
    if opp_results:
        opp_state   = session.game_state or {}
        opp_enemies = list(opp_state.get("enemies", []))
        player_opp  = await db.get(Character, session.player_character_id)
        opp_combat_over, opp_outcome = svc.check_combat_over(
            opp_enemies, player_opp.hp_current if player_opp else 0
        )
        if opp_combat_over:
            session.combat_active = False

    await db.commit()
    return {
        "entity_id":               req.entity_id,
        "x":                       req.to_x,
        "y":                       req.to_y,
        "positions":               positions,
        "turn_state":              ts,
        "movement_used":           ts["movement_used"],
        "movement_max":            ts["movement_max"],
        "opportunity_attacks":     [
            {"attacker": o["attacker"], "target": o["target"], **o["result"]}
            for o in opp_results
        ],
        "combat_over":             opp_combat_over,
        "outcome":                 opp_outcome,
    }


# ── 法术 ─────────────────────────────────────────────────

@router.get("/spells")
async def get_spell_list():
    """获取完整法术列表"""
    return spell_service.get_all()


@router.get("/spells/class/{class_name}")
async def get_spells_for_class(class_name: str, max_level: int = 9):
    """获取指定职业的可用法术"""
    return spell_service.get_for_class(class_name, max_level)


# ── 两步施法流程：spell-roll → spell-confirm ──────────────────

@router.post("/combat/{session_id}/spell-roll")
async def spell_roll(
    session_id: str,
    req: SpellRollRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    两步施法 Step 1：验证法术/法术位/目标，返回将要掷的骰子信息。
    不实际掷伤害骰、不消耗法术位、不应用效果。
    将 pending_spell 存入 turn_states。
    """
    session = await get_session_or_404(session_id, db)

    spell = spell_service.get(req.spell_name)
    if not spell:
        raise HTTPException(400, f"未知法术：{req.spell_name}")

    err = spell_service.validate_slot_level(req.spell_name, req.spell_level)
    if err:
        raise HTTPException(400, err)

    caster = await db.get(Character, req.caster_id)
    if not caster:
        raise HTTPException(404, "施法者不��在")

    # ── 检查行动配额 ──
    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat_obj = combat_result.scalars().first()
    spell_ts = _get_ts(combat_obj, req.caster_id) if combat_obj else dict(_DEFAULT_TS)
    if spell_ts["action_used"] and spell["level"] != 0:
        raise HTTPException(400, "本回合行动已用尽")

    # ── 验证法术位 ──
    is_cantrip = spell["level"] == 0
    if not is_cantrip:
        current_slots = dict(caster.spell_slots or {})
        _, slot_err = spell_service.consume_slot(dict(current_slots), req.spell_level)
        if slot_err:
            raise HTTPException(400, slot_err)

    # ── 确定目标列表 ──
    state = session.game_state or {}
    enemies = list(state.get("enemies", []))
    is_aoe = spell.get("aoe", False)

    raw_ids = req.target_ids if req.target_ids is not None else (
        [req.target_id] if req.target_id else []
    )
    if is_aoe and not raw_ids:
        raw_ids = [e["id"] for e in enemies if e.get("hp_current", 0) > 0]

    target_names = []
    for tid in raw_ids:
        e = next((en for en in enemies if en["id"] == tid), None)
        if e:
            target_names.append(e["name"])
        else:
            tc = await db.get(Character, tid)
            if tc:
                target_names.append(tc.name)

    # ── 距离检查（法术射程）──
    positions = dict(combat_obj.entity_positions or {}) if combat_obj else {}
    caster_pos = positions.get(str(req.caster_id))
    spell_range_ft = spell.get("range", 0)
    if isinstance(spell_range_ft, str):
        import re as _re
        m = _re.search(r'(\d+)', str(spell_range_ft))
        spell_range_ft = int(m.group(1)) if m else 0
    if spell_range_ft > 0 and raw_ids:
        spell_range_tiles = max(spell_range_ft // 5, 1)
        for tid in raw_ids:
            tgt_pos = positions.get(str(tid))
            dist = _chebyshev_dist(caster_pos, tgt_pos)
            if dist > spell_range_tiles:
                raise HTTPException(400, f"目标超出法术射程（距离{dist*5}ft，射程{spell_range_ft}ft）")

    # ── 计算要掷的骰子 ──
    derived = caster.derived or {}
    spell_abil = derived.get("spell_ability")
    spell_mod = derived.get("ability_modifiers", {}).get(spell_abil or "", 0) if spell_abil else 0
    spell_save_dc = derived.get("spell_save_dc", 13)

    # Figure out the dice expression from spell data
    damage_dice = ""
    heal_dice = ""
    if spell["type"] == "damage":
        base_dice = spell.get("damage_dice", spell.get("damage", "1d6"))
        upcast_dice = spell_service.calc_upcast_dice(req.spell_name, req.spell_level)
        damage_dice = upcast_dice if upcast_dice else base_dice
    elif spell["type"] == "heal":
        base_dice = spell.get("heal_dice", spell.get("heal", "1d8"))
        upcast_dice = spell_service.calc_upcast_dice(req.spell_name, req.spell_level)
        heal_dice = upcast_dice if upcast_dice else base_dice

    save_type = spell.get("save", None)

    # ── 生成 pending_spell_id 并暂存 ──
    pending_id = str(uuid.uuid4())
    pending_spell = {
        "pending_spell_id": pending_id,
        "caster_id": req.caster_id,
        "spell_name": req.spell_name,
        "spell_level": req.spell_level,
        "target_ids": raw_ids,
        "is_cantrip": is_cantrip,
        "is_aoe": is_aoe,
        "spell_type": spell["type"],
    }

    if combat_obj:
        spell_ts["pending_spell"] = pending_spell
        _save_ts(combat_obj, req.caster_id, spell_ts)

    await db.commit()

    return {
        "spell_name": req.spell_name,
        "spell_level": req.spell_level,
        "spell_type": spell["type"],
        "damage_dice": damage_dice,
        "heal_dice": heal_dice,
        "save_type": save_type,
        "save_dc": spell_save_dc if save_type else None,
        "is_cantrip": is_cantrip,
        "is_aoe": is_aoe,
        "is_concentration": spell.get("concentration", False),
        "targets": [{"id": tid, "name": n} for tid, n in zip(raw_ids, target_names)],
        "pending_spell_id": pending_id,
        "turn_state": spell_ts,
    }


@router.post("/combat/{session_id}/spell-confirm")
async def spell_confirm(
    session_id: str,
    req: SpellConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    两步施法 Step 2：掷伤害/治疗骰，消耗法术位，应用效果。
    必须在 /spell-roll 之后调用。
    """
    session = await get_session_or_404(session_id, db)

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat_obj = combat_result.scalars().first()
    if not combat_obj:
        raise HTTPException(404, "战斗状态不存在")

    await db.refresh(session)

    # ── 查找 pending_spell ──
    all_ts = dict(combat_obj.turn_states or {})
    caster_entity_id = None
    pending = None
    for eid, ets in all_ts.items():
        ps = ets.get("pending_spell")
        if ps and ps.get("pending_spell_id") == req.pending_spell_id:
            pending = ps
            caster_entity_id = eid
            break

    if not pending:
        raise HTTPException(404, "未找到待处理的施法，可能已过期或 ID 错误")

    caster = await db.get(Character, caster_entity_id)
    if not caster:
        raise HTTPException(404, "施法���不存在")

    spell_name = pending["spell_name"]
    spell_level = pending["spell_level"]
    target_ids = pending["target_ids"]
    is_cantrip = pending["is_cantrip"]
    is_aoe = pending["is_aoe"]
    spell_type = pending["spell_type"]

    spell = spell_service.get(spell_name)
    if not spell:
        raise HTTPException(400, f"未知法术：{spell_name}")

    # ── 消耗法术位 ──
    if not is_cantrip:
        new_slots, slot_err = spell_service.consume_slot(dict(caster.spell_slots or {}), spell_level)
        if slot_err:
            raise HTTPException(400, slot_err)
        caster.spell_slots = new_slots
    else:
        new_slots = caster.spell_slots or {}

    # ── 施法属性 ──
    derived = caster.derived or {}
    spell_abil = derived.get("spell_ability")
    spell_mod = derived.get("ability_modifiers", {}).get(spell_abil or "", 0) if spell_abil else 0
    spell_save_dc = derived.get("spell_save_dc", 13)
    bonus_healing = derived.get("bonus_healing", False)

    state = session.game_state or {}
    enemies = list(state.get("enemies", []))

    result_damage = 0
    result_heal = 0
    dice_detail = {}
    target_new_hp = None
    aoe_results = []
    conc_logs = []

    # ══ AoE 法术 ══
    if is_aoe:
        if spell_type == "damage":
            result_damage, dice_detail = spell_service.resolve_damage(spell_name, spell_level, spell_mod)
            # Frontend dice override for spell damage
            if req.damage_values:
                result_damage = sum(req.damage_values) + spell_mod
                dice_detail["total"] = result_damage
                if "base_roll" in dice_detail:
                    dice_detail["base_roll"]["rolls"] = req.damage_values
                    dice_detail["base_roll"]["total"] = sum(req.damage_values)
            save_ability = spell.get("save")
            half_on_save = spell.get("half_on_save", True)

            for tid in target_ids:
                dmg_this = result_damage
                save_result = None

                if save_ability:
                    target_enemy = next((e for e in enemies if e["id"] == tid), None)
                    target_char = None if target_enemy else await db.get(Character, tid)
                    t_derived = (target_enemy.get("derived", {}) if target_enemy
                                 else (target_char.derived or {} if target_char else {}))
                    t_saves = t_derived.get("saving_throws", {})
                    save_mod = t_saves.get(save_ability,
                                t_derived.get("ability_modifiers", {}).get(save_ability, 0))
                    from services.dnd_rules import roll_dice as _roll_d20
                    d20 = _roll_d20("1d20")["rolls"][0]
                    save_total = d20 + save_mod
                    saved = save_total >= spell_save_dc
                    save_result = {
                        "ability": save_ability, "dc": spell_save_dc,
                        "d20": d20, "modifier": save_mod, "total": save_total, "success": saved,
                    }
                    if saved and half_on_save:
                        dmg_this = dmg_this // 2

                target_enemy2 = next((e for e in enemies if e["id"] == tid), None)
                if target_enemy2:
                    old_hp = target_enemy2.get("hp_current", 0)
                    target_enemy2["hp_current"] = svc.apply_damage(
                        old_hp, dmg_this,
                        target_enemy2.get("derived", {}).get("hp_max", 10),
                    )
                    aoe_results.append({
                        "target_id": tid, "target_name": target_enemy2["name"],
                        "damage": dmg_this, "new_hp": target_enemy2["hp_current"],
                        "save": save_result,
                    })
                else:
                    tc = await db.get(Character, tid)
                    if tc:
                        tc.hp_current = svc.apply_damage(
                            tc.hp_current, dmg_this,
                            (tc.derived or {}).get("hp_max", tc.hp_current),
                        )
                        aoe_results.append({
                            "target_id": tid, "target_name": tc.name,
                            "damage": dmg_this, "new_hp": tc.hp_current,
                            "save": save_result,
                        })
                        cl = await _do_concentration_check(tc, dmg_this, session_id)
                        if cl:
                            conc_logs.append(cl)

            state["enemies"] = enemies
            session.game_state = dict(state); flag_modified(session, "game_state")

        elif spell_type == "heal":
            result_heal, dice_detail = spell_service.resolve_heal(spell_name, spell_level, spell_mod, bonus_healing)
            # Frontend dice override for spell heal
            if req.damage_values:
                result_heal = sum(req.damage_values) + spell_mod
                dice_detail["total"] = result_heal
                if "base_roll" in dice_detail:
                    dice_detail["base_roll"]["rolls"] = req.damage_values
                    dice_detail["base_roll"]["total"] = sum(req.damage_values)
            for tid in target_ids:
                tc = await db.get(Character, tid)
                if tc:
                    tc.hp_current = svc.apply_heal(
                        tc.hp_current, result_heal,
                        (tc.derived or {}).get("hp_max", tc.hp_current),
                    )
                    aoe_results.append({
                        "target_id": tid, "target_name": tc.name,
                        "heal": result_heal, "new_hp": tc.hp_current,
                    })

    # ══ 单目标法术 ══
    else:
        tid = target_ids[0] if target_ids else None
        if spell_type == "damage" and tid:
            result_damage, dice_detail = spell_service.resolve_damage(spell_name, spell_level, spell_mod)
            # Frontend dice override for spell damage
            if req.damage_values:
                result_damage = sum(req.damage_values) + spell_mod
                dice_detail["total"] = result_damage
                if "base_roll" in dice_detail:
                    dice_detail["base_roll"]["rolls"] = req.damage_values
                    dice_detail["base_roll"]["total"] = sum(req.damage_values)
            target_enemy = next((e for e in enemies if e["id"] == tid), None)
            if target_enemy:
                target_enemy["hp_current"] = svc.apply_damage(
                    target_enemy.get("hp_current", 0), result_damage,
                    target_enemy.get("derived", {}).get("hp_max", 10),
                )
                target_new_hp = target_enemy["hp_current"]
                state["enemies"] = enemies
                session.game_state = dict(state); flag_modified(session, "game_state")
            else:
                tc = await db.get(Character, tid)
                if tc:
                    tc.hp_current = svc.apply_damage(
                        tc.hp_current, result_damage,
                        (tc.derived or {}).get("hp_max", tc.hp_current),
                    )
                    target_new_hp = tc.hp_current
                    cl = await _do_concentration_check(tc, result_damage, session_id)
                    if cl:
                        conc_logs.append(cl)

        elif spell_type == "heal" and tid:
            result_heal, dice_detail = spell_service.resolve_heal(spell_name, spell_level, spell_mod, bonus_healing)
            # Frontend dice override for spell heal
            if req.damage_values:
                result_heal = sum(req.damage_values) + spell_mod
                dice_detail["total"] = result_heal
                if "base_roll" in dice_detail:
                    dice_detail["base_roll"]["rolls"] = req.damage_values
                    dice_detail["base_roll"]["total"] = sum(req.damage_values)
            tc = await db.get(Character, tid)
            if tc:
                tc.hp_current = svc.apply_heal(
                    tc.hp_current, result_heal,
                    (tc.derived or {}).get("hp_max", tc.hp_current),
                )
                target_new_hp = tc.hp_current

        elif spell_type in ("control", "utility") and tid:
            # Control/utility spells apply conditions
            _SPELL_CONDITIONS = {
                "Hold Person": ("paralyzed", "wis"),
                "定身术": ("paralyzed", "wis"),
                "Entangle": ("restrained", "str"),
                "纠缠术": ("restrained", "str"),
                "Web": ("restrained", "dex"),
                "蛛网": ("restrained", "dex"),
                "Sleep": ("unconscious", None),
                "睡眠术": ("unconscious", None),
                "Command": ("commanded", "wis"),
                "命令术": ("commanded", "wis"),
                "Faerie Fire": ("faerie_fire", "dex"),
                "妖火": ("faerie_fire", "dex"),
                "Blindness/Deafness": ("blinded", "con"),
                "目盲/耳聋": ("blinded", "con"),
                "Fear": ("frightened", "wis"),
                "恐惧术": ("frightened", "wis"),
                "Silence": ("silenced", None),
                "沉默术": ("silenced", None),
                "Hex": ("hexed", None),
                "妖术": ("hexed", None),
                "Bane": ("baned", "cha"),
                "灾祸术": ("baned", "cha"),
            }
            condition_info = _SPELL_CONDITIONS.get(spell_name, ("affected", spell.get("save")))
            condition_name, save_abil = condition_info

            saved = False
            save_detail = None
            if save_abil:
                target_enemy = next((e for e in enemies if e["id"] == tid), None)
                target_char_ctrl = None if target_enemy else await db.get(Character, tid)
                if target_enemy:
                    t_scores = target_enemy.get("ability_scores", {})
                    t_mod = (t_scores.get(save_abil, 10) - 10) // 2
                elif target_char_ctrl:
                    t_mod = (target_char_ctrl.derived or {}).get("saving_throws", {}).get(save_abil, 0)
                else:
                    t_mod = 0

                from services.dnd_rules import roll_dice as _ctrl_roll
                sr = _ctrl_roll("1d20")["rolls"][0]
                save_total = sr + t_mod
                saved = save_total >= spell_save_dc
                save_detail = {"ability": save_abil, "dc": spell_save_dc, "d20": sr, "modifier": t_mod, "total": save_total, "success": saved}

            if not saved:
                # Apply condition
                target_enemy2 = next((e for e in enemies if e["id"] == tid), None)
                if target_enemy2:
                    conds = target_enemy2.get("conditions", [])
                    if condition_name not in conds:
                        conds.append(condition_name)
                        target_enemy2["conditions"] = conds
                    state["enemies"] = enemies
                    session.game_state = dict(state)
                    flag_modified(session, "game_state")
                else:
                    tc_ctrl = await db.get(Character, tid)
                    if tc_ctrl:
                        conds = list(tc_ctrl.conditions or [])
                        if condition_name not in conds:
                            conds.append(condition_name)
                            tc_ctrl.conditions = conds

            # Also handle spells that do damage + control (like Tasha's Hideous Laughter does 0 damage but applies condition)
            result_damage = 0
            dice_detail = {}

    # ── 专注 ──
    if spell.get("concentration"):
        caster.concentration = spell_name

    # ── 叙事 ──
    level_str = f"（{spell_level}环）" if not is_cantrip else "（戏法）"
    if is_aoe and aoe_results:
        targets_summary = "、".join(r.get("target_name", "?") for r in aoe_results[:4])
        mechanical_narration = (
            f"✨ {caster.name} 施放了【{spell_name}】{level_str}，"
            f"命中 {targets_summary}{'等' if len(aoe_results) > 4 else ''}！"
            + (f"（单目标最高 {result_damage} 点伤害）" if result_damage else "")
            + (f"（每人恢复 {result_heal} HP）" if result_heal else "")
        )
    else:
        mechanical_narration = (
            f"✨ {caster.name} 施放了【{spell_name}】{level_str}"
            + (f"，造成 {result_damage} 点伤害！" if result_damage else "")
            + (f"，恢复 {result_heal} HP！" if result_heal else "")
        )

    # Control spell narration
    if spell_type in ("control", "utility") and 'save_detail' in dir():
        if save_detail:
            saved_str = "通过" if save_detail["success"] else "未通过"
            mechanical_narration += f"\n{save_detail['ability'].upper()} 豁免 DC{save_detail['dc']}: d20={save_detail['d20']}+{save_detail['modifier']}={save_detail['total']} — {saved_str}！"
            if not save_detail["success"]:
                mechanical_narration += f"\n目标陷入【{condition_name}】状态！"

    # LLM vivid narration for spells
    spell_target = targets_summary if (is_aoe and aoe_results) else (target_ids[0] if target_ids else "")
    vivid = await narrate_action(
        actor_name=caster.name,
        actor_class=_normalize_class(caster.char_class),
        target_name=spell_target if isinstance(spell_target, str) else str(spell_target),
        action_type="spell",
        spell_name=spell_name,
        damage=result_damage,
        heal_amount=result_heal,
        damage_type=spell.get("damage_type", ""),
    )
    narration = vivid if vivid else mechanical_narration

    db.add(GameLog(
        session_id=session_id,
        role="player" if caster.is_player else f"companion_{caster.name}",
        content=narration,
        log_type="combat",
        dice_result={
            "dice": dice_detail, "damage": result_damage, "heal": result_heal,
            "aoe": aoe_results,
        },
    ))
    for cl in conc_logs:
        db.add(cl)

    # ── 标记行动已用 ──
    spell_ts = _get_ts(combat_obj, caster_entity_id)
    spell_ts.pop("pending_spell", None)
    if not is_cantrip:
        spell_ts["action_used"] = True
    _save_ts(combat_obj, caster_entity_id, spell_ts)

    # ── 野蛮魔法涌动检测（Wild Magic Surge）──
    wild_magic_surge = None
    wild_magic_check = None
    if not is_cantrip:
        caster_sub_effects = (caster.derived or {}).get("subclass_effects", {})
        if caster_sub_effects.get("wild_magic"):
            from services.dnd_rules import roll_dice as _roll_surge, roll_wild_magic_surge

            forced_surge = (caster.class_resources or {}).get("tides_of_chaos_used", False)

            if forced_surge:
                # 使用混沌之潮后施法必定触发涌动
                wild_magic_surge = roll_wild_magic_surge()
                wild_magic_check = {"d20": "自动", "triggered": True, "forced": True,
                                    "surge_roll": wild_magic_surge.get("index", 0) + 1}  # d20 table index
                surge_narration = f"🌀 混沌反噬！混沌之潮的代价降临——{wild_magic_surge['effect']}"
                narration += f"\n\n{surge_narration}"
                db.add(GameLog(
                    session_id=session_id, role="system",
                    content=surge_narration, log_type="system",
                ))
                # 重置混沌之潮（可以再次使用）
                class_res = dict(caster.class_resources or {})
                class_res["tides_of_chaos_used"] = False
                caster.class_resources = class_res
            else:
                # 正常检测：掷 d20，1 则触发
                surge_check = _roll_surge("1d20")
                d20_val = surge_check["rolls"][0]
                if d20_val == 1:
                    wild_magic_surge = roll_wild_magic_surge()
                    wild_magic_check = {"d20": d20_val, "triggered": True, "forced": False,
                                        "surge_roll": wild_magic_surge.get("index", 0) + 1}
                    surge_narration = f"🌀 野蛮魔法涌动！d20={d20_val}——{caster.name} 体内的混沌能量失控！{wild_magic_surge['effect']}"
                    narration += f"\n\n{surge_narration}"
                    db.add(GameLog(
                        session_id=session_id, role="system",
                        content=surge_narration, log_type="system",
                        dice_result={"type": "wild_magic_surge", "d20": d20_val, **wild_magic_surge},
                    ))
                else:
                    # 未触发，但仍告知玩家检测发生了
                    wild_magic_check = {"d20": d20_val, "triggered": False, "forced": False}
                    db.add(GameLog(
                        session_id=session_id, role="system",
                        content=f"🎲 野蛮魔法检测: d20={d20_val}（未触发涌动，需要1）",
                        log_type="system",
                    ))

            # 应用有机械效果的涌动
            if wild_magic_surge:
                mech = wild_magic_surge.get("mechanical", {})
                if mech.get("type") == "heal":
                    heal_roll = _roll_surge(mech["dice"])
                    caster.hp_current = min(
                        (caster.derived or {}).get("hp_max", caster.hp_current),
                        caster.hp_current + heal_roll["total"],
                    )
                elif mech.get("type") == "condition":
                    conds = list(caster.conditions or [])
                    conds.append(mech["condition"])
                    caster.conditions = conds

    # ── 检查战斗结束 ──
    player_check = await db.get(Character, session.player_character_id)
    combat_over, outcome = svc.check_combat_over(enemies, player_check.hp_current if player_check else 0)
    if combat_over:
        session.combat_active = False
        # 清理战斗状态记录，防止下次战斗残留旧数据
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs: await db.delete(_old_cs)
        except Exception: pass

    await db.commit()

    return {
        "narration": narration,
        "damage": result_damage,
        "heal": result_heal,
        "target_id": target_ids[0] if target_ids else None,
        "target_new_hp": target_new_hp,
        "aoe_results": aoe_results,
        "remaining_slots": new_slots,
        "dice_detail": dice_detail,
        "dice_result": {"total": result_damage or result_heal or 0},
        "turn_state": spell_ts,
        "is_concentration": spell.get("concentration", False),
        "is_aoe": is_aoe,
        "combat_over": combat_over,
        "outcome": outcome,
        "wild_magic_surge": wild_magic_surge,
        "wild_magic_check": wild_magic_check,
    }


@router.post("/combat/{session_id}/spell")
async def cast_spell(session_id: str, req: SpellRequest, db: AsyncSession = Depends(get_db)):
    """
    施放法术（消耗法术位，计算升环效果）
    - 单目标：传 target_id
    - AoE 多目标：传 target_ids（空列表 = 命中所有存活敌人）
    - AoE 带豁免：每个目标各自豁免，成功者伤害减半
    """
    session = await get_session_or_404(session_id, db)

    spell = spell_service.get(req.spell_name)
    if not spell:
        raise HTTPException(400, f"未知法术：{req.spell_name}")

    err = spell_service.validate_slot_level(req.spell_name, req.spell_level)
    if err:
        raise HTTPException(400, err)

    caster = await db.get(Character, req.caster_id)
    if not caster:
        raise HTTPException(404, "施法者不存在")

    # ── 检查行动配额 ──────────────────────────────────────
    combat_result2 = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat_obj     = combat_result2.scalars().first()
    spell_ts       = _get_ts(combat_obj, req.caster_id) if combat_obj else dict(_DEFAULT_TS)
    if spell_ts["action_used"] and spell["level"] != 0:
        raise HTTPException(400, "本回合行动已用尽")

    # ── 消耗法术位 ────────────────────────────────────────
    is_cantrip = spell["level"] == 0
    if not is_cantrip:
        new_slots, slot_err = spell_service.consume_slot(dict(caster.spell_slots or {}), req.spell_level)
        if slot_err:
            raise HTTPException(400, slot_err)
        caster.spell_slots = new_slots
    else:
        new_slots = caster.spell_slots or {}

    # ── 施法属性 ──────────────────────────────────────────
    derived        = caster.derived or {}
    spell_abil     = derived.get("spell_ability")
    spell_mod      = derived.get("ability_modifiers", {}).get(spell_abil or "", 0) if spell_abil else 0
    spell_save_dc  = derived.get("spell_save_dc", 13)
    bonus_healing  = derived.get("bonus_healing", False)

    state   = session.game_state or {}
    enemies = list(state.get("enemies", []))

    result_damage  = 0
    result_heal    = 0
    dice_detail    = {}
    target_new_hp  = None        # 单目标时使用
    aoe_results    = []          # AoE 时每个目标的结果
    conc_logs      = []          # 需要写入的专注检定日志

    is_aoe = spell.get("aoe", False)

    # ══ AoE 法术 ══════════════════════════════════════════
    if is_aoe:
        # 伤害类 AoE
        if spell["type"] == "damage":
            result_damage, dice_detail = spell_service.resolve_damage(req.spell_name, req.spell_level, spell_mod)
            # 确定目标列表
            raw_ids = req.target_ids if req.target_ids is not None else (
                [req.target_id] if req.target_id else []
            )
            # target_ids 为空 → 命中所有存活敌人
            if not raw_ids:
                raw_ids = [e["id"] for e in enemies if e.get("hp_current", 0) > 0]

            save_ability = spell.get("save")
            half_on_save = spell.get("half_on_save", True)

            for tid in raw_ids:
                dmg_this = result_damage
                save_result = None

                # 如果法术有豁免，逐目标豁免检定
                if save_ability:
                    target_enemy = next((e for e in enemies if e["id"] == tid), None)
                    target_char  = None if target_enemy else await db.get(Character, tid)

                    t_derived = (target_enemy.get("derived", {}) if target_enemy
                                 else (target_char.derived or {} if target_char else {}))
                    t_saves   = t_derived.get("saving_throws", {})
                    save_mod  = t_saves.get(save_ability,
                                t_derived.get("ability_modifiers", {}).get(save_ability, 0))

                    from services.dnd_rules import roll_dice as _roll_d20
                    d20 = _roll_d20("1d20")["rolls"][0]
                    save_total = d20 + save_mod
                    saved = save_total >= spell_save_dc
                    save_result = {
                        "ability": save_ability, "dc": spell_save_dc,
                        "d20": d20, "modifier": save_mod, "total": save_total, "success": saved,
                    }
                    if saved and half_on_save:
                        dmg_this = dmg_this // 2

                # 更新 HP
                target_enemy2 = next((e for e in enemies if e["id"] == tid), None)
                if target_enemy2:
                    old_hp = target_enemy2.get("hp_current", 0)
                    target_enemy2["hp_current"] = svc.apply_damage(
                        old_hp, dmg_this,
                        target_enemy2.get("derived", {}).get("hp_max", 10),
                    )
                    aoe_results.append({
                        "target_id":   tid,
                        "target_name": target_enemy2["name"],
                        "damage":      dmg_this,
                        "new_hp":      target_enemy2["hp_current"],
                        "save":        save_result,
                    })
                else:
                    tc = await db.get(Character, tid)
                    if tc:
                        tc.hp_current = svc.apply_damage(
                            tc.hp_current, dmg_this,
                            (tc.derived or {}).get("hp_max", tc.hp_current),
                        )
                        aoe_results.append({
                            "target_id":   tid,
                            "target_name": tc.name,
                            "damage":      dmg_this,
                            "new_hp":      tc.hp_current,
                            "save":        save_result,
                        })
                        cl = await _do_concentration_check(tc, dmg_this, session_id)
                        if cl:
                            conc_logs.append(cl)

            state["enemies"] = enemies
            session.game_state = dict(state); flag_modified(session, "game_state")

        # 치유류 AoE（群体治愈）
        elif spell["type"] == "heal":
            result_heal, dice_detail = spell_service.resolve_heal(req.spell_name, req.spell_level, spell_mod, bonus_healing)
            companion_ids = (session.game_state or {}).get("companion_ids", [])
            heal_ids = req.target_ids if req.target_ids else (
                [session.player_character_id] + companion_ids
            )
            for tid in heal_ids:
                tc = await db.get(Character, tid)
                if tc:
                    tc.hp_current = svc.apply_heal(
                        tc.hp_current, result_heal,
                        (tc.derived or {}).get("hp_max", tc.hp_current),
                    )
                    aoe_results.append({
                        "target_id": tid, "target_name": tc.name,
                        "heal": result_heal, "new_hp": tc.hp_current,
                    })

    # ══ 单目标法术 ════════════════════════════════════════
    else:
        if spell["type"] == "damage" and (req.target_id or req.target_ids):
            tid = req.target_id or (req.target_ids[0] if req.target_ids else None)
            if tid:
                result_damage, dice_detail = spell_service.resolve_damage(req.spell_name, req.spell_level, spell_mod)
                target_enemy = next((e for e in enemies if e["id"] == tid), None)
                if target_enemy:
                    target_enemy["hp_current"] = svc.apply_damage(
                        target_enemy.get("hp_current", 0), result_damage,
                        target_enemy.get("derived", {}).get("hp_max", 10),
                    )
                    target_new_hp    = target_enemy["hp_current"]
                    state["enemies"] = enemies
                    session.game_state = dict(state); flag_modified(session, "game_state")
                else:
                    tc = await db.get(Character, tid)
                    if tc:
                        tc.hp_current = svc.apply_damage(
                            tc.hp_current, result_damage,
                            (tc.derived or {}).get("hp_max", tc.hp_current),
                        )
                        target_new_hp = tc.hp_current
                        cl = await _do_concentration_check(tc, result_damage, session_id)
                        if cl:
                            conc_logs.append(cl)

        elif spell["type"] == "heal" and (req.target_id or req.target_ids):
            tid = req.target_id or (req.target_ids[0] if req.target_ids else None)
            if tid:
                result_heal, dice_detail = spell_service.resolve_heal(req.spell_name, req.spell_level, spell_mod, bonus_healing)
                tc = await db.get(Character, tid)
                if tc:
                    tc.hp_current = svc.apply_heal(
                        tc.hp_current, result_heal,
                        (tc.derived or {}).get("hp_max", tc.hp_current),
                    )
                    target_new_hp = tc.hp_current

    # ── 专注：施法者开始专注 ──────────────────────────────
    if spell.get("concentration"):
        caster.concentration = req.spell_name

    # ── 组装叙事 ──────────────────────────────────────────
    level_str = f"（{req.spell_level}环）" if not is_cantrip else "（戏法）"
    if is_aoe and aoe_results:
        targets_summary = "、".join(r.get("target_name", "?") for r in aoe_results[:4])
        narration = (
            f"✨ {caster.name} 施放了【{req.spell_name}】{level_str}，"
            f"命中 {targets_summary}{'等' if len(aoe_results) > 4 else ''}！"
            + (f"（单目标最高 {result_damage} 点伤害）" if result_damage else "")
            + (f"（每人恢复 {result_heal} HP）" if result_heal else "")
        )
    else:
        narration = (
            f"✨ {caster.name} 施放了【{req.spell_name}】{level_str}"
            + (f"，造成 {result_damage} 点伤害！" if result_damage else "")
            + (f"，恢复 {result_heal} HP！" if result_heal else "")
        )

    db.add(GameLog(
        session_id  = session_id,
        role        = "player" if caster.is_player else f"companion_{caster.name}",
        content     = narration,
        log_type    = "combat",
        dice_result = {
            "dice": dice_detail, "damage": result_damage, "heal": result_heal,
            "aoe": aoe_results,
        },
    ))
    for cl in conc_logs:
        db.add(cl)

    # ── 标记行动已用，不推进回合 ─────────────────────────────
    if combat_obj:
        if not is_cantrip:
            spell_ts["action_used"] = True
        _save_ts(combat_obj, req.caster_id, spell_ts)

    # ── 检查战斗是否结束 ──────────────────────────────────
    player_check2        = await db.get(Character, session.player_character_id)
    combat_over, outcome = svc.check_combat_over(enemies, player_check2.hp_current if player_check2 else 0)
    if combat_over:
        session.combat_active = False
        # 清理战斗状态记录，防止下次战斗残留旧数据
        try:
            _old_cs = (await db.execute(select(CombatState).where(CombatState.session_id == session_id))).scalars().first()
            if _old_cs: await db.delete(_old_cs)
        except Exception: pass

    round_number = combat_obj.round_number if combat_obj else 1
    next_index   = combat_obj.current_turn_index if combat_obj else 0

    await db.commit()
    return {
        "narration":        narration,
        "damage":           result_damage,
        "heal":             result_heal,
        "target_id":        req.target_id,
        "target_new_hp":    target_new_hp,
        "aoe_results":      aoe_results,
        "remaining_slots":  new_slots,
        "dice_detail":      dice_detail,
        "dice_result":      {"total": result_damage or result_heal or 0},
        "turn_state":       spell_ts,
        "next_turn_index":  next_index,
        "round_number":     round_number,
        "is_concentration": spell.get("concentration", False),
        "is_aoe":           is_aoe,
        "combat_over":      combat_over,
        "outcome":          outcome,
    }


# ── 状态条件管理 ──────────────────────────────────────────

@router.post("/combat/{session_id}/condition/add")
async def add_condition(
    session_id: str,
    req: ConditionRequest,
    db: AsyncSession = Depends(get_db),
):
    """向战斗实体添加状态条件（角色或敌人）"""
    session = await get_session_or_404(session_id, db)
    state   = session.game_state or {}

    rounds_str = f"（{req.rounds}回合）" if req.rounds else "（永久）"
    if req.is_enemy:
        enemies = list(state.get("enemies", []))
        enemy = next((e for e in enemies if e["id"] == req.entity_id), None)
        if not enemy:
            raise HTTPException(404, f"敌人 {req.entity_id} 不存在")
        conditions = list(enemy.get("conditions", []))
        if req.condition not in conditions:
            conditions.append(req.condition)
        if req.rounds is not None:
            durations = dict(enemy.get("condition_durations", {}))
            durations[req.condition] = req.rounds
            enemy["condition_durations"] = durations
        enemy["conditions"] = conditions
        state["enemies"] = enemies
        session.game_state = dict(state); flag_modified(session, "game_state")
    else:
        char = await db.get(Character, req.entity_id)
        if not char:
            raise HTTPException(404, "角色不存在")
        conditions = list(char.conditions or [])
        if req.condition not in conditions:
            conditions.append(req.condition)
        char.conditions = conditions
        if req.rounds is not None:
            durations = dict(char.condition_durations or {})
            durations[req.condition] = req.rounds
            char.condition_durations = durations

    db.add(GameLog(
        session_id = session_id,
        role       = "system",
        content    = f"🔴 {'敌人' if req.is_enemy else req.entity_id} 获得状态：{req.condition}{rounds_str}",
        log_type   = "system",
    ))
    await db.commit()
    return {"entity_id": req.entity_id, "conditions": conditions}


@router.post("/combat/{session_id}/condition/remove")
async def remove_condition(
    session_id: str,
    req: ConditionRequest,
    db: AsyncSession = Depends(get_db),
):
    """从战斗实体移除状态条件"""
    session = await get_session_or_404(session_id, db)
    state   = session.game_state or {}

    if req.is_enemy:
        enemies = list(state.get("enemies", []))
        enemy = next((e for e in enemies if e["id"] == req.entity_id), None)
        if not enemy:
            raise HTTPException(404, f"敌人 {req.entity_id} 不存在")
        conditions = [c for c in enemy.get("conditions", []) if c != req.condition]
        enemy["conditions"] = conditions
        state["enemies"] = enemies
        session.game_state = dict(state); flag_modified(session, "game_state")
    else:
        char = await db.get(Character, req.entity_id)
        if not char:
            raise HTTPException(404, "角色不存在")
        conditions = [c for c in (char.conditions or []) if c != req.condition]
        char.conditions = conditions

    db.add(GameLog(
        session_id = session_id,
        role       = "system",
        content    = f"🟢 {'敌人' if req.is_enemy else req.entity_id} 解除状态：{req.condition}",
        log_type   = "system",
    ))
    await db.commit()
    return {"entity_id": req.entity_id, "conditions": conditions}


# ── 濒死豁免 ──────────────────────────────────────────────

@router.post("/combat/{session_id}/death-save")
async def death_saving_throw(
    session_id: str,
    req: DeathSaveRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    濒死豁免检定（5e PHB p.197）
    - HP = 0 的角色每回合投 d20
    - 20（自然）：立即稳定并恢复1HP
    - 1（自然）：记为2次失败
    - 10+：成功
    - <10：失败
    - 3成功 → 稳定（stable=True，停止豁免）
    - 3失败 → 死亡（角色被移除战斗）
    """
    session = await get_session_or_404(session_id, db)
    char = await db.get(Character, req.character_id)
    if not char:
        raise HTTPException(404, "角色不存在")
    if char.hp_current > 0:
        raise HTTPException(400, "该角色 HP > 0，无需进行濒死豁免")

    saves = dict(char.death_saves or {"successes": 0, "failures": 0, "stable": False})
    if saves.get("stable"):
        raise HTTPException(400, "该角色已稳定，无需再投")

    d20    = req.d20_value if req.d20_value is not None else random.randint(1, 20)
    result = {}

    if d20 == 20:
        # 自然20：立即稳定 + 1HP
        char.hp_current    = 1
        saves["stable"]    = True
        saves["successes"] = 3
        char.death_saves   = saves
        msg = f"🌟 {char.name} 自然20！从死亡边缘爬回，恢复1HP！"
        result = {"d20": d20, "outcome": "revive", "hp": 1}
    elif d20 == 1:
        # 自然1：2次失败
        saves["failures"] = min(3, saves.get("failures", 0) + 2)
        char.death_saves  = saves
        if saves["failures"] >= 3:
            msg = f"💀 {char.name} 自然1！两次失败，已阵亡…"
            result = {"d20": d20, "outcome": "dead", "failures": saves["failures"]}
        else:
            msg = f"😱 {char.name} 自然1！失败计数 +2（{saves['failures']}/3）"
            result = {"d20": d20, "outcome": "failure", "failures": saves["failures"]}
    elif d20 >= 10:
        # 成功
        saves["successes"] = saves.get("successes", 0) + 1
        if saves["successes"] >= 3:
            saves["stable"] = True
            msg = f"✅ {char.name} 濒死豁免成功 3/3！已稳定。"
            result = {"d20": d20, "outcome": "stable", "successes": saves["successes"]}
        else:
            msg = f"✅ {char.name} 濒死豁免成功（{saves['successes']}/3）"
            result = {"d20": d20, "outcome": "success", "successes": saves["successes"]}
        char.death_saves = saves
    else:
        # 失败
        saves["failures"] = saves.get("failures", 0) + 1
        if saves["failures"] >= 3:
            msg = f"💀 {char.name} 濒死豁免失败 3/3，已阵亡…"
            result = {"d20": d20, "outcome": "dead", "failures": saves["failures"]}
        else:
            msg = f"❌ {char.name} 濒死豁免失败（{saves['failures']}/3）"
            result = {"d20": d20, "outcome": "failure", "failures": saves["failures"]}
        char.death_saves = saves

    db.add(GameLog(
        session_id  = session_id,
        role        = "system",
        content     = msg,
        log_type    = "dice",
        dice_result = result,
    ))
    await db.commit()
    return {
        "character_id": req.character_id,
        "character_name": char.name,
        "death_saves": saves,
        **result,
    }



# ── 战技（Battle Master Maneuvers）──────────────────────────

@router.post("/combat/{session_id}/maneuver")
async def use_maneuver(session_id: str, req: ManeuverRequest, db: AsyncSession = Depends(get_db)):
    """
    Battle Master maneuver: consume 1 superiority die and apply effect.
    Maneuvers: precision, trip, disarm, riposte, menacing, pushing, goading
    """
    session = await get_session_or_404(session_id, db)
    result_db = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = result_db.scalars().first()
    if not combat:
        raise HTTPException(404, "当前没有进行中的战斗")

    turn_order = combat.turn_order or []
    if not turn_order:
        raise HTTPException(400, "无回合顺序")

    current_entry = turn_order[combat.current_turn_index % len(turn_order)]
    actor_id = str(current_entry.get("character_id", ""))

    # Verify actor is a Battle Master
    actor_char = await db.get(Character, actor_id)
    if not actor_char:
        raise HTTPException(404, "当前行动角色不存在")
    derived = actor_char.derived or {}
    sub_effects = derived.get("subclass_effects", {})
    if not sub_effects.get("battle_master"):
        raise HTTPException(400, "当前角色不是战争大师，无法使用战技")

    # Check superiority dice remaining
    class_resources = dict(actor_char.class_resources or {})
    sd_remaining = class_resources.get("superiority_dice_remaining", 0)
    if sd_remaining <= 0:
        raise HTTPException(400, "优势骰已耗尽（短休后恢复）")

    # Validate maneuver name
    valid_maneuvers = sub_effects.get("maneuvers", [])
    if req.maneuver_name not in valid_maneuvers:
        raise HTTPException(400, f"无效战技: {req.maneuver_name}，可用: {valid_maneuvers}")

    # Consume 1 superiority die
    class_resources["superiority_dice_remaining"] = sd_remaining - 1
    actor_char.class_resources = class_resources

    # Roll superiority die
    sd_die = sub_effects.get("superiority_die", "d8")
    sd_roll = roll_dice(sd_die)
    sd_value = sd_roll["total"]

    # Resolve target
    game_state = session.game_state or {}
    enemies = game_state.get("enemies", [])
    target_enemy = None
    target_char = None
    target_name = "Unknown"
    target_is_enemy = False

    for e in enemies:
        if str(e.get("id")) == req.target_id:
            target_enemy = e
            target_name = e.get("name", "Enemy")
            target_is_enemy = True
            break
    if not target_enemy:
        target_char = await db.get(Character, req.target_id)
        if target_char:
            target_name = target_char.name

    maneuver_result = {
        "maneuver": req.maneuver_name,
        "superiority_die_roll": sd_value,
        "superiority_die": sd_die,
        "dice_remaining": sd_remaining - 1,
        "actor": actor_char.name,
        "target": target_name,
    }

    actor_derived = derived
    prof = actor_derived.get("proficiency_bonus", 2)
    # Maneuver save DC = 8 + prof + max(STR, DEX)
    spell_dc = 8 + prof + max(
        actor_derived.get("ability_modifiers", {}).get("str", 0),
        actor_derived.get("ability_modifiers", {}).get("dex", 0),
    )

    if req.maneuver_name == "precision":
        maneuver_result["effect"] = f"下次攻击骰+{sd_value}"
        maneuver_result["attack_bonus"] = sd_value
        msg = f"⚔️ {actor_char.name} 使用精准打击，攻击骰+{sd_value}"

    elif req.maneuver_name == "trip":
        save_roll = random.randint(1, 20)
        target_str_mod = 0
        if target_enemy:
            t_scores = target_enemy.get("ability_scores", {})
            target_str_mod = (t_scores.get("str", 10) - 10) // 2
        elif target_char:
            target_str_mod = (target_char.derived or {}).get("ability_modifiers", {}).get("str", 0)
        save_total = save_roll + target_str_mod
        tripped = save_total < spell_dc
        maneuver_result["save_roll"] = save_roll
        maneuver_result["save_total"] = save_total
        maneuver_result["dc"] = spell_dc
        maneuver_result["tripped"] = tripped
        maneuver_result["extra_damage"] = sd_value
        if tripped:
            msg = f"⚔️ {actor_char.name} 使用绊摔攻击！{target_name} 摔倒（俯卧），额外伤害{sd_value}"
            if target_enemy:
                t_conds = target_enemy.get("conditions", [])
                if "prone" not in t_conds:
                    t_conds.append("prone")
                    target_enemy["conditions"] = t_conds
                    session.game_state = game_state
            elif target_char:
                t_conds = list(target_char.conditions or [])
                if "prone" not in t_conds:
                    t_conds.append("prone")
                    target_char.conditions = t_conds
        else:
            msg = f"⚔️ {actor_char.name} 使用绊摔攻击，{target_name} 站稳了！额外伤害{sd_value}"

    elif req.maneuver_name == "disarm":
        save_roll = random.randint(1, 20)
        target_str_mod = 0
        if target_enemy:
            t_scores = target_enemy.get("ability_scores", {})
            target_str_mod = (t_scores.get("str", 10) - 10) // 2
        elif target_char:
            target_str_mod = (target_char.derived or {}).get("ability_modifiers", {}).get("str", 0)
        save_total = save_roll + target_str_mod
        disarmed = save_total < spell_dc
        maneuver_result["save_roll"] = save_roll
        maneuver_result["save_total"] = save_total
        maneuver_result["dc"] = spell_dc
        maneuver_result["disarmed"] = disarmed
        if disarmed:
            msg = f"⚔️ {actor_char.name} 使用缴械打击！{target_name} 武器脱手！"
        else:
            msg = f"⚔️ {actor_char.name} 使用缴械打击，{target_name} 握紧了武器"

    elif req.maneuver_name == "riposte":
        maneuver_result["extra_damage"] = sd_value
        maneuver_result["effect"] = "反击攻击"
        msg = f"⚔️ {actor_char.name} 使用反击！额外伤害+{sd_value}"

    elif req.maneuver_name == "menacing":
        save_roll = random.randint(1, 20)
        target_wis_mod = 0
        if target_enemy:
            t_scores = target_enemy.get("ability_scores", {})
            target_wis_mod = (t_scores.get("wis", 10) - 10) // 2
        elif target_char:
            target_wis_mod = (target_char.derived or {}).get("ability_modifiers", {}).get("wis", 0)
        save_total = save_roll + target_wis_mod
        frightened = save_total < spell_dc
        maneuver_result["save_roll"] = save_roll
        maneuver_result["save_total"] = save_total
        maneuver_result["dc"] = spell_dc
        maneuver_result["frightened"] = frightened
        maneuver_result["extra_damage"] = sd_value
        if frightened:
            msg = f"⚔️ {actor_char.name} 使用威吓攻击！{target_name} 陷入恐惧，额外伤害{sd_value}"
            if target_enemy:
                t_conds = target_enemy.get("conditions", [])
                if "frightened" not in t_conds:
                    t_conds.append("frightened")
                    target_enemy["conditions"] = t_conds
                    session.game_state = game_state
            elif target_char:
                t_conds = list(target_char.conditions or [])
                if "frightened" not in t_conds:
                    t_conds.append("frightened")
                    target_char.conditions = t_conds
        else:
            msg = f"⚔️ {actor_char.name} 使用威吓攻击，{target_name} 不为所动！额外伤害{sd_value}"

    elif req.maneuver_name == "pushing":
        maneuver_result["push_distance"] = 15
        maneuver_result["extra_damage"] = sd_value
        msg = f"⚔️ {actor_char.name} 使用推击！{target_name} 被推开15尺，额外伤害{sd_value}"

    elif req.maneuver_name == "goading":
        save_roll = random.randint(1, 20)
        target_wis_mod = 0
        if target_enemy:
            t_scores = target_enemy.get("ability_scores", {})
            target_wis_mod = (t_scores.get("wis", 10) - 10) // 2
        elif target_char:
            target_wis_mod = (target_char.derived or {}).get("ability_modifiers", {}).get("wis", 0)
        save_total = save_roll + target_wis_mod
        goaded = save_total < spell_dc
        maneuver_result["save_roll"] = save_roll
        maneuver_result["save_total"] = save_total
        maneuver_result["dc"] = spell_dc
        maneuver_result["goaded"] = goaded
        maneuver_result["extra_damage"] = sd_value
        if goaded:
            msg = f"⚔️ {actor_char.name} 使用激怒攻击！{target_name} 攻击其他目标时有劣势，额外伤害{sd_value}"
        else:
            msg = f"⚔️ {actor_char.name} 使用激怒攻击，{target_name} 不受影响！额外伤害{sd_value}"

    else:
        msg = f"⚔️ {actor_char.name} 使用了未知战技"

    # Log
    db.add(GameLog(
        session_id  = session_id,
        role        = "system",
        content     = msg,
        log_type    = "combat",
        dice_result = maneuver_result,
    ))

    flag_modified(actor_char, "class_resources")
    if target_is_enemy:
        flag_modified(session, "game_state")

    await db.commit()
    # Add dice_roll for frontend animation
    sd_faces = int(sd_die.replace("d", "")) if sd_die.startswith("d") else 8
    maneuver_result["dice_roll"] = {"faces": sd_faces, "result": sd_value, "label": f"战技·{req.maneuver_name}"}
    maneuver_result["narration"] = msg
    return maneuver_result
