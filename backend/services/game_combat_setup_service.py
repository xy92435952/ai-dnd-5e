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

    positions = _initial_combat_positions(characters, enemies, encounter_template)
    grid_data = _grid_data_from_encounter_template(encounter_template)

    old_combats = await db.execute(select(CombatState).where(CombatState.session_id == session.id))
    for old_combat in old_combats.scalars().all():
        await db.delete(old_combat)

    db.add(CombatState(
        session_id=session.id,
        grid_data=grid_data,
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


def _grid_data_from_encounter_template(template: dict | None) -> dict:
    if not template:
        return {}

    grid: dict = {
        "_encounter_template": {
            "id": template.get("id"),
            "name": template.get("name"),
            "objectives": list(template.get("objectives") or [])[:4],
            "terrain": list(template.get("terrain") or [])[:6],
            "cover": list(template.get("cover") or [])[:6],
            "hazards": list(template.get("hazards") or [])[:6],
        }
    }

    cover = list(template.get("cover") or [])
    terrain = list(template.get("terrain") or [])
    objectives = list(template.get("objectives") or [])
    hazards = list(template.get("hazards") or [])
    cover_text = _feature_text(cover)
    terrain_text = _feature_text(terrain)
    hazard_text = _feature_text(hazards)

    authored_cover_cells = _apply_authored_cell_features(grid, cover, default_terrain="wall")
    authored_terrain_cells = _apply_authored_cell_features(grid, terrain, default_terrain="terrain")
    _apply_authored_cell_features(grid, objectives, default_terrain="objective")
    authored_hazard_cells = _apply_authored_cell_features(grid, hazards, default_terrain="hazard")

    if cover_text and not authored_cover_cells:
        for cell in ("10_4", "10_5", "10_7", "10_8"):
            grid.setdefault(cell, "wall")
    if ("difficult" in terrain_text or "sparking" in terrain_text) and not authored_terrain_cells:
        for cell in ("11_6", "12_6", "11_7", "12_7"):
            grid.setdefault(cell, "difficult")
    if hazard_text and not authored_hazard_cells:
        for cell in ("13_5", "13_6"):
            grid.setdefault(cell, "hazard")
    return grid


def _feature_text(items: list) -> str:
    parts = []
    for item in items:
        if isinstance(item, dict):
            parts.extend(str(value) for value in item.values() if value not in (None, ""))
        else:
            parts.append(str(item))
    return " ".join(parts).lower()


def _apply_authored_cell_features(grid: dict, features: list, *, default_terrain: str) -> bool:
    placed = False
    for feature in features:
        if not isinstance(feature, dict):
            continue
        feature_cells = _feature_cells(feature)
        if not feature_cells:
            continue
        cell_metadata = {
            key: value
            for key, value in feature.items()
            if key not in {"cell", "cells", "position", "positions"}
        }
        cell_metadata.setdefault("terrain", _default_feature_terrain(feature, default_terrain))
        for cell in feature_cells:
            grid[cell] = dict(cell_metadata)
            placed = True
    return placed


def _feature_cells(feature: dict) -> list[str]:
    raw_values = []
    for key in ("cells", "cell", "positions", "position"):
        value = feature.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, (list, tuple)):
            raw_values.extend(value)
        else:
            raw_values.append(value)

    cells: list[str] = []
    for value in raw_values:
        cell = _coerce_grid_cell(value)
        if cell and cell not in cells:
            cells.append(cell)
    return cells


def _default_feature_terrain(feature: dict, fallback: str) -> str:
    existing = str(
        feature.get("terrain")
        or feature.get("type")
        or feature.get("kind")
        or feature.get("category")
        or ""
    ).strip().lower()
    if existing:
        return existing.replace("-", "_").replace(" ", "_")

    text = _feature_text([feature])
    if fallback == "terrain":
        if "difficult" in text or "sparking" in text:
            return "difficult"
        if "wall" in text or "cover" in text:
            return "wall"
    return fallback


def _coerce_grid_cell(value) -> str | None:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if "_" in raw:
            x, y = raw.split("_", 1)
        elif "," in raw:
            x, y = raw.split(",", 1)
        else:
            return raw
    elif isinstance(value, dict):
        x, y = value.get("x"), value.get("y")
    else:
        return None
    try:
        return f"{int(x)}_{int(y)}"
    except (TypeError, ValueError):
        return None


def _initial_combat_positions(
    characters: list,
    enemies: list[dict],
    encounter_template: dict | None,
) -> dict:
    positions = {}
    occupied: set[tuple[int, int]] = set()
    for index, character in enumerate(characters):
        pos = {"x": 2, "y": 3 + index}
        positions[str(character.id)] = pos
        occupied.add((pos["x"], pos["y"]))

    roles = _enemy_roles_by_name(encounter_template)
    for index, enemy in enumerate(enemies):
        role = roles.get(str(enemy.get("name") or "").lower(), "frontliner")
        pos = _enemy_position_for_role(role, index, occupied) if encounter_template else {"x": 17, "y": 8 + index}
        positions[enemy["id"]] = pos
        occupied.add((pos["x"], pos["y"]))
    return positions


def _enemy_roles_by_name(encounter_template: dict | None) -> dict[str, str]:
    roles = {}
    for item in (encounter_template or {}).get("enemy_roles") or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        roles[str(item.get("name")).lower()] = str(item.get("role") or "frontliner").lower()
    return roles


def _enemy_position_for_role(role: str, index: int, occupied: set[tuple[int, int]]) -> dict:
    if role in {"caster", "artillery", "controller"}:
        candidates = [(18, 4), (18, 7), (17, 5), (17, 8)]
    elif role in {"skirmisher", "lurker"}:
        candidates = [(16, 3), (16, 9), (15, 2), (15, 10)]
    elif role in {"defender", "brute"}:
        candidates = [(15, 5), (15, 7), (14, 6), (16, 6)]
    else:
        candidates = [(15, 6), (15, 5), (15, 7), (16, 6)]

    for x, y in [*candidates, (17, 8 + index)]:
        if 0 <= x < 20 and 0 <= y < 12 and (x, y) not in occupied:
            return {"x": x, "y": y}
    return {"x": 17, "y": max(0, min(11, 8 + index))}

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
