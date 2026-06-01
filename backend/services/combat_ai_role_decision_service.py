"""Deterministic tactical-role nudges for enemy AI decisions."""

from __future__ import annotations

from typing import Any

from services.combat_ai_spell_models import CONTROL_CONDITION_MAP, SLOT_KEYS
from services.combat_grid_service import chebyshev_distance
from services.combat_recharge_service import normalize_recharge_abilities
from services.dnd_rules import can_receive_ordinary_healing, get_effective_hp_max
from services.encounter_template_service import normalize_tactical_role
from services.spell_service import spell_service


SUPPORT_CONTROL_CONDITIONS = {"blessed", "divine_favor", "guided", "resistance"}


def apply_tactical_role_decision(
    *,
    actor: dict[str, Any],
    decision: dict[str, Any],
    all_characters: list[dict[str, Any]],
    all_enemies: list[dict[str, Any]],
    positions: dict[str, Any],
) -> dict[str, Any]:
    """Return a role-aware enemy decision without changing the turn executor contract."""
    action_type = str(decision.get("action_type") or "").lower()
    if action_type in {"spell", "special"} and decision.get("action_name"):
        return decision

    role = normalize_tactical_role(actor.get("tactical_role"), "striker")
    if role == "healer":
        return _healer_decision(actor, decision, all_enemies, positions) or decision
    if role == "controller":
        return (
            _controller_special_decision(actor, decision, all_characters)
            or _controller_spell_decision(actor, decision, all_characters, positions)
            or decision
        )
    if role == "defender":
        return _defender_guard_decision(actor, decision, all_enemies, positions) or decision
    return decision


def _healer_decision(
    actor: dict[str, Any],
    decision: dict[str, Any],
    all_enemies: list[dict[str, Any]],
    positions: dict[str, Any],
) -> dict[str, Any] | None:
    target = _most_wounded_enemy_ally(actor, all_enemies)
    if not target:
        return None

    spell = _best_spell(
        actor,
        predicate=lambda _name, data: data.get("type") == "heal",
        target_id=str(target.get("id")),
        positions=positions,
    )
    if not spell:
        return None

    spell_name, spell_data, spell_level = spell
    return _override(
        decision,
        action_type="spell",
        action_name=spell_name,
        target_id=str(target.get("id")),
        spell_level=spell_level if spell_level > 0 else None,
        reason=(
            "healer role: "
            f"{target.get('name', 'ally')} is at "
            f"{target.get('hp_current', 0)}/{_hp_max(target)} HP, using {spell_name}"
        ),
        role="healer",
        spell_data=spell_data,
    )


def _controller_special_decision(
    actor: dict[str, Any],
    decision: dict[str, Any],
    all_characters: list[dict[str, Any]],
) -> dict[str, Any] | None:
    target = _best_hostile_control_target(all_characters, condition=None)
    if not target:
        return None

    for ability in normalize_recharge_abilities(actor):
        if not ability.get("available", True):
            continue
        if not ability.get("damage_dice"):
            continue
        if not _is_control_recharge_ability(ability):
            continue
        return _override(
            decision,
            action_type="special",
            action_name=str(ability.get("name") or ""),
            target_id=str(target.get("id")),
            spell_level=None,
            reason=(
                "controller role: using available control recharge ability "
                f"{ability.get('name', 'special ability')}"
            ),
            role="controller",
        )
    return None


def _controller_spell_decision(
    actor: dict[str, Any],
    decision: dict[str, Any],
    all_characters: list[dict[str, Any]],
    positions: dict[str, Any],
) -> dict[str, Any] | None:
    def is_control_spell(name: str, data: dict[str, Any]) -> bool:
        return _offensive_control_condition(name, data) is not None

    spell = _best_spell(actor, predicate=is_control_spell, target_id=None, positions=positions)
    if not spell:
        return None

    spell_name, spell_data, spell_level = spell
    condition = _offensive_control_condition(spell_name, spell_data)
    target = _best_hostile_control_target(all_characters, condition=condition)
    if not target:
        return None

    return _override(
        decision,
        action_type="spell",
        action_name=spell_name,
        target_id=str(target.get("id")),
        spell_level=spell_level if spell_level > 0 else None,
        reason=f"controller role: applying {spell_name} to limit a high-value target",
        role="controller",
        spell_data=spell_data,
    )


