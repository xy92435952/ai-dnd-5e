import json


FALLBACK_DECISION = {
    "action_type": "attack",
    "target_id": None,
    "action_name": None,
    "spell_level": None,
    "move_first": True,
    "reason": "默认攻击（AI决策失败，回退到基础逻辑）",
    "_fallback": True,
}


def strip_json_markdown(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


def parse_ai_decision_response(raw: str) -> dict:
    decision = json.loads(strip_json_markdown(raw))
    decision.setdefault("action_type", "attack")
    decision.setdefault("target_id", None)
    decision.setdefault("action_name", None)
    decision.setdefault("spell_level", None)
    decision.setdefault("move_first", True)
    decision.setdefault("reason", "")
    decision["_fallback"] = False
    return decision


def ensure_valid_ai_decision_targets(
    *,
    decision: dict,
    targets_alive: list[dict],
    all_characters: list[dict],
) -> tuple[dict, bool]:
    """Validate target_id and return (decision, target_was_replaced)."""
    valid_ids = {str(t.get("id")) for t in targets_alive}
    ally_ids = {str(a.get("id")) for a in all_characters if a.get("hp_current", 0) > 0}
    all_valid = valid_ids | ally_ids
    target_replaced = False

    if decision["target_id"] and str(decision["target_id"]) not in all_valid:
        decision["target_id"] = str(targets_alive[0].get("id"))
        target_replaced = True

    if decision["action_type"] in ("attack", "spell", "special") and not decision["target_id"]:
        decision["target_id"] = str(targets_alive[0].get("id"))

    return decision, target_replaced


def fallback_decision(**overrides) -> dict:
    return {**FALLBACK_DECISION, **overrides}
