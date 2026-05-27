"""
api.combat.attack_actions — 玩家主动战斗动作里的独立分支处理。

把 attacks.py 里最前面的 dash / disengage / help / dodge / offhand
这些“与普通攻击并列、但逻辑独立”的分支拆出来，便于主文件继续收缩。
"""
from fastapi import HTTPException

from models import Character, GameLog, Session, CombatState
from api.combat._shared import _get_ts, _save_ts
from services.character_roster import CharacterRoster
from services.dnd_rules import get_effective_hp_max
from services.combat_attack_roll_service import CombatAttackRollError
from services.combat_offhand_attack_service import resolve_offhand_attack
from services.session_access_service import assert_character_in_session


async def maybe_handle_pre_attack_action(
    *,
    session_id: str,
    action_text: str,
    target_id: str | None,
    db,
    session: Session,
    combat: CombatState,
    player: Character | None,
    player_id: str,
    player_name: str,
    state: dict,
    enemies: list,
) -> dict | None:
    """处理不会进入普通攻击主流程的前置动作。"""
    ts = _get_ts(combat, player_id)

    # ── 冲刺 ────────────────────────────────────────────
    if "冲刺" in action_text or "dash" in action_text.lower():
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"] = True
        ts["movement_max"] = ts["movement_max"] + ts.get("base_movement_max", ts["movement_max"])
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

    # ── 脱离接战 ────────────────────────────────────────
    if "脱离" in action_text or "disengage" in action_text.lower():
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"] = True
        ts["disengaged"] = True
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

    # ── 协助 ────────────────────────────────────────────
    if "协助" in action_text or "help" in action_text.lower():
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"] = True
        _save_ts(combat, player_id, ts)

        helped_name = "队友"
        if target_id:
            t_ts = _get_ts(combat, target_id)
            t_ts["being_helped"] = True
            _save_ts(combat, target_id, t_ts)
            tchar = await db.get(Character, target_id)
            if tchar:
                await assert_character_in_session(tchar, session, db)
                helped_name = tchar.name
        else:
            _roster = CharacterRoster(db, session)
            best_cid, best_hp_pct = None, 1.1
            for c in await _roster.companions_alive():
                pct = c.hp_current / max(1, get_effective_hp_max(c))
                if pct < best_hp_pct:
                    best_hp_pct = pct
                    best_cid = c.id
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

    # ── 闪避 ────────────────────────────────────────────
    is_dodge = "闪避" in action_text or "dodge" in action_text.lower()
    if is_dodge:
        if ts["action_used"]:
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"] = True
        ts["dodging"] = True
        _save_ts(combat, player_id, ts)
        narration = f"{player_name} 采取了闪避姿态，专注于躲避攻击。"
        db.add(GameLog(session_id=session_id, role="player", content=narration, log_type="combat"))
        await db.commit()
        return {
            "action": "dodge", "narration": narration,
            "turn_state": ts, "combat_over": False, "outcome": None,
        }

    # ── 副手攻击 ────────────────────────────────────────
    is_offhand_attack = "副手" in action_text or "offhand" in action_text.lower()
    if is_offhand_attack:
        try:
            offhand = await resolve_offhand_attack(
                db,
                session_id=session_id,
                session=session,
                combat=combat,
                player=player,
                player_id=player_id,
                player_name=player_name,
                target_id=target_id,
                state=state,
                enemies=enemies,
            )
        except CombatAttackRollError as exc:
            raise HTTPException(exc.status_code, exc.detail) from exc

        db.add(
            GameLog(
                session_id=session_id,
                role="player",
                content=offhand.narration,
                log_type="combat",
                dice_result={
                    "attack": offhand.attack_result,
                    "damage": offhand.damage_roll,
                    "offhand": True,
                    "extra_damage": offhand.extra_damage_notes if offhand.extra_damage_notes else None,
                },
            )
        )
        if offhand.concentration_log:
            db.add(offhand.concentration_log)

        await db.commit()
        return {
            "action": "offhand_attack",
            "narration": offhand.narration,
            "attack_result": offhand.attack_result,
            "damage": offhand.damage,
            "extra_damage_notes": offhand.extra_damage_notes,
            "target_id": offhand.target_id,
            "target_new_hp": offhand.target_new_hp,
            "target_state": offhand.target_state,
            "concentration_check": (
                offhand.concentration_log.dice_result
                if offhand.concentration_log
                else None
            ),
            "turn_state": offhand.turn_state,
            "combat_over": offhand.combat_over,
            "outcome": offhand.outcome,
        }

    return None
