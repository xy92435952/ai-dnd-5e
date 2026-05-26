from typing import Any

from services.combat_service import CombatService
from services.dnd_rules import _normalize_class

FIRE_DAMAGE_TYPES = {"fire", "火焰", "flame"}

svc = CombatService()


def is_fire_damage(damage_type: str) -> bool:
    return str(damage_type or "").strip().lower() in FIRE_DAMAGE_TYPES


def choose_ai_attack_target(
    *,
    decided_target_id: str | None,
    enemies_alive: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
    actor_is_enemy: bool,
    player,
    companions_alive: list[dict[str, Any]],
    combat_service: CombatService = svc,
) -> dict[str, Any] | None:
    """Resolve a decided AI target, falling back to the existing combat target heuristic."""
    alive_characters = [
        character
        for character in all_characters
        if character.get("hp_current", 0) > 0
    ]

    if decided_target_id:
        for target in enemies_alive:
            if str(target.get("id")) == str(decided_target_id):
                return target
        for target in alive_characters:
            if str(target.get("id")) == str(decided_target_id):
                return target

    if actor_is_enemy and alive_characters:
        return min(alive_characters, key=lambda x: x.get("hp_current", 999))

    player_payload = None
    if player:
        player_payload = {
            "id": getattr(player, "id", None),
            "hp_current": getattr(player, "hp_current", 0),
            "derived": getattr(player, "derived", {}) or {},
        }

    return combat_service.choose_ai_target(
        actor_is_enemy=actor_is_enemy,
        player=player_payload,
        allies=companions_alive,
        enemies_alive=enemies_alive,
    )


def infer_ai_is_ranged(
    *,
    archer,
    enemies: list[dict[str, Any]],
    actor_id: str,
) -> bool:
    """Infer whether the AI actor's default attack should use ranged range rules."""
    if archer and archer.equipment:
        weapons = (archer.equipment or {}).get("weapons", [])
        for weapon in weapons:
            properties = weapon.get("properties") or ""
            if isinstance(properties, list):
                properties = ",".join(properties)
            weapon_type = weapon.get("type", "")
            if (
                "远程" in properties
                or "ranged" in properties.lower()
                or weapon_type in ("简易远程武器", "军用远程武器")
            ):
                return True

    if not archer:
        for enemy in enemies:
            if str(enemy.get("id")) != str(actor_id):
                continue
            for action in enemy.get("actions", []):
                action_type = action.get("type", "")
                if "远程" in action_type or "ranged" in action_type.lower():
                    return True
            break

    return False


def target_is_dodging(
    *,
    combat,
    target_id: str | None,
    target_data: dict[str, Any] | None = None,
    target_character=None,
) -> bool:
    """Return whether the target is under the Dodge action's defensive state."""
    if not target_id:
        return False

    turn_state = (combat.turn_states or {}).get(str(target_id), {})
    if turn_state.get("dodging"):
        return True

    conditions = []
    if target_character is not None:
        conditions = list(getattr(target_character, "conditions", None) or [])
    elif target_data:
        conditions = list(target_data.get("conditions", []) or [])
    return "dodging" in conditions


def apply_character_damage_resistance(
    target_character,
    damage: int,
    damage_type: str,
) -> tuple[int, bool]:
    """Apply the AI attack path's existing Barbarian rage and fire-resistance reductions."""
    final_damage = damage
    resistance_applied = False

    if target_character and _normalize_class(target_character.char_class) == "Barbarian":
        class_resources = dict(target_character.class_resources or {})
        if class_resources.get("raging", False):
            subclass_effects = (target_character.derived or {}).get("subclass_effects", {})
            if subclass_effects.get("bear_totem"):
                if damage_type not in ("心灵", "psychic"):
                    final_damage = final_damage // 2
                    resistance_applied = True
            elif damage_type in (
                "钝击",
                "穿刺",
                "挥砍",
                "bludgeoning",
                "piercing",
                "slashing",
            ):
                final_damage = final_damage // 2
                resistance_applied = True

    if (
        not resistance_applied
        and target_character
        and "fire_resistance" in (target_character.conditions or [])
        and is_fire_damage(damage_type)
    ):
        final_damage = final_damage // 2
        resistance_applied = True

    return final_damage, resistance_applied
