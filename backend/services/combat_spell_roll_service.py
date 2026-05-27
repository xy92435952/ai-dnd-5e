from dataclasses import dataclass
from typing import Callable


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
    return {
        "spell_mod": spell_mod,
        "spell_save_dc": derived_data.get("spell_save_dc", 13),
    }


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
