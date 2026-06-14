from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm.attributes import flag_modified

from services.dnd_data import FEATS


MAGIC_INITIATE_RESOURCE_KEY = "magic_initiate_spell_uses_remaining"
MAGIC_INITIATE_RESOURCE_SOURCE = "magic_initiate"


@dataclass
class MagicInitiateSpellError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def magic_initiate_spell_resource(
    character: Any,
    *,
    spell_name: str,
    spell: dict[str, Any] | None,
    spell_level: int,
) -> dict[str, Any] | None:
    if not is_magic_initiate_leveled_spell(
        character,
        spell_name=spell_name,
        spell=spell,
        spell_level=spell_level,
    ):
        return None

    return {
        "resource_source": MAGIC_INITIATE_RESOURCE_SOURCE,
        "resource_key": MAGIC_INITIATE_RESOURCE_KEY,
        "uses_remaining": magic_initiate_spell_uses_remaining(character),
    }


def is_magic_initiate_leveled_spell(
    character: Any,
    *,
    spell_name: str,
    spell: dict[str, Any] | None,
    spell_level: int,
) -> bool:
    if _spell_base_level(spell) != 1 or int(spell_level or 0) != 1:
        return False
    chosen_spell = _magic_initiate_chosen_spell(character)
    if not chosen_spell:
        return False
    return _name_matches_any(chosen_spell, _spell_names(spell_name, spell))


def magic_initiate_spell_uses_remaining(character: Any) -> int:
    resources = dict(getattr(character, "class_resources", None) or {})
    return _coerce_non_negative_int(resources.get(MAGIC_INITIATE_RESOURCE_KEY))


def consume_magic_initiate_spell_use(
    character: Any,
    *,
    flag_modified_func: Callable[[Any, str], None] = flag_modified,
) -> dict[str, Any]:
    if not _has_magic_initiate_feat(character):
        raise MagicInitiateSpellError(400, "This character does not have Magic Initiate.")

    resources = dict(getattr(character, "class_resources", None) or {})
    remaining = _coerce_non_negative_int(resources.get(MAGIC_INITIATE_RESOURCE_KEY))
    if remaining <= 0:
        raise MagicInitiateSpellError(400, "No Magic Initiate spell uses remaining.")

    resources[MAGIC_INITIATE_RESOURCE_KEY] = remaining - 1
    character.class_resources = resources
    try:
        flag_modified_func(character, "class_resources")
    except Exception:
        pass
    return resources


def build_magic_initiate_resource_result(character: Any) -> dict[str, Any]:
    return {
        "resource_source": MAGIC_INITIATE_RESOURCE_SOURCE,
        "resource_key": MAGIC_INITIATE_RESOURCE_KEY,
        "uses_remaining": magic_initiate_spell_uses_remaining(character),
    }


def _magic_initiate_chosen_spell(character: Any) -> str:
    for feat in getattr(character, "feats", None) or []:
        if not _is_magic_initiate_feat(feat):
            continue
        if isinstance(feat, dict):
            return str(
                feat.get("spell")
                or feat.get("first_level_spell")
                or feat.get("known_spell")
                or feat.get("learned_spell")
                or feat.get("magic_initiate_spell")
                or ""
            ).strip()
    return ""


def _has_magic_initiate_feat(character: Any) -> bool:
    return any(_is_magic_initiate_feat(feat) for feat in getattr(character, "feats", None) or [])


def _is_magic_initiate_feat(feat: Any) -> bool:
    name = ""
    if isinstance(feat, dict):
        name = str(feat.get("name") or "").strip()
    else:
        name = str(feat or "").strip()
    if not name:
        return False
    target = name.lower()
    if target == "magic initiate":
        return True
    zh = str(FEATS.get("Magic Initiate", {}).get("zh") or "").strip().lower()
    return bool(zh and target == zh)


def _spell_base_level(spell: dict[str, Any] | None) -> int:
    try:
        return int((spell or {}).get("level") or 0)
    except (TypeError, ValueError):
        return 0


def _spell_names(spell_name: str, spell: dict[str, Any] | None) -> list[str]:
    values = [spell_name]
    if isinstance(spell, dict):
        values.extend([spell.get("name"), spell.get("name_en")])
    return [str(value or "").strip() for value in values if str(value or "").strip()]


def _name_matches_any(value: str, candidates: list[str]) -> bool:
    key = _normalize_spell_key(value)
    return bool(key and any(_normalize_spell_key(candidate) == key for candidate in candidates))


def _normalize_spell_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch not in {" ", "_", "-"})


def _coerce_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
