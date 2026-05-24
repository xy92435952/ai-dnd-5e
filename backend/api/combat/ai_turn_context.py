"""
api.combat.ai_turn_context — AI 回合决策所需上下文的准备器。

这里只做数据收集与整理，不做 AI 决策本身。
"""
from models import Character, Session, CombatState
from services.character_roster import CharacterRoster
from services.dnd_rules import _normalize_class


async def build_ai_turn_context(db, session: Session, combat: CombatState, actor_id: str, actor_name: str, enemies: list):
    """构造 AI 决策所需的快照上下文。"""
    is_enemy = actor_id in [e["id"] for e in enemies]
    actor_derived = {}
    actor_hp = 1
    e = None
    achar = None

    if is_enemy:
        e = next((x for x in enemies if x["id"] == actor_id), None)
        if e:
            actor_derived = e.get("derived", {})
            actor_hp = e.get("hp_current", 0)
    else:
        achar = await db.get(Character, actor_id)
        if achar:
            actor_derived = achar.derived or {}
            actor_hp = achar.hp_current

    _roster = CharacterRoster(db, session)
    player = await _roster.player()
    party_alive = []
    for c in await _roster.allies_alive():
        party_alive.append({
            "id": c.id, "name": c.name, "char_class": c.char_class, "level": c.level,
            "hp_current": c.hp_current, "hp_max": (c.derived or {}).get("hp_max", c.hp_current),
            "ac": (c.derived or {}).get("ac", 10), "derived": c.derived or {},
            "conditions": c.conditions or [], "concentration": c.concentration,
            "known_spells": c.known_spells or [], "cantrips": c.cantrips or [],
            "spell_slots": c.spell_slots or {}, "is_player": c.is_player,
            "equipment": c.equipment or {},
        })
    companions_alive = [c for c in party_alive if str(c["id"]) != str(session.player_character_id)]

    enemies_alive = [x for x in enemies if x.get("hp_current", 0) > 0]

    all_characters = []
    all_characters.extend(party_alive)

    actor_full = dict(actor_derived)
    actor_full["id"] = actor_id
    actor_full["name"] = actor_name
    if is_enemy and e:
        actor_full.update({
            "hp_current": e.get("hp_current", 0), "hp_max": e.get("hp_max", e.get("derived", {}).get("hp_max", 10)),
            "ac": e.get("ac", e.get("derived", {}).get("ac", 10)),
            "actions": e.get("actions", []), "speed": e.get("speed", 30),
            "tactics": e.get("tactics", ""), "type": e.get("type", ""),
        })
    elif achar:
        actor_full.update({
            "hp_current": achar.hp_current, "hp_max": (achar.derived or {}).get("hp_max", achar.hp_current),
            "ac": (achar.derived or {}).get("ac", 10), "char_class": achar.char_class, "level": achar.level,
            "known_spells": achar.known_spells or [], "cantrips": achar.cantrips or [],
            "spell_slots": achar.spell_slots or [], "speed": 30,
            "equipment": achar.equipment or {}, "personality": achar.personality or "",
            "actions": [{"name": w.get("name", "武器"), "type": "melee_attack",
                         "damage_dice": w.get("damage", "1d8"), "attack_bonus": actor_derived.get("attack_bonus", 2)}
                        for w in (achar.equipment or {}).get("weapons", [])],
            "prepared_spells": achar.prepared_spells or [],
        })

    return {
        "is_enemy": is_enemy,
        "actor_derived": actor_derived,
        "actor_hp": actor_hp,
        "enemy_ref": e,
        "ally_ref": achar,
        "player": player,
        "companions_alive": companions_alive,
        "enemies_alive": enemies_alive,
        "all_characters": all_characters,
        "actor_full": actor_full,
    }
