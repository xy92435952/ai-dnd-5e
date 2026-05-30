from dataclasses import dataclass
from typing import Callable
import re


@dataclass
class CombatSpellResolutionError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def consume_spell_slot_for_confirmation(
    *,
    current_slots: dict | None,
    spell_level: int,
    is_cantrip: bool,
    consume_slot: Callable[[dict, int], tuple[dict, str | None]],
) -> dict:
    if is_cantrip:
        return current_slots or {}

    new_slots, slot_err = consume_slot(dict(current_slots or {}), spell_level)
    if slot_err:
        raise CombatSpellResolutionError(400, slot_err)
    return new_slots


def build_spell_resolution_context(derived: dict | None) -> dict:
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
        "bonus_healing": derived_data.get("bonus_healing", False),
    }


def apply_frontend_dice_override(
    *,
    value: int,
    dice_detail: dict,
    damage_values: list[int] | None,
    modifier: int,
) -> tuple[int, dict]:
    if not damage_values:
        return value, dice_detail

    updated = dict(dice_detail or {})
    total = sum(damage_values) + modifier
    updated["total"] = total
    if "base_roll" in updated:
        updated["base_roll"] = {
            **updated["base_roll"],
            "rolls": damage_values,
            "total": sum(damage_values),
        }
    return total, updated


def _flat_damage_bonus_from_roll(roll: dict | None) -> int:
    if not isinstance(roll, dict):
        return 0
    if isinstance(roll.get("bonus"), int):
        return roll["bonus"]
    total = 0
    for part in roll.get("parts") or []:
        if isinstance(part, dict) and not part.get("rolls"):
            total += int(part.get("total", 0) or 0)
    return total


def spell_damage_frontend_override_bonus(dice_detail: dict | None) -> int:
    """Return flat damage already present in the spell dice expression."""
    if not isinstance(dice_detail, dict):
        return 0
    total = _flat_damage_bonus_from_roll(dice_detail.get("base_roll"))
    for extra_roll in dice_detail.get("extra_rolls") or []:
        total += _flat_damage_bonus_from_roll(extra_roll)
    return total


def _critical_dice_notation(notation: str | None) -> str | None:
    if not notation:
        return notation

    parts = []
    for match in re.finditer(r"([+-]?)(\d*)d(\d+)", str(notation).replace(" ", "")):
        if match.group(1) == "-":
            continue
        count = int(match.group(2) or "1")
        parts.append(f"{count}d{match.group(3)}")
    return "+".join(parts) if parts else None


def apply_spell_critical_damage(
    amount: int,
    dice_detail: dict,
    *,
    is_crit: bool = False,
    roll_dice: Callable[[str], dict] | None = None,
) -> tuple[int, dict]:
    if not is_crit:
        return amount, dice_detail
    roller = roll_dice
    if roller is None:
        from services.dnd_rules import roll_dice as roller

    updated = dict(dice_detail or {})
    crit_rolls: list[dict] = []
    crit_extra = 0

    base_roll = updated.get("base_roll")
    if isinstance(base_roll, dict):
        notation = _critical_dice_notation(base_roll.get("notation"))
        if notation:
            crit_roll = roller(notation)
            crit_rolls.append(crit_roll)
            crit_extra += int(crit_roll.get("total", 0) or 0)

    for extra_roll in updated.get("extra_rolls") or []:
        if not isinstance(extra_roll, dict):
            continue
        notation = _critical_dice_notation(extra_roll.get("notation"))
        if notation:
            crit_roll = roller(notation)
            crit_rolls.append(crit_roll)
            crit_extra += int(crit_roll.get("total", 0) or 0)

    if crit_extra <= 0:
        return amount, updated

    updated["crit_extra"] = crit_extra
    updated["crit_rolls"] = crit_rolls
    updated["is_crit"] = True
    updated["total"] = amount + crit_extra
    return amount + crit_extra, updated


