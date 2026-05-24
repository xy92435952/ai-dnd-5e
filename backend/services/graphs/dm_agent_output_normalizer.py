"""Output parsing, schema repair, and fallback helpers for DM agent responses."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from services.campaign_delta import normalize_campaign_delta

logger = logging.getLogger(__name__)

VALID_ABILITIES = {"str", "dex", "con", "int", "wis", "cha"}
ABILITY_ALIASES = {
    "strength": "str",
    "力量": "str",
    "dexterity": "dex",
    "敏捷": "dex",
    "constitution": "con",
    "体质": "con",
    "intelligence": "int",
    "智力": "int",
    "wisdom": "wis",
    "感知": "wis",
    "感知力": "wis",
    "charisma": "cha",
    "魅力": "cha",
}
SAVE_KEYWORDS = ("save", "saving", "豁免", "闪避", "抵抗", "避开", "躲避")
SKILL_TO_ABILITY = {
    "运动": "str",
    "athletics": "str",
    "特技": "dex",
    "隐匿": "dex",
    "巧手": "dex",
    "acrobatics": "dex",
    "stealth": "dex",
    "sleight of hand": "dex",
    "奥秘": "int",
    "调查": "int",
    "历史": "int",
    "自然": "int",
    "宗教": "int",
    "arcana": "int",
    "investigation": "int",
    "history": "int",
    "nature": "int",
    "religion": "int",
    "察觉": "wis",
    "洞察": "wis",
    "生存": "wis",
    "医药": "wis",
    "驯兽": "wis",
    "perception": "wis",
    "insight": "wis",
    "survival": "wis",
    "medicine": "wis",
    "animal handling": "wis",
    "游说": "cha",
    "说服": "cha",
    "威吓": "cha",
    "欺瞒": "cha",
    "表演": "cha",
    "persuasion": "cha",
    "intimidation": "cha",
    "deception": "cha",
    "performance": "cha",
}


def strip_code_block(text: str) -> str:
    """去除 LLM 输出中的 Markdown 代码块包裹（```json ... ```）"""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?\s*```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def _normalize_state_delta(delta: dict) -> dict:
    delta = delta if isinstance(delta, dict) else {}
    for key in ("characters", "enemies", "gold_changes"):
        if not isinstance(delta.get(key, []), list):
            delta[key] = []
    delta.setdefault("characters", [])
    delta.setdefault("enemies", [])
    delta.setdefault("combat_end", False)
    delta.setdefault("combat_end_result", None)
    delta.setdefault("combat_trigger", False)
    delta.setdefault("gold_changes", [])

    for gc in delta.get("gold_changes", []):
        if "amount" in gc:
            try:
                gc["amount"] = int(gc["amount"])
            except (ValueError, TypeError):
                gc["amount"] = 0

    for entity in delta.get("characters", []) + delta.get("enemies", []):
        if "hp_change" in entity:
            try:
                entity["hp_change"] = int(entity["hp_change"])
            except (ValueError, TypeError):
                entity["hp_change"] = 0

    return delta


def _normalize_ai_turns(ai_turns: list) -> list:
    if not isinstance(ai_turns, list):
        return []
    normalized = []
    for turn in ai_turns:
        if not isinstance(turn, dict):
            continue
        turn.setdefault("state_delta", {"characters": [], "enemies": []})
        turn["state_delta"] = _normalize_state_delta(turn["state_delta"])
        for entity in turn["state_delta"].get("characters", []) + turn["state_delta"].get("enemies", []):
            if "hp_change" in entity:
                try:
                    entity["hp_change"] = int(entity["hp_change"])
                except (ValueError, TypeError):
                    entity["hp_change"] = 0
        normalized.append(turn)
    return normalized


def normalize_needs_check(needs_check: Any) -> dict:
    if not isinstance(needs_check, dict):
        needs_check = {"required": False}
    needs_check.setdefault("required", False)
    needs_check.setdefault("check_type", None)
    needs_check.setdefault("ability", None)
    needs_check.setdefault("dc", 10)
    try:
        needs_check["dc"] = int(needs_check.get("dc") or 10)
    except (TypeError, ValueError):
        needs_check["dc"] = 10
    if not needs_check.get("required") and not (needs_check.get("check_type") or needs_check.get("ability")):
        needs_check["check_kind"] = "none"
    else:
        needs_check["check_kind"] = _normalize_check_kind(needs_check)
        needs_check["ability"] = _normalize_check_ability(needs_check)
        if needs_check["check_kind"] == "saving_throw" and not needs_check["ability"]:
            needs_check["ability"] = "dex"
    if needs_check.get("advantage") and needs_check.get("disadvantage"):
        needs_check["advantage"] = False
        needs_check["disadvantage"] = False
    return needs_check


def _normalize_check_kind(needs_check: dict) -> str:
    explicit = str(
        needs_check.get("check_kind")
        or needs_check.get("kind")
        or needs_check.get("type")
        or ""
    ).strip().lower()
    if explicit in {"saving_throw", "save", "saving throw", "豁免"}:
        return "saving_throw"
    if explicit in {"skill_check", "skill", "ability_check", "check", "检定", "技能检定"}:
        return "skill_check"

    check_type = str(needs_check.get("check_type") or "").strip().lower()
    context = str(needs_check.get("context") or "").strip().lower()
    combined = f"{check_type} {context}"
    if any(keyword in combined for keyword in SAVE_KEYWORDS):
        return "saving_throw"
    return "skill_check"


def _normalize_check_ability(needs_check: dict) -> str | None:
    ability = _normalize_ability(needs_check.get("ability"))
    if ability:
        return ability

    check_type = str(needs_check.get("check_type") or "").strip().lower()
    for raw, normalized in ABILITY_ALIASES.items():
        if raw in check_type:
            return normalized
    for ability_key in VALID_ABILITIES:
        if re.search(rf"\b{ability_key}\b", check_type):
            return ability_key

    context = str(needs_check.get("context") or "").strip().lower()
    for raw, normalized in ABILITY_ALIASES.items():
        if raw in context:
            return normalized
    for ability_key in VALID_ABILITIES:
        if re.search(rf"\b{ability_key}\b", context):
            return ability_key

    if needs_check.get("check_kind") == "saving_throw":
        if any(word in f"{check_type} {context}" for word in ("poison", "毒", "窒息", "寒冷", "饥饿")):
            return "con"
        if any(word in f"{check_type} {context}" for word in ("charm", "fear", "恐惧", "魅惑", "幻觉", "意志")):
            return "wis"
        if any(word in f"{check_type} {context}" for word in ("grapple", "shove", "拉扯", "推倒", "束缚")):
            return "str"
        return None
    return SKILL_TO_ABILITY.get(check_type)


def _normalize_ability(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if raw in VALID_ABILITIES:
        return raw
    return ABILITY_ALIASES.get(raw)


def normalize_player_choices(player_choices: Any, needs_check: dict) -> list:
    if needs_check.get("required"):
        return []
    if not isinstance(player_choices, list):
        return []

    normalized = []
    for choice in player_choices:
        if isinstance(choice, str):
            if choice.strip():
                normalized.append(choice)
            continue
        if not isinstance(choice, dict):
            continue
        text = str(choice.get("text") or "").strip()
        if not text:
            continue
        if not isinstance(choice.get("tags", []), list):
            choice["tags"] = []
        normalized.append(choice)
    return normalized


def normalize_dm_output(raw: str, player_action: str) -> tuple[dict, str, list]:
    """
    Parse and normalize raw DM LLM output.

    Returns:
      (result_dict, error_message, new_messages)
    """
    text = strip_code_block(raw)
    try:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            from services.graphs.module_parser_helpers import _try_parse_json
            data = _try_parse_json(text)
        logger.info("[dm_agent_output_normalizer] JSON OK, keys=%s", list(data.keys())[:5])

        data.setdefault("action_type", "unknown")
        data.setdefault("narrative", "")
        data.setdefault("dice_results", [])
        data.setdefault("state_delta", {})
        data.setdefault("companion_reactions", "")
        data.setdefault("ai_turns", [])
        data.setdefault("player_choices", [])
        data.setdefault("campaign_delta", {})

        data["state_delta"] = _normalize_state_delta(data["state_delta"])
        data["ai_turns"] = _normalize_ai_turns(data.get("ai_turns", []))
        data["needs_check"] = normalize_needs_check(data.get("needs_check", {"required": False}))
        data["player_choices"] = normalize_player_choices(data.get("player_choices", []), data["needs_check"])
        data["campaign_delta"] = normalize_campaign_delta(data.get("campaign_delta", {}))

        new_messages = [
            HumanMessage(content=player_action),
            AIMessage(content=data.get("narrative", "")),
        ]
        return data, "", new_messages
    except Exception as e:
        logger.error("[dm_agent_output_normalizer] FALLBACK triggered: %s", e)
        extracted_narrative = ""
        extracted_companion = ""
        if raw:
            m = re.search(r'"narrative"\s*:\s*"(.*?)"\s*[,}\n]', raw, re.DOTALL)
            if m:
                extracted_narrative = m.group(1).replace('\\"', '"').replace('\\n', '\n')
            m2 = re.search(r'"companion_reactions"\s*:\s*"(.*?)"\s*[,}\n]', raw, re.DOTALL)
            if m2:
                extracted_companion = m2.group(1).replace('\\"', '"').replace('\\n', '\n')

        fallback = {
            "action_type": "exploration",
            "narrative": extracted_narrative or "（DM处理出现异常，请重试当前行动）",
            "companion_reactions": extracted_companion,
            "needs_check": {"required": False},
            "state_delta": {},
            "player_choices": [],
            "dice_results": [],
            "ai_turns": [],
            "campaign_delta": normalize_campaign_delta({}),
        }
        new_messages = [
            HumanMessage(content=player_action),
            AIMessage(content=fallback["narrative"]),
        ]
        return fallback, str(e), new_messages
