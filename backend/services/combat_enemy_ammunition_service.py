from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class EnemyAttackActionSelection:
    action: dict[str, Any] | None
    is_ranged: bool
    unavailable_resource: dict[str, Any] | None = None
    switched_from_ranged: bool = False
    selection_reason: str | None = None
    damage_score: float | None = None


def select_enemy_attack_action(
    enemy: dict[str, Any] | None,
    *,
    preferred_is_ranged: bool,
    target_distance_tiles: int | None = None,
) -> EnemyAttackActionSelection:
    """Choose an enemy attack action while respecting tracked ammo/quantity."""
    actions = _attack_actions(enemy)
    if not actions:
        return EnemyAttackActionSelection(action=None, is_ranged=preferred_is_ranged)

    preferred = [action for action in actions if _action_is_ranged(action) is preferred_is_ranged]
    fallback = [action for action in actions if _action_is_ranged(action) is not preferred_is_ranged]

    if target_distance_tiles is not None:
        available_in_range = [
            action for action in actions
            if _resource_available(action) and _action_can_reach_distance(action, target_distance_tiles)
        ]
        if target_distance_tiles <= 1:
            melee_selected = _best_available([
                action for action in available_in_range if not _action_is_ranged(action)
            ])
            if melee_selected is not None:
                return EnemyAttackActionSelection(
                    action=melee_selected,
                    is_ranged=False,
                    selection_reason="adjacent_melee_damage",
                    damage_score=_damage_score(melee_selected),
                )
        selected = _best_available([
            action for action in available_in_range
            if _action_is_ranged(action) is preferred_is_ranged
        ])
        if selected is not None:
            return EnemyAttackActionSelection(
                action=selected,
                is_ranged=_action_is_ranged(selected),
                selection_reason="preferred_in_range_damage",
                damage_score=_damage_score(selected),
            )
        fallback_selected = _best_available([
            action for action in available_in_range
            if _action_is_ranged(action) is not preferred_is_ranged
        ])
        if fallback_selected is not None:
            return EnemyAttackActionSelection(
                action=fallback_selected,
                is_ranged=_action_is_ranged(fallback_selected),
                selection_reason="fallback_in_range_damage",
                damage_score=_damage_score(fallback_selected),
            )

    selected = _best_available(preferred)
    if selected is not None:
        return EnemyAttackActionSelection(
            action=selected,
            is_ranged=_action_is_ranged(selected),
            selection_reason="preferred_available_damage",
            damage_score=_damage_score(selected),
        )

    fallback_selected = _best_available(fallback)
    if fallback_selected is not None:
        return EnemyAttackActionSelection(
            action=fallback_selected,
            is_ranged=_action_is_ranged(fallback_selected),
            switched_from_ranged=preferred_is_ranged and not _action_is_ranged(fallback_selected),
            selection_reason="fallback_available_damage",
            damage_score=_damage_score(fallback_selected),
        )

    unavailable = next(
        (
            _unavailable_resource_payload(action)
            for action in [*preferred, *fallback]
            if _unavailable_resource_payload(action)
        ),
        None,
    )
    return EnemyAttackActionSelection(
        action=None,
        is_ranged=preferred_is_ranged,
        unavailable_resource=unavailable,
    )


