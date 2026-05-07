"""
api.combat.attack_rolls — two-step attack and damage roll endpoints.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, CombatState, GameLog
from api.deps import assert_can_act, get_session_or_404, get_user_id
from api.combat._shared import (
    _check_attack_range,
    _get_ts,
    _has_ally_adjacent_to,
    _save_ts,
    svc,
)
from api.combat.attack_damage import (
    apply_basic_damage_bonuses,
    apply_attack_damage_to_target,
    find_pending_attack,
    roll_pending_damage,
)
from api.combat.attack_modifiers import (
    apply_ranged_close_penalty,
    build_attack_deriveds,
    build_weapon_damage_dice,
    calculate_cover_bonus,
    choose_feat_power_attack,
)
from api.combat.attack_targeting import get_target_conditions, resolve_attack_target
from api.combat.schemas import AttackRollRequest, DamageRollRequest
from services.character_roster import CharacterRoster
from services.combat_narrator import narrate_action
from services.dnd_rules import _normalize_class, roll_dice
from schemas.combat_responses import CombatActionResult

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/attack-roll", response_model=CombatActionResult)
async def attack_roll(
    session_id: str,
    req:        AttackRollRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    两步攻击流程 Step 1：仅掷 d20 攻击检定，判定命中/未中/暴击/大失手。
    不掷伤害骰、不扣 HP。结果暂存到 turn_states.pending_attack 供 /damage-roll 使用。
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")
    # 多人联机：校验该用户有权操作攻击者
    await assert_can_act(session, user_id, req.entity_id, db)

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
    target = await resolve_attack_target(db, req.target_id, enemies, allow_auto_enemy=False)
    if not target:
        raise HTTPException(400, "目标不存在")
    target_derived = target.derived
    target_name = target.name
    target_is_enemy = target.is_enemy
    resolved_target_id = target.id

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
    t_conditions = await get_target_conditions(db, target, enemies)

    atk_adv, atk_dis = svc.get_attack_modifiers(p_conditions)
    def_adv, def_dis = svc.get_defense_modifiers(t_conditions)

    if ts.get("being_helped"):
        atk_adv = True
        ts["being_helped"] = False

    positions = dict(combat.entity_positions or {})
    atk_dis, ranged_penalty = apply_ranged_close_penalty(
        atk_dis=atk_dis,
        is_ranged=is_ranged,
        attacker_id=player_id,
        enemies=enemies,
        positions=positions,
        attacker_derived=p_derived,
    )

    # Cover
    cover_bonus = calculate_cover_bonus(
        grid_data=dict(combat.grid_data or {}),
        positions=positions,
        attacker_id=player_id,
        target_id=resolved_target_id,
        attacker_derived=p_derived,
        is_ranged=is_ranged,
    )

    # GWM / Sharpshooter power attack
    feat_power = choose_feat_power_attack(
        attacker_derived=p_derived,
        target_derived=target_derived,
        cover_bonus=cover_bonus,
        is_ranged=is_ranged,
    )

    # Build modified derived dicts for the roll
    attack_attacker_derived, attack_target_derived = build_attack_deriveds(
        attacker_derived=p_derived,
        target_derived=target_derived,
        cover_bonus=cover_bonus,
        is_ranged=is_ranged,
        power=feat_power,
    )

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
    weapon_damage = build_weapon_damage_dice(player, is_ranged=is_ranged, is_offhand=is_offhand)
    damage_dice = weapon_damage.damage_dice
    hit_die = weapon_damage.hit_die
    dmg_mod = weapon_damage.dmg_mod

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
        "feat_power_attack": feat_power.active,
        "feat_power_bonus_dmg": feat_power.bonus_damage,
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


@router.post("/combat/{session_id}/damage-roll", response_model=CombatActionResult)
async def damage_roll(
    session_id: str,
    req:        DamageRollRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
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
    attacker_entity_id, pending = find_pending_attack(
        dict(combat.turn_states or {}),
        req.pending_attack_id,
    )

    if not pending:
        raise HTTPException(404, "未找到待处理的攻击检定，可能已过期或 ID 错误")

    # 多人联机：校验该用户有权操作该 pending_attack 的攻击者
    await assert_can_act(session, user_id, attacker_entity_id, db)

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
    pending_damage = roll_pending_damage(
        hit_die=hit_die,
        dmg_mod=dmg_mod,
        is_crit=is_crit,
        damage_values=req.damage_values,
    )
    damage_dice_expr = pending_damage.damage_dice_expr
    damage_roll_result = pending_damage.damage_roll_result
    damage_rolls = pending_damage.damage_rolls
    crit_extra = pending_damage.crit_extra

    damage, extra_damage_notes, dueling_bonus, rage_bonus, feat_power_bonus_dmg = apply_basic_damage_bonuses(
        base_damage=pending_damage.damage,
        pending=pending,
        attacker_derived=p_derived,
        level=p_level,
        is_ranged=is_ranged,
        get_rage_bonus=svc.get_rage_bonus,
    )

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
        _roster = CharacterRoster(db, session)
        ally_list = [{"id": session.player_character_id, "hp_current": player.hp_current}]
        for c in await _roster.companions():
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
    target_new_hp, conc_log = await apply_attack_damage_to_target(
        db,
        session_id=session_id,
        enemies=enemies,
        target_id=target_id,
        target_is_enemy=target_is_enemy,
        damage=total_damage,
    )
    if target_is_enemy:
        state["enemies"]   = enemies
        session.game_state = dict(state)
        flag_modified(session, "game_state")

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
