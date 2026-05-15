"""Wild magic surge helpers."""

import random

from services.dnd_data import WILD_MAGIC_TABLE


def roll_wild_magic_surge() -> dict:
    """Roll on the wild magic surge table. Returns effect description and any mechanical impact."""
    idx = random.randint(0, len(WILD_MAGIC_TABLE) - 1)
    effect = WILD_MAGIC_TABLE[idx]
    # Some effects have mechanical impact
    mechanical = {}
    if "火球术" in effect:
        mechanical = {"type": "damage", "damage": "8d6", "damage_type": "火焰", "range": "self_aoe_20ft"}
    elif "恢复" in effect and "法术位" in effect:
        mechanical = {"type": "recover_slot", "level": 1}
    elif "恢复" in effect and "生命" in effect:
        mechanical = {"type": "heal", "dice": "2d10"}
    elif "临时生命" in effect:
        mechanical = {"type": "temp_hp", "dice": "2d10"}
    elif "力场伤害" in effect:
        mechanical = {"type": "damage", "damage": "1d10", "damage_type": "力场", "range": "self_aoe_10ft"}
    elif "抗性" in effect:
        mechanical = {"type": "resistance_all", "duration": "1min"}
    elif "失能" in effect:
        mechanical = {"type": "condition", "condition": "失能", "duration": "1round"}
    return {"effect": effect, "mechanical": mechanical, "index": idx}
