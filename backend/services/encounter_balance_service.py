"""DnD 5e encounter difficulty estimator.

This is intentionally local and deterministic. It gives the DM agent and future
encounter builders a stable math-backed signal instead of asking an LLM to guess
whether a fight is fair.
"""

from __future__ import annotations

from typing import Any


XP_BY_CR = {
    "0": 10,
    "1/8": 25,
    "1/4": 50,
    "1/2": 100,
    "1": 200,
    "2": 450,
    "3": 700,
    "4": 1100,
    "5": 1800,
    "6": 2300,
    "7": 2900,
    "8": 3900,
    "9": 5000,
    "10": 5900,
    "11": 7200,
    "12": 8400,
    "13": 10000,
    "14": 11500,
    "15": 13000,
    "16": 15000,
    "17": 18000,
    "18": 20000,
    "19": 22000,
    "20": 25000,
    "21": 33000,
    "22": 41000,
    "23": 50000,
    "24": 62000,
    "25": 75000,
    "26": 90000,
    "27": 105000,
    "28": 120000,
    "29": 135000,
    "30": 155000,
}


XP_THRESHOLDS_BY_LEVEL = {
    1: {"easy": 25, "medium": 50, "hard": 75, "deadly": 100},
    2: {"easy": 50, "medium": 100, "hard": 150, "deadly": 200},
    3: {"easy": 75, "medium": 150, "hard": 225, "deadly": 400},
    4: {"easy": 125, "medium": 250, "hard": 375, "deadly": 500},
    5: {"easy": 250, "medium": 500, "hard": 750, "deadly": 1100},
    6: {"easy": 300, "medium": 600, "hard": 900, "deadly": 1400},
    7: {"easy": 350, "medium": 750, "hard": 1100, "deadly": 1700},
    8: {"easy": 450, "medium": 900, "hard": 1400, "deadly": 2100},
    9: {"easy": 550, "medium": 1100, "hard": 1600, "deadly": 2400},
    10: {"easy": 600, "medium": 1200, "hard": 1900, "deadly": 2800},
    11: {"easy": 800, "medium": 1600, "hard": 2400, "deadly": 3600},
    12: {"easy": 1000, "medium": 2000, "hard": 3000, "deadly": 4500},
    13: {"easy": 1100, "medium": 2200, "hard": 3400, "deadly": 5100},
    14: {"easy": 1250, "medium": 2500, "hard": 3800, "deadly": 5700},
    15: {"easy": 1400, "medium": 2800, "hard": 4300, "deadly": 6400},
    16: {"easy": 1600, "medium": 3200, "hard": 4800, "deadly": 7200},
    17: {"easy": 2000, "medium": 3900, "hard": 5900, "deadly": 8800},
    18: {"easy": 2100, "medium": 4200, "hard": 6300, "deadly": 9500},
    19: {"easy": 2400, "medium": 4900, "hard": 7300, "deadly": 10900},
    20: {"easy": 2800, "medium": 5700, "hard": 8500, "deadly": 12700},
}


def estimate_encounter_difficulty(
    party: list[dict[str, Any]] | None,
    monsters: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Estimate encounter difficulty using 5e XP thresholds and count multipliers."""
    party_levels = [_party_member_level(member) for member in party or [] if _party_member_level(member) > 0]
    monster_xps = [_monster_xp(monster) for monster in monsters or [] if _monster_xp(monster) > 0]
    thresholds = _party_thresholds(party_levels)
    base_xp = sum(monster_xps)
    multiplier = _encounter_multiplier(len(monster_xps), len(party_levels))
    adjusted_xp = int(base_xp * multiplier)
    difficulty = _difficulty_for_adjusted_xp(adjusted_xp, thresholds)

    return {
        "difficulty": difficulty,
        "party_size": len(party_levels),
        "average_party_level": _average_level(party_levels),
        "monster_count": len(monster_xps),
        "base_xp": base_xp,
        "adjusted_xp": adjusted_xp,
        "multiplier": multiplier,
        "thresholds": thresholds,
    }


def monster_xp(monster: dict[str, Any] | None) -> int:
    """Public wrapper for monster XP extraction."""
    return _monster_xp(monster or {})


def _party_thresholds(levels: list[int]) -> dict[str, int]:
    totals = {"easy": 0, "medium": 0, "hard": 0, "deadly": 0}
    for level in levels:
        row = XP_THRESHOLDS_BY_LEVEL.get(max(1, min(20, int(level))), XP_THRESHOLDS_BY_LEVEL[1])
        for key in totals:
            totals[key] += row[key]
    return totals


def _difficulty_for_adjusted_xp(adjusted_xp: int, thresholds: dict[str, int]) -> str:
    if adjusted_xp <= 0 or thresholds["easy"] <= 0:
        return "none"
    if adjusted_xp < thresholds["medium"]:
        return "easy"
    if adjusted_xp < thresholds["hard"]:
        return "medium"
    if adjusted_xp < thresholds["deadly"]:
        return "hard"
    return "deadly"


def _encounter_multiplier(monster_count: int, party_size: int) -> float:
    if monster_count <= 0:
        return 0.0
    if monster_count == 1:
        multiplier = 1.0
    elif monster_count == 2:
        multiplier = 1.5
    elif 3 <= monster_count <= 6:
        multiplier = 2.0
    elif 7 <= monster_count <= 10:
        multiplier = 2.5
    elif 11 <= monster_count <= 14:
        multiplier = 3.0
    else:
        multiplier = 4.0

    if party_size and party_size < 3:
        multiplier = _next_multiplier(multiplier)
    elif party_size > 5:
        multiplier = _previous_multiplier(multiplier)
    return multiplier


def _monster_xp(monster: dict[str, Any]) -> int:
    explicit = monster.get("xp")
    if explicit is not None:
        try:
            return max(0, int(float(str(explicit).replace(",", ""))))
        except (TypeError, ValueError):
            pass
    cr = _normalize_cr(monster.get("cr", monster.get("challenge_rating", monster.get("challenge"))))
    return XP_BY_CR.get(cr, 0)


def _party_member_level(member: dict[str, Any]) -> int:
    try:
        return max(1, min(20, int(member.get("level", 1) or 1)))
    except (TypeError, ValueError):
        return 1


def _average_level(levels: list[int]) -> float:
    if not levels:
        return 0.0
    return round(sum(levels) / len(levels), 2)


def _normalize_cr(value: Any) -> str:
    text = str(value if value is not None else "0").strip().lower()
    if text in {"1/8", "1/4", "1/2"}:
        return text
    aliases = {
        "0.125": "1/8",
        ".125": "1/8",
        "0.25": "1/4",
        ".25": "1/4",
        "0.5": "1/2",
        ".5": "1/2",
    }
    if text in aliases:
        return aliases[text]
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer():
        return str(int(number))
    return str(number)


def _next_multiplier(value: float) -> float:
    ladder = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    for candidate in ladder:
        if candidate > value:
            return candidate
    return ladder[-1]


def _previous_multiplier(value: float) -> float:
    ladder = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
    previous = ladder[0]
    for candidate in ladder:
        if candidate >= value:
            return previous
        previous = candidate
    return previous
