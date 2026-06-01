from typing import Any

from services.combat_grid_service import chebyshev_distance
from services.combat_resistance_service import apply_character_damage_resistance, is_fire_damage
from services.combat_service import CombatService
from services.encounter_template_service import normalize_tactical_role

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
    actor: dict[str, Any] | None = None,
    positions: dict[str, Any] | None = None,
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
        pressured_target = choose_role_pressured_attack_target(
            actor=actor,
            candidates=alive_characters,
            positions=positions or {},
        )
        if pressured_target:
            return pressured_target
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


def choose_role_pressured_attack_target(
    *,
    actor: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    positions: dict[str, Any],
) -> dict[str, Any] | None:
    """Pick a target for explicit striker/skirmisher enemies before the generic HP fallback."""
    if not actor or not actor.get("tactical_role"):
        return None

    role = normalize_tactical_role(actor.get("tactical_role"), "")
    alive_candidates = [
        candidate
        for candidate in candidates
        if _hp_current(candidate) > 0
    ]
    if not alive_candidates:
        return None

    if role == "striker":
        return min(
            alive_candidates,
            key=lambda target: (
                _striker_pressure_score(target),
                _hp_current(target),
                _target_ac(target),
                str(target.get("id") or ""),
            ),
        )

    if role == "skirmisher":
        return min(
            alive_candidates,
            key=lambda target: (
                _skirmisher_pressure_score(actor, target, alive_candidates, positions),
                _hp_current(target),
                _target_ac(target),
                str(target.get("id") or ""),
            ),
        )

    return None


def _striker_pressure_score(target: dict[str, Any]) -> float:
    hp_current = _hp_current(target)
    hp_max = _hp_max(target)
    ac = _target_ac(target)
    score = hp_current * 4 + ac

    if hp_current <= max(6, int(hp_max * 0.25)):
        score -= 36
    if _hp_ratio(target) <= 0.35:
        score -= 10
    if _is_concentrating(target):
        score -= 28
    if ac <= 13:
        score -= 4
    return score


def _skirmisher_pressure_score(
    actor: dict[str, Any],
    target: dict[str, Any],
    candidates: list[dict[str, Any]],
    positions: dict[str, Any],
) -> float:
    hp_current = _hp_current(target)
    ac = _target_ac(target)
    score = hp_current * 2 + ac

    nearest_party_distance = _nearest_other_party_distance(target, candidates, positions)
    if nearest_party_distance != 999:
        score -= min(nearest_party_distance, 4) * 5
        if nearest_party_distance <= 1:
            score += 16
        else:
            score -= 10

    actor_pos = positions.get(str(actor.get("id") or ""))
    target_pos = positions.get(str(target.get("id") or ""))
    if actor_pos and target_pos:
        actor_distance = chebyshev_distance(actor_pos, target_pos)
        if actor_distance > 6:
            score += (actor_distance - 6) * 4

    if _is_concentrating(target):
        score -= 12
    if ac <= 13:
        score -= 4
    return score


def _nearest_other_party_distance(
    target: dict[str, Any],
    candidates: list[dict[str, Any]],
    positions: dict[str, Any],
) -> int:
    target_id = str(target.get("id") or "")
    target_pos = positions.get(target_id)
    if not target_pos:
        return 999

    distances = []
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "")
        if candidate_id == target_id or _hp_current(candidate) <= 0:
            continue
        candidate_pos = positions.get(candidate_id)
        if candidate_pos:
            distances.append(chebyshev_distance(target_pos, candidate_pos))
    return min(distances, default=999)


def _is_concentrating(target: dict[str, Any]) -> bool:
    concentration = target.get("concentration")
    if isinstance(concentration, dict):
        return bool(concentration.get("spell_name") or concentration.get("spell") or concentration.get("name"))
    return bool(concentration)


def _hp_ratio(target: dict[str, Any]) -> float:
    return _hp_current(target) / _hp_max(target)


def _hp_current(target: dict[str, Any]) -> int:
    return max(0, int(target.get("hp_current", 0) or 0))


def _hp_max(target: dict[str, Any]) -> int:
    derived = target.get("derived") or {}
    return max(1, int(target.get("hp_max") or derived.get("hp_max") or _hp_current(target) or 1))


def _target_ac(target: dict[str, Any]) -> int:
    derived = target.get("derived") or {}
    return int(target.get("ac") or derived.get("ac") or 10)


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
