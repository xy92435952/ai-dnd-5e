import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models import CombatState, Module, Session
from services.dnd_rules import roll_initiative


def build_enemy_from_module(monster: dict) -> dict:
    """Convert a parsed module monster stat block into combat enemy state."""
    scores = monster.get("ability_scores", {})

    def mod(score):
        return (score - 10) // 2

    primary_action = next(
        (
            action for action in monster.get("actions", [])
            if action.get("type") in ("melee_attack", "ranged_attack")
        ),
        None,
    )
    attack_bonus = primary_action.get("attack_bonus", 3) if primary_action else 3
    damage_dice = primary_action.get("damage_dice", "1d6+2") if primary_action else "1d6+2"
    damage_type = primary_action.get("damage_type", "钝击") if primary_action else "钝击"
    hp = monster.get("hp", 10)
    multiattack = max(1, int(monster.get("multiattack") or monster.get("attacks_max") or 1))

    return {
        "id": f"enemy_{uuid.uuid4().hex[:8]}",
        "name": monster.get("name", "未知怪物"),
        "hp_current": hp,
        "hp_max": hp,
        "ac": monster.get("ac", 13),
        "conditions": [],
        "dead": False,
        "ability_scores": scores,
        "attack_bonus": attack_bonus,
        "damage_dice": damage_dice,
        "damage_type": damage_type,
        "speed": monster.get("speed", 30),
        "resistances": monster.get("resistances", []),
        "immunities": monster.get("immunities", []),
        "vulnerabilities": monster.get("vulnerabilities", []),
        "condition_immunities": monster.get("condition_immunities", []),
        "special_abilities": monster.get("special_abilities", []),
        "actions": monster.get("actions", []),
        "multiattack": multiattack,
        "attacks_max": multiattack,
        "known_spells": list(monster.get("known_spells") or []),
        "prepared_spells": list(monster.get("prepared_spells") or []),
        "cantrips": list(monster.get("cantrips") or []),
        "spell_slots": dict(monster.get("spell_slots") or {}),
        "spell_ability": monster.get("spell_ability"),
        "spell_save_dc": monster.get("spell_save_dc"),
        "concentration": monster.get("concentration"),
        "tactics": monster.get("tactics", "直接攻击最近的目标"),
        "initiative": mod(scores.get("dex", 10)),
        "is_player": False,
        "derived": {
            "hp_max": hp,
            "ac": monster.get("ac", 13),
            "initiative": mod(scores.get("dex", 10)),
            "attack_bonus": attack_bonus,
            "spell_ability": monster.get("spell_ability"),
            "spell_save_dc": monster.get("spell_save_dc"),
            "ability_modifiers": {
                "str": mod(scores.get("str", 10)),
                "dex": mod(scores.get("dex", 10)),
                "con": mod(scores.get("con", 10)),
                "int": mod(scores.get("int", 10)),
                "wis": mod(scores.get("wis", 10)),
                "cha": mod(scores.get("cha", 10)),
            },
        },
    }


async def init_combat(
    *,
    session: Session,
    initial_enemies: list,
    characters: list,
    module: Module,
    db: AsyncSession,
) -> None:
    """Initialize combat state using DM-specified enemies, module monsters, or a fallback enemy."""
    enemies = _resolve_initial_enemies(initial_enemies=initial_enemies, module=module)
    for enemy in enemies:
        enemy["is_enemy"] = True
        enemy.setdefault("is_player", False)

    combatants = [
        {
            "id": str(character.id),
            "name": character.name,
            "initiative": (character.derived or {}).get("initiative", 0),
            "is_player": character.is_player,
            "is_enemy": False,
        }
        for character in characters
    ] + enemies
    initiative_order = roll_initiative(combatants)

    positions = {}
    for index, character in enumerate(characters):
        positions[str(character.id)] = {"x": 2, "y": 3 + index}
    for index, enemy in enumerate(enemies):
        positions[enemy["id"]] = {"x": 17, "y": 8 + index}

    old_combats = await db.execute(select(CombatState).where(CombatState.session_id == session.id))
    for old_combat in old_combats.scalars().all():
        await db.delete(old_combat)

    db.add(CombatState(
        session_id=session.id,
        grid_data={},
        entity_positions=positions,
        turn_order=initiative_order,
        current_turn_index=0,
        round_number=1,
    ))
    session.combat_active = True
    state = dict(session.game_state or {})
    state["enemies"] = enemies
    session.game_state = state
    flag_modified(session, "game_state")
    await db.flush()


