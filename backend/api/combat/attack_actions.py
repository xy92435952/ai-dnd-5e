"""
api.combat.attack_actions — 玩家主动战斗动作里的独立分支处理。

把 attacks.py 里最前面的 dash / disengage / help / dodge / offhand
这些“与普通攻击并列、但逻辑独立”的分支拆出来，便于主文件继续收缩。
"""
from sqlalchemy.orm.attributes import flag_modified

from models import Character, GameLog, Session, CombatState
from api.combat._shared import _get_ts, _save_ts, _do_concentration_check, svc
from services.character_roster import CharacterRoster


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
    if "冲刺" in action_text:
        if ts["action_used"]:
            from fastapi import HTTPException
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"] = True
        ts["movement_max"] = ts["movement_max"] * 2
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
            from fastapi import HTTPException
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
            from fastapi import HTTPException
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
                helped_name = tchar.name
        else:
            _roster = CharacterRoster(db, session)
            best_cid, best_hp_pct = None, 1.1
            for c in await _roster.companions_alive():
                pct = c.hp_current / max(1, (c.derived or {}).get("hp_max", 1))
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
            from fastapi import HTTPException
            raise HTTPException(400, "本回合行动已用尽")
        ts["action_used"] = True
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
        if not ts["action_used"]:
            from fastapi import HTTPException
            raise HTTPException(400, "副手攻击需要先完成本回合的主手攻击")
        if ts["bonus_action_used"]:
            from fastapi import HTTPException
            raise HTTPException(400, "本回合附赠行动已用尽")

        offhand_target_id = target_id
        offhand_target_name = ""
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
                offhand_target_name = alive[0]["name"]
                offhand_target_deriv = alive[0].get("derived", {})
                offhand_target_enemy = True
                offhand_target_id = alive[0]["id"]

        if not offhand_target_name:
            from fastapi import HTTPException
            raise HTTPException(400, "没有可攻击的目标")

        offhand_result = svc.resolve_melee_attack(
            attacker_derived=player.derived or {} if player else {},
            target_derived=offhand_target_deriv,
            is_offhand=True,
        )

        offhand_conc_log = None
        offhand_new_hp = None
        if offhand_result.attack_roll["hit"]:
            if offhand_target_enemy:
                for e in enemies:
                    if e["id"] == offhand_target_id:
                        e["hp_current"] = svc.apply_damage(
                            e.get("hp_current", 0), offhand_result.damage,
                            e.get("derived", {}).get("hp_max", 10),
                        )
                        offhand_new_hp = e["hp_current"]
                state["enemies"] = enemies
                session.game_state = dict(state)
                flag_modified(session, "game_state")
            else:
                otchar2 = await db.get(Character, offhand_target_id)
                if otchar2:
                    otchar2.hp_current = svc.apply_damage(
                        otchar2.hp_current, offhand_result.damage,
                        (otchar2.derived or {}).get("hp_max", otchar2.hp_current),
                    )
                    offhand_new_hp = otchar2.hp_current
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
            session_id=session_id,
            role="player",
            content=offhand_narration,
            log_type="combat",
            dice_result={
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
            "action": "offhand_attack",
            "narration": offhand_narration,
            "attack_result": offhand_result.attack_roll,
            "damage": offhand_result.damage,
            "target_id": offhand_target_id,
            "target_new_hp": offhand_new_hp,
            "concentration_check": offhand_conc_log.dice_result if offhand_conc_log else None,
            "turn_state": ts,
            "combat_over": offhand_over,
            "outcome": offhand_outcome,
        }

    return None