def select_enemy_multiattack_actions(
    enemy: dict[str, Any] | None,
    *,
    preferred_is_ranged: bool,
    target_distance_tiles: int | None = None,
    attack_count: int = 1,
) -> list[EnemyAttackActionSelection]:
    """Choose the authored action for each attack in an enemy multiattack."""
    count = max(1, _as_int(attack_count, 1))
    if count <= 1:
        return [
            select_enemy_attack_action(
                enemy,
                preferred_is_ranged=preferred_is_ranged,
                target_distance_tiles=target_distance_tiles,
            )
        ]

    sequence = _multiattack_sequence_actions(
        enemy,
        target_distance_tiles=target_distance_tiles,
    )
    if not sequence:
        selection = select_enemy_attack_action(
            enemy,
            preferred_is_ranged=preferred_is_ranged,
            target_distance_tiles=target_distance_tiles,
        )
        return [selection for _ in range(count)]

    selections: list[EnemyAttackActionSelection] = []
    for action in sequence[:count]:
        if (
            _resource_available(action)
            and (
                target_distance_tiles is None
                or _action_can_reach_distance(action, target_distance_tiles)
            )
        ):
            selections.append(
                EnemyAttackActionSelection(
                    action=action,
                    is_ranged=_action_is_ranged(action),
                    selection_reason="multiattack_sequence",
                    damage_score=_damage_score(action),
                )
            )
        else:
            selections.append(
                select_enemy_attack_action(
                    enemy,
                    preferred_is_ranged=preferred_is_ranged,
                    target_distance_tiles=target_distance_tiles,
                )
            )

    while len(selections) < count:
        selections.append(
            select_enemy_attack_action(
                enemy,
                preferred_is_ranged=preferred_is_ranged,
                target_distance_tiles=target_distance_tiles,
            )
        )

    return selections


def consume_enemy_attack_action_resource(action: dict[str, Any] | None) -> dict[str, Any]:
    """Consume a selected enemy action resource in-place and return UI metadata."""
    if not isinstance(action, dict):
        return {}

    resource_type = _resource_type(action)
    if resource_type == "ammunition":
        if "ammo" not in action:
            return {}
        ammo = _as_int(action.get("ammo"), 0)
        if ammo <= 0:
            return _resource_payload(action, resource_type, consumed=False, unavailable=True)
        remaining = ammo - 1
        action["ammo"] = remaining
        return _resource_payload(
            action,
            resource_type,
            consumed=True,
            ammo_remaining=remaining,
        )

    if resource_type == "thrown_weapon":
        if "quantity" not in action:
            return {}
        quantity = _as_int(action.get("quantity"), 0)
        if quantity <= 0:
            return _resource_payload(action, resource_type, consumed=False, unavailable=True)
        remaining = max(quantity - 1, 0)
        action["quantity"] = remaining
        if remaining <= 0:
            action["available"] = False
        return _resource_payload(
            action,
            resource_type,
            consumed=True,
            quantity_remaining=remaining,
            weapon_removed=remaining <= 0,
        )

    return {}


def _attack_actions(enemy: dict[str, Any] | None) -> list[dict[str, Any]]:
    actions = (enemy or {}).get("actions") or []
    return [
        action
        for action in actions
        if isinstance(action, dict) and _is_attack_action(action)
    ]


def _is_attack_action(action: dict[str, Any]) -> bool:
    name = _norm(action.get("name") or action.get("action_name"))
    action_type = _norm(action.get("type"))
    if name in {"multiattack", "multi attack"} or action_type in {"multiattack", "multi_attack"}:
        return False
    if "attack" in action_type or "melee" in action_type or "ranged" in action_type:
        return True
    return bool(_resource_type(action))


def _best_available(actions: list[dict[str, Any]]) -> dict[str, Any] | None:
    best_action: dict[str, Any] | None = None
    best_score: float | None = None
    for action in actions:
        if not _resource_available(action):
            continue
        score = _damage_score(action)
        if best_action is None or score > (best_score or 0):
            best_action = action
            best_score = score
    return best_action


def _resource_available(action: dict[str, Any]) -> bool:
    if action.get("available") is False:
        return False
    resource_type = _resource_type(action)
    if resource_type == "ammunition" and "ammo" in action:
        return _as_int(action.get("ammo"), 0) > 0
    if resource_type == "thrown_weapon" and "quantity" in action:
        return _as_int(action.get("quantity"), 0) > 0
    return True


def _unavailable_resource_payload(action: dict[str, Any]) -> dict[str, Any] | None:
    if _resource_available(action):
        return None
    resource_type = _resource_type(action)
    if not resource_type:
        return None
    return _resource_payload(action, resource_type, consumed=False, unavailable=True)


