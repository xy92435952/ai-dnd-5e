from typing import Any

from services.combat_concentration_effect_service import discard_condition_sources


def tick_character_conditions(char) -> list[str]:
    """回合开始时递减角色状态持续时间，到期自动移除。返回已移除的条件列表。"""
    durations = dict(char.condition_durations or {})
    conditions = list(char.conditions or [])
    removed = []

    for condition in list(durations.keys()):
        durations[condition] -= 1
        if durations[condition] <= 0:
            durations.pop(condition)
            conditions = [current for current in conditions if current != condition]
            discard_condition_sources(char, condition)
            removed.append(condition)

    char.condition_durations = durations
    char.conditions = conditions
    return removed


def tick_enemy_conditions(enemy: dict[str, Any]) -> list[str]:
    """回合开始时递减敌人状态持续时间。"""
    durations = dict(enemy.get("condition_durations", {}))
    conditions = list(enemy.get("conditions", []))
    removed = []

    for condition in list(durations.keys()):
        durations[condition] -= 1
        if durations[condition] <= 0:
            durations.pop(condition)
            conditions = [current for current in conditions if current != condition]
            discard_condition_sources(enemy, condition)
            removed.append(condition)

    enemy["condition_durations"] = durations
    enemy["conditions"] = conditions
    return removed
