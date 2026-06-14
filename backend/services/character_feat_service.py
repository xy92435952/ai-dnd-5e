from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from services.dnd_data import FEATS


@dataclass
class CharacterFeatError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def normalize_starting_feats(feats: list[Any] | None) -> list[dict]:
    return _normalize_new_feats(feats or [], existing_feats=[])


def normalize_existing_feats(feats: list[Any] | None) -> list[dict]:
    normalized: list[dict] = []
    seen: set[str] = set()
    for feat in feats or []:
        name = _feat_name(feat)
        if not name:
            continue
        canonical_name = _canonical_feat_name(name)
        key = (canonical_name or name).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        if canonical_name:
            normalized.append(canonical_feat_entry(canonical_name))
        else:
            normalized.append(_safe_legacy_feat_entry(feat, name))
    return normalized


def normalize_level_up_feat_choice(
    feat_choice: Any,
    *,
    existing_feats: list[Any] | None = None,
) -> dict:
    normalized = _normalize_new_feats([feat_choice], existing_feats=existing_feats or [])
    return normalized[0]


def canonical_feat_entry(feat: Any) -> dict:
    name = _feat_name(feat)
    canonical_name = _canonical_feat_name(name)
    if not canonical_name:
        raise CharacterFeatError(400, f"Unknown feat: {name}")
    feat_data = deepcopy(FEATS[canonical_name])
    return {"name": canonical_name, **feat_data}


def _normalize_new_feats(feats: list[Any], *, existing_feats: list[Any]) -> list[dict]:
    existing_names = {
        _canonical_feat_name(_feat_name(feat))
        for feat in existing_feats or []
        if _canonical_feat_name(_feat_name(feat))
    }
    normalized: list[dict] = []
    seen = set(existing_names)
    for feat in feats:
        name = _feat_name(feat)
        canonical_name = _canonical_feat_name(name)
        if not canonical_name:
            raise CharacterFeatError(400, f"Unknown feat: {name}")
        if canonical_name in seen:
            raise CharacterFeatError(400, f"Duplicate feat choice: {canonical_name}")
        seen.add(canonical_name)
        normalized.append(canonical_feat_entry(canonical_name))
    return normalized


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


def _safe_legacy_feat_entry(feat: Any, name: str) -> dict:
    if not isinstance(feat, dict):
        return {"name": name}
    safe = {
        key: feat[key]
        for key in ("name", "zh", "desc", "description", "source")
        if key in feat
    }
    safe["name"] = str(safe.get("name") or name).strip()
    return safe
