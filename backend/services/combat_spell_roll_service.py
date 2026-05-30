from dataclasses import dataclass
from typing import Callable

AUTO_HIT_DAMAGE_SPELLS = frozenset({
    "magic missile",
    "榄旀硶椋炲脊",
    "魔法飞弹",
})


@dataclass
class CombatSpellRollError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def spell_action_cost(spell: dict | None) -> str:
    casting_time = str((spell or {}).get("casting_time") or "action").lower()
    if "bonus" in casting_time:
        return "bonus"
    if "reaction" in casting_time:
        return "reaction"
    return "action"


def validate_spell_turn_state(
    turn_state: dict,
    *,
    is_cantrip: bool = False,
    action_cost: str = "action",
) -> dict:
    del is_cantrip  # Cantrips still consume their normal casting action.
    if action_cost == "reaction":
        raise CombatSpellRollError(400, "反应法术必须由反应触发")
    if action_cost == "bonus":
        if turn_state.get("bonus_action_used"):
            raise CombatSpellRollError(400, "本回合附赠动作已用尽")
        return turn_state
    if turn_state.get("action_used"):
        raise CombatSpellRollError(400, "本回合行动已用尽")
    return turn_state


def build_spell_ability_context(derived: dict | None) -> dict:
    derived_data = derived or {}
    spell_ability = derived_data.get("spell_ability")
    spell_mod = (
        derived_data.get("ability_modifiers", {}).get(spell_ability or "", 0)
        if spell_ability
        else 0
    )
    context = {
        "spell_mod": spell_mod,
        "spell_save_dc": derived_data.get("spell_save_dc", 13),
    }
    if "spell_attack_bonus" in derived_data or spell_ability:
        context["spell_attack_bonus"] = derived_data.get(
            "spell_attack_bonus",
            derived_data.get("proficiency_bonus", 0) + spell_mod,
        )
    return context


def _spell_names(spell_name: str, spell: dict | None) -> set[str]:
    names = {str(spell_name or "").strip().lower()}
    for key in ("name", "name_en"):
        value = (spell or {}).get(key)
        if value:
            names.add(str(value).strip().lower())
    return names


def spell_requires_attack_roll(spell_name: str, spell: dict | None) -> bool:
    """Return True for damage spells resolved with a spell attack roll."""
    spell = spell or {}
    if spell.get("type") != "damage":
        return False
    if spell.get("save"):
        return False
    return not bool(_spell_names(spell_name, spell) & AUTO_HIT_DAMAGE_SPELLS)


def spell_attack_is_ranged(spell: dict | None) -> bool:
    """Treat explicit melee spell attacks as close attacks; everything else is ranged."""
    spell = spell or {}
    text = " ".join(str(spell.get(key) or "") for key in ("name", "name_en", "desc")).lower()
    if "melee spell attack" in text or "近战法术攻击" in text or "杩戞垬娉曟湳鏀诲嚮" in text:
        return False
    try:
        return int(spell.get("range", 0) or 0) > 1
    except (TypeError, ValueError):
        return True


def build_spell_roll_preview(
    *,
    spell_name: str,
    spell_level: int,
    spell: dict,
    calc_upcast_dice: Callable[[str, int], str | None],
) -> dict:
    damage_dice = ""
    heal_dice = ""
    if spell["type"] == "damage":
        base_dice = spell.get("damage_dice", spell.get("damage", "1d6"))
        upcast_dice = calc_upcast_dice(spell_name, spell_level)
        damage_dice = upcast_dice if upcast_dice else base_dice
    elif spell["type"] == "heal":
        base_dice = spell.get("heal_dice", spell.get("heal", "1d8"))
        upcast_dice = calc_upcast_dice(spell_name, spell_level)
        heal_dice = upcast_dice if upcast_dice else base_dice

    return {
        "damage_dice": damage_dice,
        "heal_dice": heal_dice,
        "save_type": spell.get("save", None),
        "is_aoe": spell.get("aoe", False),
        "is_concentration": spell.get("concentration", False),
    }
