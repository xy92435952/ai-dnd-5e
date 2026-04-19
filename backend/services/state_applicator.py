"""
StateApplicator — 将 WF3 返回的 state_delta 应用到数据库
==========================================================
职责：
  - 解析 DM Agent 返回的 state_delta JSON
  - 更新 Character（HP / 条件 / 法术位 / 濒死豁免 / 专注）
  - 更新 CombatState 中的敌人状态（HP / 条件 / 死亡）
  - 处理战斗触发（combat_trigger）和战斗结束（combat_end）
  - 将所有变化写入 GameLog

设计原则：
  - 所有 HP 变化都做边界校验（不超 max，不低于 0）
  - 遇到找不到的实体 ID 时记录警告，不抛异常
  - 返回 ApplyResult 供 API 层决定下一步（触发战斗/结束战斗/继续）
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models.character import Character
from models.session import Session, CombatState, GameLog
from schemas.game_schemas import GameState, EnemyState

logger = logging.getLogger(__name__)


@dataclass
class ApplyResult:
    """apply() 的返回值，供 API 层决策用。"""
    narrative:          str = ""
    action_type:        str = "unknown"
    companion_reactions:str = ""
    dice_display:       list = field(default_factory=list)
    player_choices:     list = field(default_factory=list)
    needs_check:        dict = field(default_factory=lambda: {"required": False})
    combat_triggered:   bool = False          # 需要初始化战斗
    combat_ended:       bool = False          # 需要清理战斗
    combat_end_result:  Optional[str] = None  # "victory" / "defeat" / None
    initial_enemies:    list = field(default_factory=list)  # 触发战斗时的初始敌人列表
    errors:             list = field(default_factory=list)


class StateApplicator:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─────────────────────────────────────────────
    # 主入口
    # ─────────────────────────────────────────────

    async def apply(
        self,
        session: Session,
        result_json: str,
        characters: list[Character],
        combat_state: Optional[CombatState] = None,
    ) -> ApplyResult:
        """
        解析 WF3 返回的完整 JSON，应用所有状态变化。

        Args:
            session:       当前游戏会话
            result_json:   WF3 返回的 result 字段（完整 JSON 字符串）
            characters:    本次会话的所有角色（玩家+队友）
            combat_state:  当前战斗状态（战斗中）或 None

        Returns:
            ApplyResult，包含叙述文本和触发/结束战斗标志
        """
        ar = ApplyResult()

        try:
            data = json.loads(result_json)
        except Exception as e:
            ar.errors.append(f"result JSON 解析失败: {e}")
            ar.narrative = "（DM 回应解析失败，请重试）"
            return ar

        # 提取展示字段
        ar.narrative           = data.get("narrative", "")
        ar.action_type         = data.get("action_type", "unknown")
        ar.companion_reactions = data.get("companion_reactions", "")
        ar.dice_display        = data.get("dice_results", [])
        ar.player_choices      = data.get("player_choices", [])
        ar.needs_check         = data.get("needs_check", {"required": False})

        delta = data.get("state_delta", {})

        # 建立角色索引（id → Character 对象）
        char_map = {str(c.id): c for c in characters}

        # ── 应用角色状态变化 ──
        for char_delta in delta.get("characters", []):
            await self._apply_character_delta(char_delta, char_map, session.id)

        # ── 应用 AI 回合中的状态变化 ──
        for ai_turn in data.get("ai_turns", []):
            sub_delta = ai_turn.get("state_delta", {})
            for char_delta in sub_delta.get("characters", []):
                await self._apply_character_delta(char_delta, char_map, session.id)
            if combat_state:
                for enemy_delta in sub_delta.get("enemies", []):
                    self._apply_enemy_delta(enemy_delta, session)
            ar.dice_display.extend(ai_turn.get("dice_results", []))

        # ── 应用敌人状态变化 ──
        if combat_state:
            for enemy_delta in delta.get("enemies", []):
                self._apply_enemy_delta(enemy_delta, session)

        # ── 金币变化 ──
        for gold_delta in delta.get("gold_changes", []):
            await self._apply_gold_change(gold_delta, char_map)

        # ── 位置变化（自然语言战斗中的移动）──
        if combat_state:
            for pc in delta.get("position_changes", []):
                eid = str(pc.get("id", ""))
                new_pos = pc.get("position")
                if eid and new_pos and isinstance(new_pos, dict):
                    positions = dict(combat_state.entity_positions or {})
                    x, y = new_pos.get("x", 0), new_pos.get("y", 0)
                    if 0 <= x < 20 and 0 <= y < 12:
                        positions[eid] = {"x": x, "y": y}
                        combat_state.entity_positions = positions
                        logger.info(f"位置变化: {eid[:8]} → ({x},{y}) | {pc.get('reason','')}")

        # ── 战斗触发 ──
        if delta.get("combat_trigger"):
            ar.combat_triggered  = True
            ar.initial_enemies   = delta.get("initial_enemies", [])

        # ── 战斗结束 ──
        if delta.get("combat_end"):
            ar.combat_ended     = True
            ar.combat_end_result = delta.get("combat_end_result")
            session.combat_active = False

        # ── 场景推进 ──
        if delta.get("scene_advance") and delta.get("new_scene_hint"):
            session.current_scene = delta["new_scene_hint"]

        # ── 场景氛围（v0.10）──
        scene_vibe = delta.get("scene_vibe")
        if scene_vibe and isinstance(scene_vibe, dict):
            gs = dict(session.game_state or {})
            gs["scene_vibe"] = {
                "location": scene_vibe.get("location"),
                "time_of_day": scene_vibe.get("time_of_day"),
                "tension": scene_vibe.get("tension"),
            }
            session.game_state = gs
            flag_modified(session, "game_state")

        # ── 线索追加（v0.10）──
        clues_add = delta.get("clues_add", [])
        if clues_add and isinstance(clues_add, list):
            cs = dict(session.campaign_state or {})
            clues = list(cs.get("clues", []))
            from datetime import datetime
            now_iso = datetime.utcnow().isoformat() + "Z"
            for clue in clues_add:
                if not isinstance(clue, dict) or not clue.get("text"):
                    continue
                clues.append({
                    "text": str(clue["text"])[:80],
                    "category": clue.get("category", "general"),
                    "found_at": now_iso,
                    "is_new": True,
                })
            cs["clues"] = clues
            session.campaign_state = cs
            flag_modified(session, "campaign_state")

        # ── 写入会话历史 ──
        self._append_session_history(session, ar)

        # ── 写入 GameLog ──
        await self._write_logs(session, ar, data)

        return ar

    # ─────────────────────────────────────────────
    # 角色状态变化
    # ─────────────────────────────────────────────

    async def _apply_character_delta(
        self,
        delta: dict,
        char_map: dict[str, Character],
        session_id: str,
    ) -> None:
        char_id = str(delta.get("id", ""))
        char = char_map.get(char_id)
        if not char:
            logger.warning(f"state_delta 包含未知角色 ID: {char_id}")
            return

        derived = char.derived or {}
        hp_max  = derived.get("hp_max", char.hp_current)

        # HP 变化（边界保护）
        hp_change = int(delta.get("hp_change", 0))
        if hp_change != 0:
            char.hp_current = max(0, min(hp_max, char.hp_current + hp_change))

        # 条件管理
        conditions = set(char.conditions or [])
        for c in delta.get("conditions_add", []):
            conditions.add(c)
        for c in delta.get("conditions_remove", []):
            conditions.discard(c)
        char.conditions = list(conditions)

        # 法术位消耗
        slots_used = delta.get("spell_slots_used", {})
        if slots_used:
            current_slots = dict(char.spell_slots or {})
            for slot_level, count in slots_used.items():
                current = current_slots.get(slot_level, 0)
                current_slots[slot_level] = max(0, current - int(count))
            char.spell_slots = current_slots

        # 专注
        if delta.get("concentration_set") is not None:
            char.concentration = delta["concentration_set"] or None
        if delta.get("concentration_clear"):
            char.concentration = None

        # 濒死豁免
        ds_change = delta.get("death_saves")
        if ds_change:
            ds = dict(char.death_saves or {"successes": 0, "failures": 0, "stable": False})
            ds["successes"] = min(3, ds.get("successes", 0) + int(ds_change.get("successes_add", 0)))
            ds["failures"]  = min(3, ds.get("failures", 0)  + int(ds_change.get("failures_add", 0)))
            if ds_change.get("stabilized"):
                ds["stable"] = True
            if ds_change.get("revived"):
                ds["stable"] = True
                char.hp_current = 1
            char.death_saves = ds

        # 鼓舞（inspiration）
        if delta.get("inspiration_gained"):
            # 预留字段，Character 模型后续可加 has_inspiration
            pass

    # ─────────────────────────────────────────────
    # 金币变化
    # ─────────────────────────────────────────────

    async def _apply_gold_change(
        self,
        delta: dict,
        char_map: dict[str, Character],
    ) -> None:
        char_id = str(delta.get("id", ""))
        char = char_map.get(char_id)
        if not char:
            logger.warning(f"gold_changes 包含未知角色 ID: {char_id}")
            return

        amount = int(delta.get("amount", 0))
        if amount == 0:
            return

        equipment = dict(char.equipment or {})
        current_gold = equipment.get("gold", 0)
        new_gold = max(0, current_gold + amount)
        equipment["gold"] = new_gold
        char.equipment = equipment

        reason = delta.get("reason", "")
        logger.info(f"角色 {char.name} 金币变化: {current_gold} → {new_gold} ({'+' if amount > 0 else ''}{amount}, {reason})")

    # ─────────────────────────────────────────────
    # 敌人状态变化（存储在 Session.game_state.enemies）
    # ─────────────────────────────────────────────

    def _apply_enemy_delta(self, delta: dict, session: Session) -> None:
        enemy_id = str(delta.get("id", ""))
        if not enemy_id:
            return

        game_state = dict(session.game_state or {})
        enemies = game_state.get("enemies", [])

        for enemy in enemies:
            if str(enemy.get("id", "")) == enemy_id:
                hp_max = enemy.get("hp_max", enemy.get("hp_current", 0))

                # HP 变化
                hp_change = int(delta.get("hp_change", 0))
                if hp_change != 0:
                    enemy["hp_current"] = max(
                        0, min(hp_max, enemy.get("hp_current", 0) + hp_change)
                    )

                # 条件
                conds = set(enemy.get("conditions", []))
                for c in delta.get("conditions_add", []):
                    conds.add(c)
                for c in delta.get("conditions_remove", []):
                    conds.discard(c)
                enemy["conditions"] = list(conds)

                # 死亡
                if delta.get("dead") or enemy["hp_current"] == 0:
                    enemy["dead"] = True
                    enemy["conditions"] = ["死亡"]

                break
        else:
            logger.warning(f"state_delta 包含未知敌人 ID: {enemy_id}")

        session.game_state = game_state

    # ─────────────────────────────────────────────
    # 会话历史追加
    # ─────────────────────────────────────────────

    def _append_session_history(self, session: Session, ar: ApplyResult) -> None:
        MAX_HISTORY = 4000
        history = session.session_history or ""

        new_lines = []
        if ar.narrative:
            new_lines.append(f"DM：{ar.narrative}")
        if ar.companion_reactions:
            new_lines.append(ar.companion_reactions)

        appended = "\n".join(new_lines)
        combined = f"{history}\n{appended}" if history else appended

        # 从句子边界截断（避免切断中文）
        if len(combined) > MAX_HISTORY:
            cutoff = combined[-MAX_HISTORY:]
            boundary = cutoff.find("\nDM：")
            if boundary != -1:
                cutoff = cutoff[boundary:]
            combined = cutoff

        session.session_history = combined.strip()

    # ─────────────────────────────────────────────
    # GameLog 写入
    # ─────────────────────────────────────────────

    async def _write_logs(
        self,
        session: Session,
        ar: ApplyResult,
        full_data: dict,
    ) -> None:
        logs_to_add = []

        # DM 叙述
        if ar.narrative:
            logs_to_add.append(GameLog(
                session_id=session.id,
                role="dm",
                content=ar.narrative,
                log_type="narrative" if "combat" not in ar.action_type else "combat",
                dice_result=ar.dice_display or None,
            ))

        # 队友反应
        if ar.companion_reactions:
            logs_to_add.append(GameLog(
                session_id=session.id,
                role="companion",
                content=ar.companion_reactions,
                log_type="companion",
            ))

        # AI 回合叙述（每个 AI 单位单独一条日志）
        for ai_turn in full_data.get("ai_turns", []):
            if ai_turn.get("narrative"):
                logs_to_add.append(GameLog(
                    session_id=session.id,
                    role=f"companion_{ai_turn.get('actor_name', 'ai')}",
                    content=ai_turn["narrative"],
                    log_type="combat",
                    dice_result=ai_turn.get("dice_results"),
                ))

        for log in logs_to_add:
            self.db.add(log)