def _defender_guard_decision(
    actor: dict[str, Any],
    decision: dict[str, Any],
    all_enemies: list[dict[str, Any]],
    positions: dict[str, Any],
) -> dict[str, Any] | None:
    if str(decision.get("action_type") or "").lower() not in {"attack", "dash", ""}:
        return None

    actor_hp_ratio = _hp_ratio(actor)
    if actor_hp_ratio <= 0.35:
        return None

    actor_id = str(actor.get("id") or "")
    actor_pos = positions.get(actor_id)
    for ally in all_enemies:
        if str(ally.get("id")) == actor_id or ally.get("hp_current", 0) <= 0:
            continue
        ally_role = normalize_tactical_role(ally.get("tactical_role"), "striker")
        if ally_role not in {"controller", "healer"} and _hp_ratio(ally) > 0.5:
            continue
        ally_pos = positions.get(str(ally.get("id")))
        if actor_pos and ally_pos and chebyshev_distance(actor_pos, ally_pos) > 1:
            continue
        return _override(
            decision,
            action_type="dodge",
            action_name=None,
            target_id=None,
            spell_level=None,
            reason=(
                "defender role: holding guard near "
                f"{ally.get('name', 'a vulnerable ally')}"
            ),
            role="defender",
        )
    return None


def _most_wounded_enemy_ally(
    actor: dict[str, Any],
    all_enemies: list[dict[str, Any]],
) -> dict[str, Any] | None:
    actor_id = str(actor.get("id") or "")
    candidates = []
    for enemy in all_enemies:
        if enemy.get("hp_current", 0) <= 0:
            continue
        if not can_receive_ordinary_healing(enemy):
            continue
        hp_max = _hp_max(enemy)
        hp_current = int(enemy.get("hp_current", 0) or 0)
        if hp_current >= hp_max:
            continue
        ratio = hp_current / hp_max
        threshold = 0.45 if str(enemy.get("id")) == actor_id else 0.55
        if ratio > threshold:
            continue
        candidates.append((ratio, 1 if str(enemy.get("id")) == actor_id else 0, str(enemy.get("id")), enemy))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[:3])
    return candidates[0][3]


def _best_hostile_control_target(
    all_characters: list[dict[str, Any]],
    *,
    condition: str | None,
) -> dict[str, Any] | None:
    candidates = []
    for character in all_characters:
        hp = int(character.get("hp_current", 0) or 0)
        if hp <= 0:
            continue
        if condition and condition in list(character.get("conditions") or []):
            continue
        hp_max = _hp_max(character)
        ac = int(character.get("ac") or (character.get("derived") or {}).get("ac") or 10)
        candidates.append((-hp_max, -ac, str(character.get("id")), character))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[:3])
    return candidates[0][3]


def _best_spell(
    actor: dict[str, Any],
    *,
    predicate,
    target_id: str | None,
    positions: dict[str, Any],
) -> tuple[str, dict[str, Any], int] | None:
    candidates = []
    for spell_name in _actor_spell_names(actor):
        resolved = _resolve_spell_name(spell_name)
        if not resolved:
            continue
        registry_name, spell_data = resolved
        if not predicate(registry_name, spell_data):
            continue
        slot_level = _available_spell_level(actor, spell_data)
        if slot_level is None:
            continue
        if target_id and not _spell_can_reach(actor, target_id, spell_data, positions):
            continue
        spell_range = _spell_range_tiles(spell_data)
        candidates.append((
            1 if int(spell_data.get("level") or 0) == 0 else 0,
            int(spell_data.get("level") or 0),
            -spell_range,
            registry_name,
            spell_data,
            slot_level,
        ))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[:4])
    selected = candidates[0]
    return selected[3], selected[4], selected[5]


