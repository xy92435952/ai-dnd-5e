"""Reusable production-like seed data for local smoke testing."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

import bcrypt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character, CombatState, GameLog, Module, Session, User
from services.character_creation_service import build_starting_equipment
from services.combat_turn_state_service import DEFAULT_TURN_STATE
from services.dnd_rules import (
    calc_derived,
    get_class_resource_defaults,
    roll_initiative,
)
from services.exploration_reaction_service import maybe_create_feather_fall_prompt


SMOKE_USER_PASSWORD = "smoke-password"
SMOKE_SCENARIO_VERSION = 1


@dataclass(frozen=True)
class SmokeScenarioResult:
    slug: str
    variant: str
    user_id: str
    username: str
    password: str
    module_id: str
    character_id: str
    companion_ids: tuple[str, ...]
    session_id: str
    combat_state_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "variant": self.variant,
            "username": self.username,
            "password": self.password,
            "user_id": self.user_id,
            "module_id": self.module_id,
            "character_id": self.character_id,
            "companion_ids": list(self.companion_ids),
            "session_id": self.session_id,
            "combat_state_id": self.combat_state_id,
            "login_hint": {
                "username": self.username,
                "password": self.password,
            },
        }


async def seed_smoke_scenario(
    db: AsyncSession,
    *,
    slug: str = "codex_smoke",
    password: str = SMOKE_USER_PASSWORD,
    variant: str = "standard",
) -> SmokeScenarioResult:
    """Create or replace a deterministic smoke-test module, party, session and combat."""
    clean_slug = _clean_slug(slug)
    clean_variant = _normalize_variant(variant)
    ids = _SmokeIds(clean_slug)

    await _delete_existing(db, ids)

    user = User(
        id=ids.user_id,
        username=f"test_{clean_slug}",
        password_hash=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        display_name="Smoke Test Player",
    )
    module = Module(
        id=ids.module_id,
        user_id=ids.user_id,
        name=f"__test_module_smoke_{clean_slug}",
        file_path="seeded://smoke-scenario",
        file_type="seed",
        parsed_content=build_smoke_module_content(),
        level_min=2,
        level_max=3,
        recommended_party_size=3,
        parse_status="done",
        parse_error=None,
    )
    hero = _build_character(
        character_id=ids.character_id,
        user_id=ids.user_id,
        name="Smoke Sentinel",
        race="Human",
        char_class="Fighter",
        subclass="Champion",
        level=3,
        background="Soldier",
        ability_scores={"str": 16, "dex": 13, "con": 14, "int": 10, "wis": 12, "cha": 10},
        proficient_skills=["Athletics", "Perception"],
        fighting_style="Defense",
        equipment_choice=0,
        is_player=True,
    )
    companion = _build_character(
        character_id=ids.companion_id,
        user_id=None,
        name="Mara Quickstep",
        race="Halfling",
        char_class="Rogue",
        subclass="Thief",
        level=3,
        background="Urchin",
        ability_scores={"str": 8, "dex": 16, "con": 12, "int": 13, "wis": 14, "cha": 12},
        proficient_skills=["Stealth", "Investigation"],
        fighting_style=None,
        equipment_choice=0,
        is_player=False,
        personality="Careful scout who spots traps before the party rushes in.",
        speech_style="Dry, clipped, practical.",
        combat_preference="Flank enemies and protect downed allies.",
        catchphrase="Quiet feet, open eyes.",
        backstory="Mara knows the old aqueduct routes under the gatehouse.",
    )
    session = Session(
        id=ids.session_id,
        user_id=ids.user_id,
        module_id=ids.module_id,
        player_character_id=ids.character_id,
        current_scene=(
            "Rain ticks against the brass gatehouse while a damaged sentry "
            "asks the party to prove they can stabilize the crossing."
        ),
        session_history="Smoke scenario seeded for repeatable manual and automated checks.",
        game_state={
            "scenario_seed": {
                "slug": clean_slug,
                "version": SMOKE_SCENARIO_VERSION,
            },
            "companion_ids": [ids.companion_id],
            "scene_index": 0,
            "flags": {"met_keeper_mara": True, "gate_alarm_active": True},
            "dm_style": "classic",
            "last_turn": {
                "action": "Arrive at the Clockwork Crossing",
                "source": "seed",
            },
            "trap_states": {
                "gatehouse_tripwire": {
                    "id": "gatehouse_tripwire",
                    "name": "Gatehouse tripwire",
                    "status": "discovered",
                    "armed": True,
                    "dc": 13,
                }
            },
            "player_choices": [
                {
                    "id": "inspect_tripwire",
                    "text": "Inspect the tripwire before crossing.",
                    "skill_check": True,
                    "kind": "investigation",
                    "ability": "int",
                    "dc": 13,
                },
                {
                    "id": "parley_sentry",
                    "text": "Ask the brass sentry who damaged the gate.",
                    "skill_check": False,
                    "kind": "dialogue",
                },
            ],
        },
        campaign_state={
            "quest_log": [
                {
                    "quest": "Stabilize the Clockwork Crossing",
                    "status": "active",
                    "outcome": "",
                }
            ],
            "npc_registry": {
                "Keeper Mara": {
                    "relationship": "cautious ally",
                    "key_facts": ["Knows the gate schedule", "Wants minimal bloodshed"],
                    "promises": [],
                }
            },
            "key_decisions": ["Accepted Keeper Mara's request to investigate the gatehouse."],
            "world_flags": {"clockwork_gate_unstable": True},
            "clues": [
                {
                    "text": "Fresh scorch marks point toward a training construct malfunction.",
                    "category": "hazard",
                    "is_new": True,
                }
            ],
        },
        save_name=f"Smoke Scenario - {clean_slug}",
        combat_active=True,
    )
    hero.session_id = ids.session_id
    companion.session_id = ids.session_id

    enemies = build_smoke_enemies()
    combatants = [
        {
            "id": ids.character_id,
            "character_id": ids.character_id,
            "name": hero.name,
            "initiative": (hero.derived or {}).get("initiative", 0),
            "is_player": True,
            "is_enemy": False,
        },
        {
            "id": ids.companion_id,
            "character_id": ids.companion_id,
            "name": companion.name,
            "initiative": (companion.derived or {}).get("initiative", 0),
            "is_player": False,
            "is_enemy": False,
        },
        *enemies,
    ]
    turn_order = roll_initiative(combatants)
    combat = CombatState(
        id=ids.combat_state_id,
        session_id=ids.session_id,
        grid_data={
            "7_4": "wall",
            "7_5": "wall",
            "10_7": "difficult",
            "11_7": "difficult",
        },
        entity_positions={
            ids.character_id: {"x": 3, "y": 5},
            ids.companion_id: {"x": 3, "y": 6},
            "enemy_smoke_construct": {"x": 12, "y": 5},
            "enemy_smoke_spark": {"x": 13, "y": 7},
        },
        turn_order=turn_order,
        current_turn_index=0,
        round_number=1,
        combat_log=[
            "Smoke scenario begins with a live tactical encounter.",
        ],
        turn_states={
            combatant["id"]: dict(DEFAULT_TURN_STATE)
            for combatant in combatants
        },
    )
    game_state = dict(session.game_state or {})
    game_state["enemies"] = enemies
    game_state["encounter_balance"] = {
        "party_size": 2,
        "average_level": 3,
        "monster_xp": 300,
        "adjusted_xp": 450,
        "difficulty": "medium",
        "thresholds": {"easy": 150, "medium": 300, "hard": 450, "deadly": 800},
    }
    _apply_smoke_variant(clean_variant, ids, hero, companion, session, combat, game_state)
    session.game_state = game_state

    db.add_all([
        user,
        module,
        hero,
        companion,
        session,
        combat,
        GameLog(
            session_id=ids.session_id,
            role="dm",
            content=session.current_scene,
            log_type="narrative",
        ),
        GameLog(
            session_id=ids.session_id,
            role="system",
            content="Smoke seed prepared combat, trap, quest, and checkpoint state.",
            log_type="system",
        ),
    ])
    await db.commit()

    return SmokeScenarioResult(
        slug=clean_slug,
        variant=clean_variant,
        user_id=ids.user_id,
        username=user.username,
        password=password,
        module_id=ids.module_id,
        character_id=ids.character_id,
        companion_ids=(ids.companion_id,),
        session_id=ids.session_id,
        combat_state_id=ids.combat_state_id,
    )


def build_smoke_module_content() -> dict[str, Any]:
    return {
        "setting": "The Clockwork Crossing",
        "tone": "Heroic tactical fantasy with clear rules hooks.",
        "plot_summary": (
            "A compact gatehouse controls an unstable planar crossing. Keeper Mara "
            "needs the party to investigate sabotage, handle a live trap, and stop "
            "two malfunctioning constructs before the gate tears open."
        ),
        "level_min": 2,
        "level_max": 3,
        "recommended_party_size": 3,
        "scenes": [
            {
                "title": "Rain at the Gatehouse",
                "description": (
                    "The party arrives during a storm. A visible tripwire, a damaged "
                    "sentry, and scorch marks all point toward a construct malfunction."
                ),
                "choices": [
                    {
                        "text": "Inspect the tripwire.",
                        "skill_check": True,
                        "kind": "investigation",
                        "dc": 13,
                    },
                    {
                        "text": "Question Keeper Mara.",
                        "skill_check": False,
                        "kind": "dialogue",
                    },
                ],
            },
            {
                "title": "Training Yard",
                "description": (
                    "Two constructs patrol near low walls and a sparking patch of "
                    "difficult terrain."
                ),
            },
        ],
        "npcs": [
            {
                "name": "Keeper Mara",
                "role": "Gate warden",
                "motivation": "Stabilize the crossing without killing the constructs.",
                "disposition": "cautious ally",
            }
        ],
        "monsters": [
            {
                "name": "Clockwork Training Construct",
                "cr": "1",
                "xp": 200,
                "ac": 14,
                "hp": 22,
                "speed": 30,
                "ability_scores": {"str": 14, "dex": 12, "con": 14, "int": 3, "wis": 10, "cha": 6},
                "resistances": ["poison"],
                "condition_immunities": ["poisoned", "charmed"],
                "multiattack": 1,
                "actions": [
                    {
                        "name": "Slam",
                        "type": "melee_attack",
                        "attack_bonus": 4,
                        "damage_dice": "1d8+2",
                        "damage_type": "bludgeoning",
                        "range": 5,
                    }
                ],
                "tactics": "Hold the gate line and attack the closest armed intruder.",
            },
            {
                "name": "Voltaic Spark",
                "cr": "1/2",
                "xp": 100,
                "ac": 13,
                "hp": 15,
                "speed": 40,
                "ability_scores": {"str": 6, "dex": 16, "con": 12, "int": 4, "wis": 10, "cha": 8},
                "immunities": ["lightning"],
                "actions": [
                    {
                        "name": "Arc Lash",
                        "type": "melee_attack",
                        "attack_bonus": 5,
                        "damage_dice": "1d6+3",
                        "damage_type": "lightning",
                        "range": 5,
                    }
                ],
                "tactics": "Skirmish around difficult terrain and pressure isolated targets.",
            },
        ],
        "magic_items": [
            {
                "name": "Gate Token",
                "rarity": "common",
                "description": "A brass token used to stabilize one minor gate surge.",
            }
        ],
        "key_rewards": ["Gate Token", "25 gp"],
    }


def build_smoke_enemies() -> list[dict[str, Any]]:
    return [
        {
            "id": "enemy_smoke_construct",
            "name": "Clockwork Training Construct",
            "hp_current": 22,
            "hp_max": 22,
            "cr": "1",
            "xp": 200,
            "ac": 14,
            "conditions": [],
            "dead": False,
            "ability_scores": {"str": 14, "dex": 12, "con": 14, "int": 3, "wis": 10, "cha": 6},
            "attack_bonus": 4,
            "damage_dice": "1d8+2",
            "damage_type": "bludgeoning",
            "speed": 30,
            "resistances": ["poison"],
            "immunities": [],
            "vulnerabilities": [],
            "condition_immunities": ["poisoned", "charmed"],
            "special_abilities": [],
            "actions": [
                {
                    "name": "Slam",
                    "type": "melee_attack",
                    "attack_bonus": 4,
                    "damage_dice": "1d8+2",
                    "damage_type": "bludgeoning",
                    "range": 5,
                }
            ],
            "multiattack": 1,
            "attacks_max": 1,
            "initiative": 1,
            "is_player": False,
            "is_enemy": True,
            "derived": {"hp_max": 22, "ac": 14, "initiative": 1, "attack_bonus": 4},
        },
        {
            "id": "enemy_smoke_spark",
            "name": "Voltaic Spark",
            "hp_current": 15,
            "hp_max": 15,
            "cr": "1/2",
            "xp": 100,
            "ac": 13,
            "conditions": [],
            "dead": False,
            "ability_scores": {"str": 6, "dex": 16, "con": 12, "int": 4, "wis": 10, "cha": 8},
            "attack_bonus": 5,
            "damage_dice": "1d6+3",
            "damage_type": "lightning",
            "speed": 40,
            "resistances": [],
            "immunities": ["lightning"],
            "vulnerabilities": [],
            "condition_immunities": [],
            "special_abilities": [],
            "actions": [
                {
                    "name": "Arc Lash",
                    "type": "melee_attack",
                    "attack_bonus": 5,
                    "damage_dice": "1d6+3",
                    "damage_type": "lightning",
                    "range": 5,
                }
            ],
            "multiattack": 1,
            "attacks_max": 1,
            "initiative": 3,
            "is_player": False,
            "is_enemy": True,
            "derived": {"hp_max": 15, "ac": 13, "initiative": 3, "attack_bonus": 5},
        },
    ]


async def _delete_existing(db: AsyncSession, ids: "_SmokeIds") -> None:
    await db.execute(delete(GameLog).where(GameLog.session_id == ids.session_id))
    await db.execute(delete(CombatState).where(CombatState.session_id == ids.session_id))
    await db.execute(delete(Session).where(Session.id == ids.session_id))
    await db.execute(delete(Character).where(Character.id.in_([ids.character_id, ids.companion_id])))
    await db.execute(delete(Module).where(Module.id == ids.module_id))
    await db.execute(delete(User).where(User.id == ids.user_id))
    await db.commit()


def _build_character(
    *,
    character_id: str,
    user_id: str | None,
    name: str,
    race: str,
    char_class: str,
    subclass: str,
    level: int,
    background: str,
    ability_scores: dict[str, int],
    proficient_skills: list[str],
    fighting_style: str | None,
    equipment_choice: int,
    is_player: bool,
    personality: str | None = None,
    speech_style: str | None = None,
    combat_preference: str | None = None,
    catchphrase: str | None = None,
    backstory: str | None = None,
) -> Character:
    equipment = build_starting_equipment(char_class, equipment_choice, background=background)
    derived = calc_derived(
        char_class,
        level,
        ability_scores,
        subclass=subclass,
        fighting_style=fighting_style,
        equipment=equipment,
        race=race,
        proficient_skills=proficient_skills,
    )
    return Character(
        id=character_id,
        user_id=user_id,
        is_player=is_player,
        name=name,
        race=race,
        char_class=char_class,
        subclass=subclass,
        level=level,
        background=background,
        alignment="Neutral Good",
        ability_scores=ability_scores,
        derived=derived,
        hp_current=derived["hp_max"],
        spell_slots=dict(derived.get("spell_slots_max") or {}),
        known_spells=[],
        prepared_spells=[],
        cantrips=[],
        proficient_skills=proficient_skills,
        proficient_saves=["str", "con"] if char_class == "Fighter" else ["dex", "int"],
        languages=["Common"],
        tool_proficiencies=[],
        feats=[],
        equipment=equipment,
        fighting_style=fighting_style,
        conditions=[],
        condition_durations={},
        death_saves=None,
        hit_dice_remaining=level,
        class_resources=get_class_resource_defaults(char_class, level, subclass=subclass),
        personality=personality,
        speech_style=speech_style,
        combat_preference=combat_preference,
        catchphrase=catchphrase,
        backstory=backstory,
    )


def _clean_slug(slug: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in slug).strip("_")
    return (cleaned or "codex_smoke")[:32]


def _normalize_variant(variant: str | None) -> str:
    value = (variant or "standard").strip().lower().replace("-", "_")
    aliases = {
        "default": "standard",
        "normal": "standard",
        "deathsave": "death_save",
        "death_saves": "death_save",
        "featherfall": "feather_fall",
    }
    value = aliases.get(value, value)
    allowed = {"standard", "death_save", "reaction", "feather_fall"}
    if value not in allowed:
        raise ValueError(f"Unsupported smoke scenario variant: {variant}")
    return value


def _set_current_turn(combat: CombatState, character_id: str) -> None:
    for index, entry in enumerate(combat.turn_order or []):
        if str(entry.get("character_id")) == str(character_id):
            combat.current_turn_index = index
            return


def _apply_smoke_variant(
    variant: str,
    ids: "_SmokeIds",
    hero: Character,
    companion: Character,
    session: Session,
    combat: CombatState,
    game_state: dict[str, Any],
) -> None:
    if variant == "standard":
        return

    game_state["scenario_seed_variant"] = variant
    combat_log = list(combat.combat_log or [])
    turn_states = dict(combat.turn_states or {})
    hero_state = dict(turn_states.get(ids.character_id) or DEFAULT_TURN_STATE)

    if variant == "death_save":
        hero.hp_current = 0
        hero.death_saves = {"successes": 1, "failures": 1, "stable": False}
        hero_state.update({
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
        })
        turn_states[ids.character_id] = hero_state
        combat.turn_states = turn_states
        _set_current_turn(combat, ids.character_id)
        combat_log.append("Smoke variant prepared a dying player turn for death-save UI checks.")
        combat.combat_log = combat_log
        session.current_scene = (
            "Smoke Sentinel is down but not dead. The next decision is a death save."
        )
        return

    if variant == "feather_fall":
        companion.char_class = "Wizard"
        companion.subclass = "Evocation"
        companion.known_spells = ["Feather Fall"]
        companion.spell_slots = {"1st": 1}
        companion.class_resources = get_class_resource_defaults(
            "Wizard",
            companion.level,
            subclass=companion.subclass,
        )
        session.combat_active = False
        fall_trap = {
            "id": "gatehouse_drop_shaft",
            "name": "Gatehouse drop shaft",
            "description": "A cracked brass floor panel drops a creature into a deep shaft.",
            "damage": "6",
            "damage_type": "fall",
            "fall_distance_ft": 30,
            "save_ability": "dex",
            "save_dc": 99,
            "half_on_save": True,
        }
        game_state["trap_states"] = {
            **dict(game_state.get("trap_states") or {}),
            "gatehouse_drop_shaft": {
                "id": "gatehouse_drop_shaft",
                "name": "Gatehouse drop shaft",
                "status": "triggered",
                "discovered": True,
                "armed": False,
                "triggered": True,
            },
        }
        game_state["player_choices"] = []
        session.game_state = game_state
        prompt = maybe_create_feather_fall_prompt(
            session=session,
            trap=fall_trap,
            target=hero,
            characters=[hero, companion],
            trigger_actor_user_id=session.user_id,
        )
        if prompt:
            game_state.clear()
            game_state.update(session.game_state or {})
            game_state["last_turn"] = {
                "player_choices": [],
                "needs_check": None,
                "action_type": "trap_trigger",
                "source": "seed",
                "pending_exploration_reaction_id": prompt.get("id"),
            }
        combat_log.append("Smoke variant prepared a pending exploration Feather Fall prompt.")
        combat.combat_log = combat_log
        session.current_scene = (
            "The gatehouse floor gives way beneath Smoke Sentinel. Mara Quickstep, "
            "now carrying a prepared Feather Fall spell for this smoke check, can "
            "spend her reaction before the fall damage lands."
        )
        return

    if variant == "reaction":
        incoming_damage = 9
        hp_before = int(hero.hp_current or 0)
        hero.hp_current = max(0, hp_before - incoming_damage)
        hero.known_spells = ["Shield"]
        hero.spell_slots = {**dict(hero.spell_slots or {}), "1st": 1}
        hero_state.update({
            "reaction_used": False,
            "pending_attack_reaction": {
                "trigger": "incoming_attack",
                "attacker_id": "enemy_smoke_construct",
                "attacker_name": "Clockwork Training Construct",
                "target_id": ids.character_id,
                "reactor_character_id": ids.character_id,
                "reactor_name": hero.name,
                "incoming_damage": incoming_damage,
                "target_hp_before_damage": hp_before,
                "attack_roll": 20,
                "player_ac": (hero.derived or {}).get("ac", 10),
                "events": [{
                    "attacker_id": "enemy_smoke_construct",
                    "attacker_name": "Clockwork Training Construct",
                    "target_id": ids.character_id,
                    "hit": True,
                    "attack_total": 20,
                    "target_ac": (hero.derived or {}).get("ac", 10),
                    "damage": incoming_damage,
                    "damage_type": "bludgeoning",
                }],
                "available_reactions": [{
                    "id": "shield",
                    "name": "Shield",
                    "type": "shield",
                    "cost": "1st-level spell slot",
                    "slot_level": "1st",
                    "slots_remaining": 1,
                    "effect": "+5 AC（持续到你的下个回合开始）",
                    "resulting_ac": (hero.derived or {}).get("ac", 10) + 5,
                    "damage_prevented": incoming_damage,
                    "blocked_attacks": 1,
                }],
                "options": [{
                    "type": "shield",
                    "target_id": "enemy_smoke_construct",
                    "character_id": ids.character_id,
                    "label": "Shield - +5 AC（持续到你的下个回合开始）",
                    "cost": "1st-level spell slot",
                    "damage_prevented": incoming_damage,
                }],
            },
        })
        turn_states[ids.character_id] = hero_state
        combat.turn_states = turn_states
        _set_current_turn(combat, ids.character_id)
        combat_log.append("Smoke variant prepared a post-attack pending Shield reaction prompt.")
        combat.combat_log = combat_log
        session.current_scene = (
            "A construct strike has landed, but Smoke Sentinel can still answer with Shield."
        )


class _SmokeIds:
    def __init__(self, slug: str):
        self.slug = slug
        self.user_id = _stable_uuid(slug, "user")
        self.module_id = _stable_uuid(slug, "module")
        self.character_id = _stable_uuid(slug, "character")
        self.companion_id = _stable_uuid(slug, "companion")
        self.session_id = _stable_uuid(slug, "session")
        self.combat_state_id = _stable_uuid(slug, "combat")


def _stable_uuid(slug: str, namespace: str) -> str:
    digest = hashlib.sha1(f"{slug}:{namespace}".encode("utf-8")).hexdigest()
    return str(uuid.UUID(digest[:32]))
