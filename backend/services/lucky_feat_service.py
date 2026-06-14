from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from services.dnd_data import FEATS


LUCKY_RESOURCE_KEY = "lucky_points_remaining"


@dataclass
class LuckyFeatError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def spend_lucky_point(
    character: Any,
    *,
    d20_before: int | None,
    lucky_d20_value: int | None,
    context: str,
) -> dict[str, Any]:
    """Spend one trusted Lucky point and return public reroll metadata."""
    if lucky_d20_value is None:
        raise LuckyFeatError(400, "Lucky reroll requires lucky_d20_value.")

    d20_before = _normalize_d20(d20_before, field_name="d20_before")
    d20_after = _normalize_d20(lucky_d20_value, field_name="lucky_d20_value")

    if not has_lucky_access(character):
        raise LuckyFeatError(400, "This character does not have the Lucky feat.")

    class_resources = dict(getattr(character, "class_resources", None) or {})
    remaining = _coerce_non_negative_int(class_resources.get(LUCKY_RESOURCE_KEY))
    if remaining <= 0:
        raise LuckyFeatError(400, "No Lucky points remaining.")

    class_resources[LUCKY_RESOURCE_KEY] = remaining - 1
    character.class_resources = class_resources
    _flag_class_resources_modified(character)

    return {
        "type": "lucky",
        "spent": True,
        "context": context,
        "d20_before": d20_before,
        "d20_after": d20_after,
        "lucky_points_remaining": remaining - 1,
    }


def apply_lucky_to_skill_check(
    result: dict[str, Any],
    *,
    lucky: dict[str, Any],
    dc: int,
) -> dict[str, Any]:
    d20 = int(lucky["d20_after"])
    modifier = int(result.get("modifier") or 0)
    condition_modifier = int(result.get("condition_modifier") or 0)
    total = d20 + modifier + condition_modifier
    return {
        **result,
        "d20": d20,
        "total": total,
        "success": total >= dc,
        "lucky": lucky,
    }


def apply_lucky_to_attack_roll(
    attack_roll: dict[str, Any],
    *,
    lucky: dict[str, Any],
    crit_threshold: int,
) -> dict[str, Any]:
    d20 = int(lucky["d20_after"])
    attack_bonus = int(attack_roll.get("attack_bonus") or 0)
    condition_modifier = int(attack_roll.get("condition_modifier") or 0)
    attack_total = d20 + attack_bonus + condition_modifier
    target_ac = int(attack_roll.get("target_ac") or 0)
    is_crit = d20 >= crit_threshold
    is_fumble = d20 == 1
    hit = (not is_fumble) and (is_crit or attack_total >= target_ac)

    prior_rolls = list(attack_roll.get("d20_rolls") or [lucky["d20_before"]])
    if d20 not in prior_rolls:
        prior_rolls.append(d20)

    return {
        **attack_roll,
        "d20": d20,
        "attack_total": attack_total,
        "hit": hit,
        "is_crit": is_crit,
        "is_fumble": is_fumble,
        "d20_rolls": prior_rolls,
        "selected_d20": d20,
        "other_roll": lucky["d20_before"],
        "d20_selection": "lucky",
        "lucky": lucky,
    }


def has_lucky_access(character: Any) -> bool:
    class_resources = getattr(character, "class_resources", None) or {}
    if LUCKY_RESOURCE_KEY in class_resources:
        return True

    derived = getattr(character, "derived", None) or {}
    feat_effects = derived.get("feat_effects") or {}
    lucky_effect = feat_effects.get("Lucky") or feat_effects.get("lucky")
    if isinstance(lucky_effect, dict) and _coerce_non_negative_int(lucky_effect.get("lucky_points")) > 0:
        return True

    return any(_is_lucky_feat(feat) for feat in getattr(character, "feats", None) or [])


def _normalize_d20(value: int | None, *, field_name: str) -> int:
    try:
        d20 = int(value)
    except (TypeError, ValueError) as exc:
        raise LuckyFeatError(400, f"{field_name} must be an integer d20 value.") from exc
    if d20 < 1 or d20 > 20:
        raise LuckyFeatError(400, f"{field_name} must be between 1 and 20.")
    return d20


def _coerce_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _is_lucky_feat(feat: Any) -> bool:
    name = ""
    if isinstance(feat, dict):
        name = str(feat.get("name") or "").strip()
    else:
        name = str(feat or "").strip()
    if not name:
        return False
    if name.lower() == "lucky":
        return True
    lucky_zh = str(FEATS.get("Lucky", {}).get("zh") or "").strip().lower()
    return bool(lucky_zh and name.lower() == lucky_zh)


def _flag_class_resources_modified(character: Any) -> None:
    try:
        flag_modified(character, "class_resources")
    except Exception:
        pass