def _resource_payload(
    action: dict[str, Any],
    resource_type: str,
    *,
    consumed: bool,
    unavailable: bool = False,
    ammo_remaining: int | None = None,
    quantity_remaining: int | None = None,
    weapon_removed: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "weapon": _action_name(action),
        "action_name": _action_name(action),
        "resource_type": resource_type,
        "consumed": consumed,
        "enemy_resource": True,
    }
    if ammo_remaining is not None:
        payload["ammo_remaining"] = ammo_remaining
    elif resource_type == "ammunition" and "ammo" in action:
        payload["ammo_remaining"] = _as_int(action.get("ammo"), 0)
    if quantity_remaining is not None:
        payload["quantity_remaining"] = quantity_remaining
    elif resource_type == "thrown_weapon" and "quantity" in action:
        payload["quantity_remaining"] = _as_int(action.get("quantity"), 0)
    if weapon_removed:
        payload["weapon_removed"] = True
    if unavailable:
        payload["unavailable"] = True
    return payload


def _resource_type(action: dict[str, Any]) -> str | None:
    explicit = _norm(action.get("resource_type") or action.get("weapon_resource_type"))
    if explicit in {"ammunition", "ammo"}:
        return "ammunition"
    if explicit in {"thrown", "thrown_weapon"}:
        return "thrown_weapon"
    if "ammo" in action:
        return "ammunition"
    if _has_property(action, "ammunition") or _has_property(action, "弹药"):
        return "ammunition"
    if "quantity" in action and _has_thrown_property(action):
        return "thrown_weapon"
    return None


def _action_is_ranged(action: dict[str, Any]) -> bool:
    action_type = _norm(action.get("type"))
    if "ranged" in action_type or "remote" in action_type or "yuan_cheng" in action_type or "远程" in action_type:
        return True
    if "melee" in action_type or "近战" in action_type:
        return False
    if _has_property(action, "range") or _has_property(action, "ranged"):
        return True
    if _resource_type(action) == "ammunition":
        return True
    if _has_thrown_property(action):
        return True
    return False


def _action_can_reach_distance(action: dict[str, Any], distance_tiles: int) -> bool:
    if distance_tiles < 0:
        return True
    if _action_is_ranged(action):
        return distance_tiles <= _action_range_tiles(action)
    return distance_tiles <= _action_reach_tiles(action)


