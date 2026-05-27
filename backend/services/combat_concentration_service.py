from typing import Optional

from models import GameLog
from services.combat_service import CombatService
from services.dnd_rules import get_incapacitating_reasons

svc = CombatService()


def break_concentration_if_incapacitated(
    char,
    session_id: str,
) -> Optional[GameLog]:
    """End concentration automatically when a character is incapacitated."""
    if not getattr(char, "concentration", None):
        return None

    reasons = get_incapacitating_reasons(char)
    if not reasons:
        return None

    spell_name = char.concentration
    char.concentration = None
    reason_text = "、".join(reasons)
    return GameLog(
        session_id=session_id,
        role="system",
        content=f"💔 {char.name} 因【{reason_text}】失去了【{spell_name}】的专注。",
        log_type="dice",
        dice_result={
            "type": "concentration",
            "broke": True,
            "automatic": True,
            "reason": "incapacitated",
            "reasons": reasons,
        },
    )


async def do_concentration_check(
    char,
    damage: int,
    session_id: str,
) -> Optional[GameLog]:
    """
    受伤后的专注中断检定。
    - 若无专注或伤害为 0，直接返回 None
    - 失败则清除 char.concentration
    - 返回需要写入 DB 的 GameLog，调用方负责 db.add()
    """
    if not char.concentration:
        return None

    automatic_log = break_concentration_if_incapacitated(char, session_id)
    if automatic_log:
        return automatic_log

    if damage <= 0:
        return None

    check = svc.check_concentration(
        character_dict={
            "concentration": char.concentration,
            "derived": char.derived or {},
            "proficient_saves": char.proficient_saves or [],
            "conditions": getattr(char, "conditions", None) or [],
            "condition_durations": getattr(char, "condition_durations", None) or {},
            "hp_current": getattr(char, "hp_current", None),
            "death_saves": getattr(char, "death_saves", None),
        },
        damage=damage,
    )
    if not check:
        return None

    roll_result = check["roll_result"]
    spell_name = check["spell_name"]
    war_caster_tag = "（战争施法者·优势）" if check.get("war_caster") else ""
    if check["broke"]:
        char.concentration = None
        message = (
            f"💔 {char.name} 失去了【{spell_name}】的专注！"
            f" CON豁免{war_caster_tag} DC{check['dc']}："
            f"d20={roll_result['d20']}+{roll_result['modifier']}={roll_result['total']} ❌"
        )
    else:
        message = (
            f"🧘 {char.name} 维持了【{spell_name}】的专注。"
            f" CON豁免{war_caster_tag} DC{check['dc']}："
            f"d20={roll_result['d20']}+{roll_result['modifier']}={roll_result['total']} ✅"
        )

    return GameLog(
        session_id=session_id,
        role="system",
        content=message,
        log_type="dice",
        dice_result={
            "type": "concentration",
            "dc": check["dc"],
            "broke": check["broke"],
            **roll_result,
        },
    )