def _actor_spell_names(actor: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("prepared_spells", "known_spells", "cantrips", "spells"):
        values = actor.get(key) or []
        if isinstance(values, dict):
            values = values.keys()
        if not isinstance(values, (list, tuple, set)):
            continue
        for value in values:
            text = str(value or "").strip()
            if text and text not in names:
                names.append(text)
    return names


def _resolve_spell_name(name: str) -> tuple[str, dict[str, Any]] | None:
    exact = spell_service.get(name)
    if exact:
        return name, exact

    normalized = _normalize_name(name)
    for spell in spell_service.get_all():
        registry_name = str(spell.get("name") or "")
        if _normalize_name(registry_name) == normalized:
            data = spell_service.get(registry_name) or dict(spell)
            return registry_name, data
        if _normalize_name(spell.get("name_en")) == normalized:
            data = spell_service.get(registry_name) or dict(spell)
            return registry_name, data
    return None


def _available_spell_level(actor: dict[str, Any], spell_data: dict[str, Any]) -> int | None:
    base_level = int(spell_data.get("level") or 0)
    if base_level <= 0:
        return 0
    slots = dict(actor.get("spell_slots") or {})
    for index, key in enumerate(SLOT_KEYS, start=1):
        if index < base_level:
            continue
        if int(slots.get(key) or 0) > 0:
            return index
    return None


def _spell_can_reach(
    actor: dict[str, Any],
    target_id: str,
    spell_data: dict[str, Any],
    positions: dict[str, Any],
) -> bool:
    actor_pos = positions.get(str(actor.get("id")))
    target_pos = positions.get(str(target_id))
    if not actor_pos or not target_pos:
        return True
    return chebyshev_distance(actor_pos, target_pos) <= _spell_range_tiles(spell_data)


def _spell_range_tiles(spell_data: dict[str, Any]) -> int:
    raw = spell_data.get("range")
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


def _offensive_control_condition(name: str, spell_data: dict[str, Any]) -> str | None:
    condition = (
        CONTROL_CONDITION_MAP.get(name)
        or CONTROL_CONDITION_MAP.get(str(spell_data.get("name_en") or ""))
        or str(spell_data.get("condition") or "")
    )
    if condition in SUPPORT_CONTROL_CONDITIONS:
        return None
    spell_type = str(spell_data.get("type") or "")
    if condition:
        return condition
    if spell_type == "control":
        return "controlled"
    return None


def _is_control_recharge_ability(ability: dict[str, Any]) -> bool:
    if any(ability.get(key) for key in (
        "condition",
        "condition_name",
        "condition_on_failed_save",
        "conditions_on_failed_save",
    )):
        return True
    text = " ".join(
        str(ability.get(key, ""))
        for key in ("name", "description", "extra_effects", "targeting", "area")
    ).lower()
    return any(marker in text for marker in (
        "restrain",
        "stun",
        "frighten",
        "paralyze",
        "poison",
        "prone",
        "slow",
        "web",
        "束缚",
        "震慑",
        "恐惧",
        "麻痹",
        "中毒",
        "减速",
    ))


def _hp_ratio(entity: dict[str, Any]) -> float:
    return int(entity.get("hp_current", 0) or 0) / _hp_max(entity)


def _hp_max(entity: dict[str, Any]) -> int:
    return max(1, int(entity.get("hp_max") or get_effective_hp_max(entity) or 1))


def _override(
    decision: dict[str, Any],
    *,
    action_type: str,
    action_name: str | None,
    target_id: str | None,
    spell_level: int | None,
    reason: str,
    role: str,
    spell_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = dict(decision)
    updated.update({
        "action_type": action_type,
        "action_name": action_name,
        "target_id": target_id,
        "spell_level": spell_level,
        "reason": reason,
        "_tactical_role_override": role,
    })
    if spell_data:
        updated["_tactical_role_spell_type"] = spell_data.get("type")
    return updated


def _normalize_name(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")
