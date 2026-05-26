from dataclasses import dataclass
from typing import Optional

from services.dnd_rules import (
    apply_character_healing,
    roll_dice,
    stabilize_character,
)


DIRECT_USE_EFFECTS = {"heal", "antitoxin", "fire_resistance", "stabilize"}


@dataclass
class ItemEffectError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def get_direct_use_effect(item_name: str, item_data: dict) -> str:
    if not item_data.get("consumable", False):
        raise ItemEffectError(400, f"【{item_name}】不是消耗品，无法使用")

    effect = item_data.get("effect", "")
    if effect not in DIRECT_USE_EFFECTS:
        raise ItemEffectError(400, f"【{item_name}】暂不支持直接使用")

    return effect


def _validate_stabilize_target(actor, target) -> None:
    if str(getattr(target, "id", "")) != str(getattr(actor, "id", "")):
        if not getattr(actor, "session_id", None) or actor.session_id != getattr(target, "session_id", None):
            raise ItemEffectError(400, "目标必须与使用者在同一队伍")

    if getattr(target, "hp_current", 0) > 0:
        raise ItemEffectError(400, "目标并未濒死，无法使用医疗包稳定")


def apply_item_effect(
    *,
    actor,
    item_name: str,
    item_data: dict,
    target: Optional[object] = None,
) -> dict:
    effect = get_direct_use_effect(item_name, item_data)
    result = {"item": item_name, "effect": effect}

    if effect == "heal":
        heal_dice = item_data.get("heal_dice", "2d4+2")
        roll = roll_dice(heal_dice)
        heal_amount = roll["total"]
        old_hp = actor.hp_current
        heal_result = apply_character_healing(actor, heal_amount)
        result["heal_roll"] = roll
        result["heal_amount"] = heal_amount
        result["hp_before"] = old_hp
        result["hp_after"] = actor.hp_current
        result["revived"] = heal_result["revived"]
        result["death_saves"] = heal_result["death_saves"]

    elif effect == "antitoxin":
        conditions = list(actor.conditions or [])
        if "poisoned" in conditions:
            conditions = [c for c in conditions if c != "poisoned"]
            actor.conditions = conditions
            result["removed_condition"] = "poisoned"
            result["conditions"] = conditions
        result["description"] = "对毒素的豁免检定获得优势，持续1小时"

    elif effect == "fire_resistance":
        conditions = list(actor.conditions or [])
        if "fire_resistance" not in conditions:
            conditions.append("fire_resistance")
            result["added_condition"] = "fire_resistance"
        actor.conditions = conditions
        result["conditions"] = conditions
        result["description"] = "获得火焰伤害抗性，持续1小时"

    elif effect == "stabilize":
        target = target or actor
        _validate_stabilize_target(actor, target)
        death_saves = stabilize_character(target)
        result["target_character_id"] = target.id
        result["target_name"] = target.name
        result["target_hp_current"] = target.hp_current
        result["death_saves"] = death_saves
        result["description"] = "目标已稳定，生命值仍为0"

    return result
