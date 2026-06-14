from typing import Optional


WALL_TERRAIN = {"wall", "cover", "half_cover", "three_quarters_cover", "blocking", "blocker", "opaque"}
TOTAL_COVER_TERRAIN = {"total_cover"}
DIFFICULT_TERRAIN = {"difficult", "difficult_terrain"}


def terrain_kind(value) -> str:
    if isinstance(value, dict):
        if value.get("hazard") is True:
            return "hazard"
        if value.get("objective") is True:
            return "objective"
        raw = (
            value.get("terrain")
            or value.get("type")
            or value.get("kind")
            or value.get("category")
            or ""
        )
        if not raw and any(key in value for key in ("cover", "cover_bonus", "cover_level")):
            raw = "cover"
    else:
        raw = value
    return str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")


def get_cover_bonus(grid_data: dict, attacker_pos: dict, target_pos: dict) -> int:
    return get_cover_analysis(grid_data, attacker_pos, target_pos)["bonus"]


def get_cover_analysis(grid_data: dict, attacker_pos: dict, target_pos: dict) -> dict:
    if not grid_data or not attacker_pos or not target_pos:
        return {"bonus": 0, "obstacle_weight": 0, "cells": [], "blocks_target": False}

    ax, ay = attacker_pos.get("x", 0), attacker_pos.get("y", 0)
    tx, ty = target_pos.get("x", 0), target_pos.get("y", 0)

    dx = tx - ax
    dy = ty - ay
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        return {"bonus": 0, "obstacle_weight": 0, "cells": [], "blocks_target": False}

    obstacles = 0
    cells = []
    blocks_target = False
    for i in range(1, steps):
        cx = ax + round(dx * i / steps)
        cy = ay + round(dy * i / steps)
        cell = f"{cx}_{cy}"
        terrain = terrain_kind(grid_data.get(f"{cx}_{cy}", ""))
        if terrain in TOTAL_COVER_TERRAIN:
            obstacles += 2
            blocks_target = True
            cells.append({"cell": cell, "terrain": terrain, "weight": 2})
        elif terrain in WALL_TERRAIN:
            obstacles += 1
            cells.append({"cell": cell, "terrain": terrain, "weight": 1})
        elif terrain in DIFFICULT_TERRAIN:
            obstacles += 0.5
            cells.append({"cell": cell, "terrain": terrain, "weight": 0.5})

    if obstacles >= 2:
        bonus = 5
    elif obstacles >= 1:
        bonus = 2
    else:
        bonus = 0

    return {
        "bonus": bonus,
        "obstacle_weight": obstacles,
        "cells": cells,
        "blocks_target": blocks_target,
        **({"blocked_by": "total_cover"} if blocks_target else {}),
    }


def resolve_grapple(
    attacker_derived: dict,
    target_derived: dict,
    attacker_proficient_skills: list = None,
    target_proficient_skills: list = None,
    attacker_condition_durations: dict | None = None,
    target_condition_durations: dict | None = None,
    attacker_conditions: list[str] | None = None,
    target_conditions: list[str] | None = None,
) -> dict:
    from services.dnd_rules import roll_skill_check
    atk_check = roll_skill_check(
        {
            "derived": attacker_derived,
            "proficient_skills": attacker_proficient_skills or [],
            "conditions": attacker_conditions or [],
            "condition_durations": attacker_condition_durations or {},
        },
        "运动", dc=0,
    )
    t_skills = target_proficient_skills or []
    t_mods = target_derived.get("ability_modifiers", {})
    t_prof = target_derived.get("proficiency_bonus", 2)
    athl_mod = t_mods.get("str", 0) + (t_prof if "运动" in t_skills or "Athletics" in t_skills else 0)
    acrob_mod = t_mods.get("dex", 0) + (t_prof if "杂技" in t_skills or "Acrobatics" in t_skills else 0)
    if acrob_mod > athl_mod:
        def_check = roll_skill_check(
            {
                "derived": target_derived,
                "proficient_skills": t_skills,
                "conditions": target_conditions or [],
                "condition_durations": target_condition_durations or {},
            },
            "杂技", dc=0,
        )
    else:
        def_check = roll_skill_check(
            {
                "derived": target_derived,
                "proficient_skills": t_skills,
                "conditions": target_conditions or [],
                "condition_durations": target_condition_durations or {},
            },
            "运动", dc=0,
        )
    return {
        "success": atk_check["total"] >= def_check["total"],
        "attacker_roll": atk_check,
        "target_roll": def_check,
    }


def resolve_shove(
    attacker_derived: dict,
    target_derived: dict,
    attacker_proficient_skills: list = None,
    target_proficient_skills: list = None,
    shove_type: str = "prone",
    attacker_condition_durations: dict | None = None,
    target_condition_durations: dict | None = None,
    attacker_conditions: list[str] | None = None,
    target_conditions: list[str] | None = None,
) -> dict:
    result = resolve_grapple(
        attacker_derived,
        target_derived,
        attacker_proficient_skills,
        target_proficient_skills,
        attacker_condition_durations,
        target_condition_durations,
        attacker_conditions,
        target_conditions,
    )
    result["shove_type"] = shove_type
    return result


def choose_ai_target(
    actor_is_enemy: bool,
    player: Optional[dict],
    allies: list[dict],
    enemies_alive: list[dict],
) -> Optional[dict]:
    if actor_is_enemy:
        if player and player.get("hp_current", 0) > 0:
            return player
        alive = [a for a in allies if a.get("hp_current", 0) > 0]
        return min(alive, key=lambda x: x.get("hp_current", 999), default=None)
    return min(enemies_alive, key=lambda x: x.get("hp_current", 999), default=None)