def _resolve_initial_enemies(*, initial_enemies: list, module: Module) -> list[dict]:
    enemies: list[dict] = []
    if initial_enemies:
        parsed_monsters = {
            monster["name"]: monster
            for monster in (module.parsed_content or {}).get("monsters", [])
        }
        for item in initial_enemies:
            if isinstance(item, str):
                item = {"name": item}
            name = item.get("name", "未知怪物") if isinstance(item, dict) else str(item)
            base = parsed_monsters.get(name)
            if base:
                enemy = build_enemy_from_module(base)
                if isinstance(item, dict) and item.get("hp_current"):
                    enemy["hp_current"] = item["hp_current"]
            else:
                enemy = _fallback_enemy_from_dm(item, name)
            enemies.append(enemy)

    if not enemies:
        module_monsters = (module.parsed_content or {}).get("monsters", [])
        for monster in module_monsters[:3]:
            enemies.append(build_enemy_from_module(monster))

    if not enemies:
        enemies.append(_generic_fallback_enemy())
    return enemies


def _fallback_enemy_from_dm(item, name: str) -> dict:
    item = item if isinstance(item, dict) else {}
    return {
        "id": f"enemy_{uuid.uuid4().hex[:8]}",
        "name": name,
        "hp_current": item.get("hp", 20),
        "hp_max": item.get("hp", 20),
        "ac": item.get("ac", 13),
        "conditions": [],
        "dead": False,
        "attack_bonus": item.get("attack_bonus", 3),
        "damage_dice": item.get("damage_dice", "1d6+2"),
        "damage_type": item.get("damage_type", "钝击"),
        "resistances": item.get("resistances", []),
        "immunities": item.get("immunities", []),
        "vulnerabilities": item.get("vulnerabilities", []),
        "condition_immunities": item.get("condition_immunities", []),
        "special_abilities": item.get("special_abilities", []),
        "actions": item.get("actions", []),
        "multiattack": max(1, int(item.get("multiattack") or item.get("attacks_max") or 1)),
        "attacks_max": max(1, int(item.get("multiattack") or item.get("attacks_max") or 1)),
        "tactics": "直接攻击最近的目标",
        "is_player": False,
        "initiative": 0,
        "derived": {
            "hp_max": item.get("hp", 20),
            "ac": item.get("ac", 13),
            "attack_bonus": item.get("attack_bonus", 3),
        },
    }


def _generic_fallback_enemy() -> dict:
    return {
        "id": f"enemy_{uuid.uuid4().hex[:8]}",
        "name": "敌对生物",
        "hp_current": 30,
        "hp_max": 30,
        "ac": 13,
        "conditions": [],
        "dead": False,
        "attack_bonus": 4,
        "damage_dice": "1d8+2",
        "damage_type": "钝击",
        "resistances": [],
        "immunities": [],
        "vulnerabilities": [],
        "condition_immunities": [],
        "special_abilities": [],
        "actions": [],
        "multiattack": 1,
        "attacks_max": 1,
        "tactics": "直接攻击最近的目标",
        "is_player": False,
        "initiative": 1,
        "derived": {
            "hp_max": 30,
            "ac": 13,
            "attack_bonus": 4,
            "ability_modifiers": {
                "str": 2,
                "dex": 1,
                "con": 1,
                "int": -1,
                "wis": 0,
                "cha": -1,
            },
        },
    }