def resolve_spell_roll_amount(
    *,
    spell_type: str,
    spell_name: str,
    spell_level: int,
    spell_mod: int,
    bonus_healing: bool,
    damage_values: list[int] | None,
    is_crit: bool = False,
    roll_dice: Callable[[str], dict] | None = None,
    resolve_damage: Callable[[str, int, int], tuple[int, dict]],
    resolve_heal: Callable[[str, int, int, bool], tuple[int, dict]],
) -> tuple[int, dict]:
    if spell_type == "damage":
        amount, dice_detail = resolve_damage(spell_name, spell_level, spell_mod)
    elif spell_type == "heal":
        amount, dice_detail = resolve_heal(spell_name, spell_level, spell_mod, bonus_healing)
    else:
        return 0, {}

    override_modifier = (
        spell_damage_frontend_override_bonus(dice_detail)
        if spell_type == "damage"
        else spell_mod
    )
    amount, dice_detail = apply_frontend_dice_override(
        value=amount,
        dice_detail=dice_detail,
        damage_values=damage_values,
        modifier=override_modifier,
    )
    if spell_type == "damage":
        amount, dice_detail = apply_spell_critical_damage(
            amount,
            dice_detail,
            is_crit=is_crit,
            roll_dice=roll_dice,
        )
    return amount, dice_detail


def build_spell_mechanical_narration(
    *,
    caster_name: str,
    spell_name: str,
    spell_level: int,
    is_cantrip: bool,
    is_aoe: bool,
    aoe_results: list[dict],
    result_damage: int,
    result_heal: int,
    spell_type: str,
    save_detail: dict | None,
    condition_name: str | None,
    resurrection_results: list[dict] | None = None,
) -> str:
    level_str = f"（{spell_level}环）" if not is_cantrip else "（戏法）"
    resurrection_results = resurrection_results or []
    if resurrection_results:
        revived = [result for result in resurrection_results if result.get("resurrected")]
        blocked = [result for result in resurrection_results if not result.get("resurrected")]
        if revived:
            targets_summary = "、".join(result.get("target_name", "?") for result in revived[:4])
            return (
                f"✨ {caster_name} 施放了「{spell_name}」{level_str}，"
                f"{targets_summary}{'等' if len(revived) > 4 else ''}复活并恢复生命。"
            )
        targets_summary = "、".join(result.get("target_name", "?") for result in blocked[:4])
        return (
            f"✨ {caster_name} 施放了「{spell_name}」{level_str}，"
            f"但 {targets_summary or '目标'} 不符合复活条件。"
        )

    if is_aoe and aoe_results:
        targets_summary = "、".join(result.get("target_name", "?") for result in aoe_results[:4])
        narration = (
            f"✨ {caster_name} 施放了【{spell_name}】{level_str}，"
            f"命中 {targets_summary}{'等' if len(aoe_results) > 4 else ''}！"
            + (f"（单目标最高 {result_damage} 点伤害）" if result_damage else "")
            + (f"（每人恢复 {result_heal} HP）" if result_heal else "")
        )
    else:
        narration = (
            f"✨ {caster_name} 施放了【{spell_name}】{level_str}"
            + (f"，造成 {result_damage} 点伤害！" if result_damage else "")
            + (f"，恢复 {result_heal} HP！" if result_heal else "")
        )

    if spell_type in ("control", "utility") and save_detail:
        saved_str = "通过" if save_detail["success"] else "未通过"
        narration += (
            f"\n{save_detail['ability'].upper()} 豁免 DC{save_detail['dc']}: "
            f"d20={save_detail['d20']}+{save_detail['modifier']}={save_detail['total']} — {saved_str}！"
        )
        if not save_detail["success"]:
            narration += f"\n目标陷入【{condition_name}】状态！"

    return narration


def choose_spell_narration_target(*, is_aoe: bool, aoe_results: list[dict], target_ids: list[str]) -> str:
    if is_aoe and aoe_results:
        return "、".join(result.get("target_name", "?") for result in aoe_results[:4])
    return target_ids[0] if target_ids else ""
