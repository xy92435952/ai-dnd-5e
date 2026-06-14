"""Helpers for reading canonical feat effects from derived stats."""

from typing import Any


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
