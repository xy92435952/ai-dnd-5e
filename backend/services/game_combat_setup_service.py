import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models import CombatState, Module, Session
from services.dnd_rules import roll_initiative
from services.combat_legendary_action_service import initialize_legendary_actions
from services.combat_legendary_resistance_service import initialize_legendary_resistances
from services.combat_recharge_service import normalize_recharge_abilities
from services.encounter_template_service import (
    mark_encounter_template_triggered,
    select_current_encounter_template,
)
from services.encounter_balance_service import estimate_encounter_difficulty
from services.module_content import get_module_content


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
    recharge_abilities = normalize_recharge_abilities(monster)

    enemy = {
        "id": f"enemy_{uuid.uuid4().hex[:8]}",
        "name": monster.get("name", "未知怪物"),
        "hp_current": hp,
        "hp_max": hp,
        "cr": monster.get("cr", monster.get("challenge_rating", monster.get("challenge"))),
        "xp": monster.get("xp"),
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
        "legendary_actions": monster.get("legendary_actions", []),
        "recharge_abilities": recharge_abilities,
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
    enemy["legendary_resistances"] = monster.get(
        "legendary_resistances",
        monster.get("legendary_resistance_uses", monster.get("legendary_resistance", 0)),
    )
    enemy["legendary_resistances_remaining"] = monster.get("legendary_resistances_remaining")
    initialize_legendary_resistances(enemy)
    initialize_legendary_actions(enemy)
    return enemy


async def init_combat(
    *,
    session: Session,
    initial_enemies: list,
    characters: list,
    module: Module,
    db: AsyncSession,
) -> None:
    """Initialize combat state using DM-specified enemies, module monsters, or a fallback enemy."""
    enemies, encounter_template = _resolve_initial_enemies(
        initial_enemies=initial_enemies,
        module=module,
        game_state=session.game_state,
        characters=characters,
    )
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
    if encounter_template:
        state = mark_encounter_template_triggered(state, encounter_template.get("id"))
        state["last_encounter_template_id"] = encounter_template.get("id")
        if encounter_template.get("party_balance"):
            state["last_encounter_template_balance"] = encounter_template.get("party_balance")
    state["enemies"] = enemies
    state["encounter_balance"] = estimate_encounter_difficulty(
        [
            {"id": str(character.id), "level": character.level or 1}
            for character in characters
        ],
        enemies,
    )
    session.game_state = state
    flag_modified(session, "game_state")
    await db.flush()


def _resolve_initial_enemies(
    *,
    initial_enemies: list,
    module: Module,
    game_state: dict | None = None,
    characters: list | None = None,
) -> tuple[list[dict], dict | None]:
    return _resolve_initial_enemies_from_sources(
        initial_enemies=initial_enemies,
        module=module,
        game_state=game_state,
        characters=characters,
    )


def _resolve_initial_enemies_from_sources(
    *,
    initial_enemies: list,
    module: Module,
    game_state: dict | None = None,
    characters: list | None = None,
) -> tuple[list[dict], dict | None]:
    enemies = _build_enemies_from_initial_items(initial_enemies or [], module)
    if enemies:
        return enemies, None

    encounter_template = select_current_encounter_template(
        game_state or {},
        get_module_content(module),
        party=[
            {"id": str(character.id), "level": character.level or 1}
            for character in characters or []
        ],
    )
    if encounter_template:
        enemies = _build_enemies_from_initial_items(
            encounter_template.get("initial_enemies") or [],
            module,
        )
        if enemies:
            return enemies, encounter_template

    module_monsters = get_module_content(module).get("monsters", [])
    for monster in module_monsters[:3]:
        enemies.append(build_enemy_from_module(monster))

    if not enemies:
        enemies.append(_generic_fallback_enemy())
    return enemies, None

def _build_enemies_from_initial_items(items: list, module: Module) -> list[dict]:
    enemies: list[dict] = []
    parsed = get_module_content(module)
    parsed_monsters = {
        monster["name"]: monster
        for monster in parsed.get("monsters", [])
        if isinstance(monster, dict) and monster.get("name")
    }
    for item in items:
        if isinstance(item, str):
            item = {"name": item}
        name = item.get("name", "Unknown Creature") if isinstance(item, dict) else str(item)
        base = parsed_monsters.get(name)
        if base:
            enemy = build_enemy_from_module(base)
            if isinstance(item, dict) and item.get("hp_current"):
                enemy["hp_current"] = item["hp_current"]
        else:
            enemy = _fallback_enemy_from_dm(item, name)
        enemies.append(enemy)
    return enemies


def _fallback_enemy_from_dm(item, name: str) -> dict:
    item = item if isinstance(item, dict) else {}
    multiattack = max(1, int(item.get("multiattack") or item.get("attacks_max") or 1))
    recharge_abilities = normalize_recharge_abilities(item)
    enemy = {
        "id": f"enemy_{uuid.uuid4().hex[:8]}",
        "name": name,
        "hp_current": item.get("hp", 20),
        "hp_max": item.get("hp", 20),
        "cr": item.get("cr", item.get("challenge_rating", item.get("challenge"))),
        "xp": item.get("xp"),
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
        "legendary_actions": item.get("legendary_actions", []),
        "recharge_abilities": recharge_abilities,
        "multiattack": multiattack,
        "attacks_max": multiattack,
        "tactics": "直接攻击最近的目标",
        "is_player": False,
        "initiative": 0,
        "derived": {
            "hp_max": item.get("hp", 20),
            "ac": item.get("ac", 13),
            "attack_bonus": item.get("attack_bonus", 3),
        },
    }
    enemy["legendary_resistances"] = item.get(
        "legendary_resistances",
        item.get("legendary_resistance_uses", item.get("legendary_resistance", 0)),
    )
    enemy["legendary_resistances_remaining"] = item.get("legendary_resistances_remaining")
    initialize_legendary_resistances(enemy)
    initialize_legendary_actions(enemy)
    return enemy


def _generic_fallback_enemy() -> dict:
    enemy = {
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
        "legendary_actions": [],
        "recharge_abilities": [],
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
    initialize_legendary_resistances(enemy)
    initialize_legendary_actions(enemy)
    return enemy
