from typing import Any

from services.combat_resistance_service import apply_character_damage_resistance, is_fire_damage
from services.combat_service import CombatService

svc = CombatService()


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


def target_conditions(
    *,
    target_data: dict[str, Any] | None = None,
    target_character=None,
) -> list[str]:
    """Return active target conditions for generic AI attack rules."""
    if target_character is not None:
        return list(getattr(target_character, "conditions", None) or [])
    if target_data:
        return list(target_data.get("conditions", []) or [])
    return []


def has_pack_tactics(enemy: dict[str, Any] | None) -> bool:
    if not enemy:
        return False
    if enemy.get("pack_tactics") is True:
        return True
    for ability in enemy.get("special_abilities") or []:
        name = str(ability.get("name") if isinstance(ability, dict) else ability).lower()
        description = str(ability.get("description", "") if isinstance(ability, dict) else "").lower()
        if "pack tactics" in name or "pack tactics" in description or "群体战术" in name or "群体战术" in description:
            return True
    return False


def pack_tactics_advantage(
    *,
    attacker: dict[str, Any] | None,
    target_id: str | None,
    allies: list[dict[str, Any]],
    positions: dict[str, Any],
    has_ally_adjacent_to,
) -> bool:
    if not attacker or not target_id or not has_pack_tactics(attacker):
        return False
    return bool(has_ally_adjacent_to(target_id, str(attacker.get("id", "")), allies, positions))
