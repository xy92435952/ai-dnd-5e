import json

from schemas.game_schemas import GameState
from services.context_builder_multiplayer import build_multiplayer_context
from services.dnd_rules import get_effective_derived, get_effective_hp_base
from services.dm_styles import get_dm_style

ENEMY_FIELDS = [
    "id", "name", "hp_current", "hp_max", "ac", "conditions",
    "actions", "ability_scores", "speed", "resistances", "immunities",
    "special_abilities", "tactics", "dead",
]

CHAR_FIELDS = [
    "id", "name", "race", "char_class", "level",
    "hp_current", "hp_max", "ac", "initiative",
    "proficiency_bonus", "attack_bonus", "spell_save_dc",
    "ability_modifiers", "spell_slots", "conditions",
    "death_saves", "concentration", "known_spells",
    "cantrips", "equipped", "active_effects",
    "proficient_skills", "proficient_saves",
    "is_player", "personality", "backstory",
    "speech_style", "combat_preference", "catchphrase",
]


def build_character_snapshot(char) -> dict:
    base_derived = char.derived or {}
    derived = get_effective_derived(char)
    base_hp_max = get_effective_hp_base(char, base_derived)
    return {
        "id": char.id,
        "name": char.name,
        "race": char.race,
        "char_class": char.char_class,
        "level": char.level,
        "hp_current": char.hp_current,
        "hp_max": derived.get("hp_max", char.hp_current),
        "base_hp_max": base_hp_max,
        "ac": derived.get("ac", 10),
        "initiative": derived.get("initiative", 0),
        "proficiency_bonus": derived.get("proficiency_bonus", 2),
        "attack_bonus": derived.get("attack_bonus", 2),
        "spell_save_dc": derived.get("spell_save_dc", 10),
        "ability_modifiers": derived.get("ability_modifiers", {}),
        "spell_slots": char.spell_slots or {},
        "conditions": char.conditions or [],
        "death_saves": char.death_saves or {"successes": 0, "failures": 0, "stable": False},
        "concentration": char.concentration,
        "known_spells": char.known_spells or [],
        "cantrips": char.cantrips or [],
        "proficient_skills": char.proficient_skills or [],
        "proficient_saves": char.proficient_saves or [],
        "is_player": char.is_player,
        "personality": char.personality or "",
        "backstory": char.backstory or "",
        "speech_style": char.speech_style or "",
        "combat_preference": char.combat_preference or "",
        "catchphrase": char.catchphrase or "",
        "gold": (getattr(char, "equipment", {}) or {}).get("gold", 0),
        "equipped": getattr(char, "equipment", {}) or {},
        "active_effects": getattr(char, "active_effects", {}) or {},
    }


def build_game_state_payload(
    *,
    session,
    characters: list,
    combat_state=None,
    current_actor_id: str | None = None,
) -> dict:
    GameState.model_validate(session.game_state or {})

    actor_name = None
    if current_actor_id:
        for char in characters:
            if char.id == current_actor_id:
                actor_name = char.name
                break

    state = {
        "session_id": session.id,
        "combat_active": session.combat_active,
        "current_scene": session.current_scene or "",
        "round_number": 0,
        "characters": [],
        "enemies": [],
        "turn_order": [],
        "current_turn": None,
        "current_actor_id": current_actor_id,
        "current_actor_name": actor_name,
    }

    dm_style = get_dm_style((session.game_state or {}).get("dm_style"))
    state["dm_style"] = {
        "key": dm_style.key,
        "label": dm_style.label,
        "summary": dm_style.summary,
    }
    state["dm_style_prompt"] = dm_style.prompt

    if session.is_multiplayer:
        state["multiplayer_context"] = build_multiplayer_context(
            session=session,
            characters=characters,
            current_actor_id=current_actor_id,
        )

    state["characters"] = [build_character_snapshot(char) for char in characters]

    if session.combat_active and combat_state:
        state["round_number"] = combat_state.round_number
        state["turn_order"] = combat_state.turn_order or []
        state["current_turn"] = (
            combat_state.turn_order[combat_state.current_turn_index]["character_id"]
            if combat_state.turn_order else None
        )

        game_state_data = GameState.model_validate(session.game_state or {})
        for enemy in game_state_data.enemies:
            enemy_dict = enemy.model_dump()
            filtered = {k: enemy_dict[k] for k in ENEMY_FIELDS if k in enemy_dict}
            state["enemies"].append(filtered)

        state["entity_positions"] = combat_state.entity_positions or {}

    return state


def build_game_state_json(
    *,
    session,
    characters: list,
    combat_state=None,
    current_actor_id: str | None = None,
) -> str:
    return json.dumps(
        build_game_state_payload(
            session=session,
            characters=characters,
            combat_state=combat_state,
            current_actor_id=current_actor_id,
        ),
        ensure_ascii=False,
    )
