from typing import Optional


def get_cover_bonus(grid_data: dict, attacker_pos: dict, target_pos: dict) -> int:
    if not grid_data or not attacker_pos or not target_pos:
        return 0

    ax, ay = attacker_pos.get("x", 0), attacker_pos.get("y", 0)
    tx, ty = target_pos.get("x", 0), target_pos.get("y", 0)

    dx = tx - ax
    dy = ty - ay
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        return 0

    obstacles = 0
    for i in range(1, steps):
        cx = ax + round(dx * i / steps)
        cy = ay + round(dy * i / steps)
        terrain = grid_data.get(f"{cx}_{cy}", "")
        if terrain == "wall":
            obstacles += 1
        elif terrain == "difficult":
            obstacles += 0.5

    if obstacles >= 2:
        return 5
    if obstacles >= 1:
        return 2
    return 0


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
