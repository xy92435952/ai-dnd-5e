"""Helpers for consuming stored module parser output.

Some older/local seed paths stored ``Module.parsed_content`` as a JSON string
inside the JSON column. Newer code expects a dict, so normalize at read
boundaries instead of letting ``.get`` crash request handlers.
"""

from __future__ import annotations

import json
from typing import Any


def normalize_module_content(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def get_module_content(module: Any | None) -> dict[str, Any]:
    if module is None:
        return {}
    return normalize_module_content(getattr(module, "parsed_content", None))
