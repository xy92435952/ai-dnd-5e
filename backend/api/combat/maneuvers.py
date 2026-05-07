"""
api.combat.maneuvers — Battle Master maneuver combat endpoint.
"""
import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, CombatState, GameLog
from api.deps import get_session_or_404
from api.combat.schemas import ManeuverRequest
from services.dnd_rules import roll_dice
from schemas.combat_responses import CombatActionResult

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/maneuver", response_model=CombatActionResult)
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
