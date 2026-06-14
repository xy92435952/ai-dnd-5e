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


def validate_feat_prerequisites(
    feats: list[Any] | None,
    *,
    ability_scores: dict | None = None,
    derived: dict | None = None,
    known_spells: list[str] | None = None,
    cantrips: list[str] | None = None,
    spell_slots: dict | None = None,
) -> None:
    """Validate prerequisites for newly selected canonical feat entries."""
    for feat in feats or []:
        name = _canonical_feat_name(_feat_name(feat))
        if name == "War Caster" and not _can_cast_at_least_one_spell(
            derived=derived,
            known_spells=known_spells,
            cantrips=cantrips,
            spell_slots=spell_slots,
        ):
            raise CharacterFeatError(
                400,
                "War Caster requires the ability to cast at least one spell.",
            )
        if name == "Ritual Caster" and not _has_int_or_wis_13(ability_scores):
            raise CharacterFeatError(
                400,
                "Ritual Caster requires Intelligence or Wisdom 13 or higher.",
            )


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


def _can_cast_at_least_one_spell(
    *,
    derived: dict | None,
    known_spells: list[str] | None,
    cantrips: list[str] | None,
    spell_slots: dict | None,
) -> bool:
    if known_spells or cantrips:
        return True

    derived_data = derived or {}
    spell_slots_max = derived_data.get("spell_slots_max") or {}
    for slots in (spell_slots or {}, spell_slots_max):
        for value in slots.values():
            try:
                if int(value or 0) > 0:
                    return True
            except (TypeError, ValueError):
                continue
    return False


def _has_int_or_wis_13(ability_scores: dict | None) -> bool:
    scores = _ability_score_mapping(ability_scores)
    for key in ("int", "wis"):
        try:
            if int(scores.get(key) or 0) >= 13:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _ability_score_mapping(ability_scores: Any) -> dict:
    if not ability_scores:
        return {}
    if isinstance(ability_scores, dict):
        return ability_scores
    model_dump = getattr(ability_scores, "model_dump", None)
    if callable(model_dump):
        try:
            return model_dump(by_alias=True)
        except TypeError:
            return model_dump()
    return {
        "int": getattr(ability_scores, "int", None) or getattr(ability_scores, "int_", None),
        "wis": getattr(ability_scores, "wis", None),
    }


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
