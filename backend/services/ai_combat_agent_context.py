"""Context formatting helpers for AI combat decisions."""


def chebyshev(a: dict, b: dict) -> int:
    if not a or not b:
        return 999
    return max(abs(a.get("x", 0) - b.get("x", 0)), abs(a.get("y", 0) - b.get("y", 0)))


def format_entity(e: dict, pos: dict = None) -> str:
    """格式化一个实体为简短描述"""
    hp = e.get("hp_current", 0)
    hp_max = e.get("hp_max") or (e.get("derived") or {}).get("hp_max", hp)
    hp_pct = int(hp / hp_max * 100) if hp_max > 0 else 0
    conds = ", ".join(e.get("conditions", [])) or "无"
    conc = e.get("concentration", "")
    pos_str = f"({pos['x']},{pos['y']})" if pos else "未知"
    cls = e.get("char_class", e.get("type", ""))
    conc_str = f" [专注: {conc}]" if conc else ""

    return (
        f"  - ID: {e.get('id','?')} | {e.get('name','?')} ({cls}) | "
        f"HP: {hp}/{hp_max} ({hp_pct}%) | AC: {e.get('ac') or (e.get('derived') or {}).get('ac',10)} | "
        f"位置: {pos_str} | 条件: {conds}{conc_str}"
    )


def format_actions(actions: list) -> str:
    """格式化怪物/角色的可用行动"""
    if not actions:
        return "  - 普通近战攻击"
    lines = []
    for a in actions:
        name = a.get("name", "未知")
        atype = a.get("type", "")
        dmg = a.get("damage_dice", "")
        atk = a.get("attack_bonus") or a.get("to_hit", "")
        rng = a.get("reach_or_range", a.get("reach", ""))
        extra = a.get("extra_effects", "")
        lines.append(f"  - {name} ({atype}) | 命中: +{atk} | 伤害: {dmg} | 范围: {rng}" +
                     (f" | 特殊: {extra}" if extra else ""))
    return "\n".join(lines) if lines else "  - 普通近战攻击"


def format_spells(char: dict) -> str:
    """格式化队友的可用法术"""
    known = char.get("known_spells", []) or []
    cantrips = char.get("cantrips", []) or []
    slots = char.get("spell_slots", {}) or {}
    prepared = char.get("prepared_spells", []) or []
    all_spells = list(set(known) | set(cantrips) | set(prepared))

    if not all_spells:
        return "  无法术"

    lines = []
    if cantrips:
        lines.append(f"  戏法（无限次）: {', '.join(cantrips)}")
    for slot_level in ["1st", "2nd", "3rd", "4th", "5th"]:
        remaining = slots.get(slot_level, 0)
        if remaining > 0:
            lines.append(f"  {slot_level} 级法术位: {remaining} 剩余")
    if known:
        lines.append(f"  习得法术: {', '.join(known[:10])}")
    return "\n".join(lines) if lines else "  无法术"


def format_distances(actor_pos: dict, entities: list, positions: dict) -> str:
    """格式化距离信息"""
    lines = []
    for e in entities:
        eid = str(e.get("id", ""))
        epos = positions.get(eid)
        if epos and actor_pos:
            dist = chebyshev(actor_pos, epos)
            lines.append(f"  → {e.get('name','?')} (ID:{eid[:8]}): {dist} 格 ({dist*5}ft)" +
                         (" ⚔近战范围" if dist <= 1 else ""))
    return "\n".join(lines) if lines else "  无距离信息"


def build_ai_combat_context(
    *,
    actor: dict,
    actor_is_enemy: bool,
    all_characters: list,
    all_enemies: list,
    positions: dict,
) -> dict:
    actor_id = str(actor.get("id", ""))
    actor_pos = positions.get(actor_id, {})
    move_speed = max(actor.get("speed", 30), 20) // 5

    if actor_is_enemy:
        targets = all_characters
        allies = [e for e in all_enemies if str(e.get("id")) != actor_id and e.get("hp_current", 0) > 0]
    else:
        targets = all_enemies
        allies = [c for c in all_characters if str(c.get("id")) != actor_id and c.get("hp_current", 0) > 0]

    targets_alive = [t for t in targets if t.get("hp_current", 0) > 0]
    targets_info = "\n".join(format_entity(t, positions.get(str(t.get("id")))) for t in targets_alive)
    allies_info = "\n".join(format_entity(a, positions.get(str(a.get("id")))) for a in allies) or "  无盟友"
    distance_info = format_distances(actor_pos, targets_alive + allies, positions)
    actor_hp_max = actor.get("hp_max") or (actor.get("derived") or {}).get("hp_max", actor.get("hp_current", 1))

    return {
        "actor_id": actor_id,
        "actor_pos": actor_pos,
        "move_speed": move_speed,
        "targets_alive": targets_alive,
        "targets_info": targets_info,
        "allies_info": allies_info,
        "distance_info": distance_info,
        "actor_hp_max": actor_hp_max,
    }
