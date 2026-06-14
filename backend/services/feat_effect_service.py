"""Helpers for reading canonical feat effects from derived stats."""

from typing import Any

from services.dnd_data import FEATS


def has_feat_effect(
    derived: dict[str, Any] | None,
    feat_name: str,
    effect_key: str,
) -> bool:
    """Return whether a derived feat entry grants a specific official effect.

    Canonical derived stats store feat effects as dictionaries keyed by feat
    name. Older snapshots may store a bare truthy value for known feats, so keep
    that compatibility path until all persisted characters have been refreshed.
    """
    feat_effect = ((derived or {}).get("feat_effects") or {}).get(feat_name)
    if isinstance(feat_effect, dict):
        return bool(feat_effect.get(effect_key))
    return bool(feat_effect)


def get_feat_list_effect_value(
    feats: list[Any] | None,
    feat_name: str,
    effect_key: str,
    default: Any = None,
) -> Any:
    """Read a trusted effect value for a feat present in a raw feat list."""
    target = _canonical_feat_name(feat_name)
    if not target:
        return default
    for feat in feats or []:
        if _canonical_feat_name(_feat_name(feat)) == target:
            effects = FEATS.get(target, {}).get("effects") or {}
            return effects.get(effect_key, default)
    return default


def _feat_name(feat: Any) -> str:
    if isinstance(feat, dict):
        return str(feat.get("name") or "").strip()
    return str(feat or "").strip()


def _canonical_feat_name(name: str) -> str | None:
    target = str(name or "").strip().lower()
    if not target:
        return None
    for feat_name, data in FEATS.items():
        if feat_name.lower() == target:
            return feat_name
        zh = str(data.get("zh") or "").strip().lower()
        if zh and zh == target:
            return feat_name
    return None