def _action_reach_tiles(action: dict[str, Any]) -> int:
    explicit = _first_number(
        action.get("reach"),
        action.get("reach_ft"),
        action.get("reach_feet"),
        action.get("reach_or_range"),
        *_properties(action),
    )
    if explicit is None:
        return 2 if _has_property(action, "reach") else 1
    if explicit <= 3:
        return max(1, explicit)
    return max(1, (explicit + 4) // 5)


def _action_range_tiles(action: dict[str, Any]) -> int:
    numbers = _numbers(
        action.get("range"),
        action.get("range_ft"),
        action.get("range_feet"),
        action.get("reach_or_range"),
        *_properties(action),
    )
    if not numbers:
        return 24
    value = max(numbers)
    if value <= 12:
        return max(1, value)
    return max(1, (value + 4) // 5)


def _damage_score(action: dict[str, Any]) -> float:
    for key in (
        "damage_dice",
        "damage",
        "damage_roll",
        "damage_expression",
        "damage_dice_expression",
    ):
        score = _average_damage_expression(action.get(key))
        if score is not None:
            return score
    hit_die = _first_number(action.get("hit_die"), action.get("damage_die"))
    if hit_die:
        return (hit_die + 1) / 2
    return 0.0


def _average_damage_expression(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    dice_total = 0.0

    def replace_dice(match: re.Match) -> str:
        nonlocal dice_total
        count = int(match.group(1) or "1")
        sides = int(match.group(2))
        dice_total += count * (sides + 1) / 2
        return " "

    remainder = re.sub(r"(?i)(\d*)d(\d+)", replace_dice, text)
    flat_total = sum(int(match) for match in re.findall(r"(?<!d)([+-]?\d+)", remainder))
    if dice_total or flat_total:
        return dice_total + flat_total
    return None


def _first_number(*values: Any) -> int | None:
    numbers = _numbers(*values)
    return numbers[0] if numbers else None


def _numbers(*values: Any) -> list[int]:
    found: list[int] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (int, float)):
            found.append(max(0, int(value)))
            continue
        found.extend(max(0, int(match)) for match in re.findall(r"\d+", str(value)))
    return found


def _has_thrown_property(action: dict[str, Any]) -> bool:
    return any("thrown" in prop or "投掷" in prop for prop in _properties(action))


def _has_property(action: dict[str, Any], needle: str) -> bool:
    return any(needle in prop for prop in _properties(action))


def _properties(action: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for key in ("properties", "traits", "tags"):
        raw = action.get(key)
        if isinstance(raw, list):
            values.extend(raw)
        elif raw:
            values.extend(str(raw).replace(";", ",").split(","))
    return [_norm(value) for value in values if str(value).strip()]


def _action_name(action: dict[str, Any]) -> str:
    return str(action.get("name") or action.get("weapon") or "Attack")


def _multiattack_sequence_actions(
    enemy: dict[str, Any] | None,
    *,
    target_distance_tiles: int | None,
) -> list[dict[str, Any]]:
    actions = _attack_actions(enemy)
    if not actions:
        return []

    names = _explicit_multiattack_names(enemy)
    if not names:
        names = _multiattack_names_from_texts(enemy, actions)
    if not names:
        return []

    sequence: list[dict[str, Any]] = []
    for name in names:
        action = _find_action_by_name(actions, name, target_distance_tiles=target_distance_tiles)
        if action is not None:
            sequence.append(action)
    return sequence


def _explicit_multiattack_names(enemy: dict[str, Any] | None) -> list[str]:
    if not isinstance(enemy, dict):
        return []
    for key in (
        "multiattack_actions",
        "multiattack_sequence",
        "multiattack_action_sequence",
        "multiattack_pattern",
    ):
        names = _names_from_explicit_sequence(enemy.get(key))
        if names:
            return names
    return []


def _names_from_explicit_sequence(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        names: list[str] = []
        for part in re.split(r"\s*(?:,|;|\band\b|\bthen\b|\+)\s*", value):
            names.extend(_names_from_counted_text(part))
        return names
    if isinstance(value, dict):
        name = value.get("name") or value.get("action") or value.get("action_name") or value.get("weapon")
        if name:
            count = max(1, _as_int(value.get("count") or value.get("times") or value.get("uses"), 1))
            return [str(name).strip()] * count
        names: list[str] = []
        for key, count_value in value.items():
            count = max(1, _as_int(count_value, 1))
            names.extend([str(key).strip()] * count)
        return [name for name in names if name]
    if isinstance(value, (list, tuple)):
        names: list[str] = []
        for item in value:
            names.extend(_names_from_explicit_sequence(item))
        return names
    return []


def _names_from_counted_text(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    match = re.match(
        r"(?i)^(?:(\d+|a|an|one|once|two|twice|three|four|five|six|seven|eight|nine|ten)\s+)?(?:with\s+)?(?:its\s+|their\s+|his\s+|her\s+)?(.+?)\s*(?:attack|attacks)?$",
        text,
    )
    if not match:
        return [text]
    raw_count, raw_name = match.groups()
    name = str(raw_name or "").strip()
    if not name:
        return []
    if not raw_count:
        return [name]
    count = int(raw_count) if str(raw_count).isdigit() else _COUNT_WORDS.get(str(raw_count).lower(), 1)
    return [name] * max(1, count)


def _multiattack_names_from_texts(
    enemy: dict[str, Any] | None,
    actions: list[dict[str, Any]],
) -> list[str]:
    for text in _multiattack_texts(enemy):
        names = _multiattack_names_from_text(text, actions)
        if names:
            return names
    return []


def _multiattack_texts(enemy: dict[str, Any] | None) -> list[str]:
    if not isinstance(enemy, dict):
        return []
    texts: list[str] = []
    for key in (
        "multiattack_text",
        "multiattack_desc",
        "multiattack_description",
        "multiattack_note",
        "multiattack_details",
    ):
        value = enemy.get(key)
        if isinstance(value, str) and value.strip():
            texts.append(value.strip())
    if isinstance(enemy.get("multiattack"), str) and enemy["multiattack"].strip():
        texts.append(enemy["multiattack"].strip())

    for action in enemy.get("actions") or []:
        if not isinstance(action, dict):
            continue
        name = _norm(action.get("name") or action.get("action_name"))
        action_type = _norm(action.get("type"))
        if name not in {"multiattack", "multi attack"} and action_type not in {"multiattack", "multi_attack"}:
            continue
        for key in ("description", "desc", "text", "details", "effect"):
            value = action.get(key)
            if isinstance(value, str) and value.strip():
                texts.append(value.strip())
    return texts


_COUNT_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "once": 1,
    "two": 2,
    "twice": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _multiattack_names_from_text(text: str, actions: list[dict[str, Any]]) -> list[str]:
    mentions: list[tuple[int, dict[str, Any], int]] = []
    occupied: set[tuple[int, str]] = set()
    lowered = str(text or "").lower()
    for action in actions:
        for pattern in _action_name_patterns(action):
            for match in re.finditer(pattern, lowered):
                key = (match.start(), _action_name(action).lower())
                if key in occupied:
                    continue
                occupied.add(key)
                mentions.append((
                    match.start(),
                    action,
                    _multiattack_count_before(lowered, match.start()),
                ))
    if not mentions:
        return []

    names: list[str] = []
    for _, action, count in sorted(mentions, key=lambda item: item[0]):
        names.extend([_action_name(action)] * max(1, count))
    return names


def _multiattack_count_before(text: str, start: int) -> int:
    prefix = text[:start]
    split_points = [
        prefix.rfind(delimiter)
        for delimiter in (":", ";", ",", ".", "\n", " and ", " plus ", " then ")
    ]
    last_split = max(split_points)
    segment = prefix[last_split + 1:] if last_split >= 0 else prefix
    matches = re.findall(
        r"\b(\d+|a|an|one|once|two|twice|three|four|five|six|seven|eight|nine|ten)\b",
        segment,
    )
    if not matches:
        return 1
    token = matches[-1]
    if token.isdigit():
        return max(1, int(token))
    return _COUNT_WORDS.get(token, 1)


def _action_name_patterns(action: dict[str, Any]) -> list[str]:
    name = _action_name(action).strip().lower()
    if not name:
        return []
    words = re.findall(r"[a-z0-9]+", name)
    if not words:
        return [re.escape(name)]
    variants = {tuple(words)}
    last = words[-1]
    if last.endswith("s") and len(last) > 1:
        variants.add(tuple([*words[:-1], last[:-1]]))
    else:
        variants.add(tuple([*words[:-1], f"{last}s"]))
    return [
        r"(?<![a-z0-9])" + r"\s+".join(re.escape(word) for word in variant) + r"(?![a-z0-9])"
        for variant in variants
    ]


def _find_action_by_name(
    actions: list[dict[str, Any]],
    name: str,
    *,
    target_distance_tiles: int | None,
) -> dict[str, Any] | None:
    wanted = _name_key(name)
    for action in actions:
        if _name_key(_action_name(action)) != wanted:
            continue
        if target_distance_tiles is not None and not _action_can_reach_distance(action, target_distance_tiles):
            continue
        return action
    return None


def _name_key(value: Any) -> str:
    words = re.findall(r"[a-z0-9]+", str(value or "").lower())
    if not words:
        return _norm(value)
    if words[-1].endswith("s") and len(words[-1]) > 1:
        words[-1] = words[-1][:-1]
    return " ".join(words)


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clone_enemy_action_resource(action: dict[str, Any] | None) -> dict[str, Any]:
    return deepcopy(action or {})
