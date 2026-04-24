"""
api.combat._shared — 战斗模块的共享常量 / 单例 / 辅助函数。

这里定义的每样东西被多个端点模块调用。改动前请用 grep 确认影响范围。
"""
import uuid
import random
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, Session, GameLog, CombatState
from api.deps import serialize_combat, broadcast_to_session
from services.combat_service import CombatService
from services.dnd_rules import _normalize_class
from services.character_roster import CharacterRoster

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


# ── 多人联机：战斗状态广播辅助 ──────────────────────────
# 在 commit 后调用，向房间所有 WS 连接广播一次最新战斗状态。
# 单人模式静默跳过。

async def _broadcast_combat(session: Session, combat: CombatState | None, event_type: str = "combat_update", **extra) -> None:
    if not session.is_multiplayer:
        return
    payload = {"type": event_type}
    if combat is not None:
        payload["combat"] = serialize_combat(combat)
        # 当前回合归属（用 user_id 给前端做 owner 判断）
        if combat.turn_order:
            try:
                cur = combat.turn_order[combat.current_turn_index or 0]
                payload["current_entity_id"] = cur.get("character_id") if isinstance(cur, dict) else None
            except (IndexError, AttributeError):
                pass
    payload.update(extra)
    await broadcast_to_session(session, payload)


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
        _roster = CharacterRoster(db, session)
        for companion in await _roster.companions_alive():
            cid = companion.id
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

