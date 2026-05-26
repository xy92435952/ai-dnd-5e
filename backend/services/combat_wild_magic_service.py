from dataclasses import dataclass
from typing import Any, Callable

from services.dnd_rules import get_effective_hp_max


@dataclass
class WildMagicResolution:
    surge: dict[str, Any] | None = None
    check: dict[str, Any] | None = None
    narration_append: str | None = None
    log_content: str | None = None
    log_dice_result: dict[str, Any] | None = None
    updated_class_resources: dict[str, Any] | None = None


def resolve_wild_magic_for_spell(
    *,
    caster_name: str,
    is_cantrip: bool,
    derived: dict[str, Any] | None,
    class_resources: dict[str, Any] | None,
    roll_dice: Callable[[str], dict[str, Any]],
    roll_wild_magic_surge: Callable[[], dict[str, Any]],
) -> WildMagicResolution:
    if is_cantrip:
        return WildMagicResolution()

    subclass_effects = (derived or {}).get("subclass_effects", {})
    if not subclass_effects.get("wild_magic"):
        return WildMagicResolution()

    resources = dict(class_resources or {})
    if resources.get("tides_of_chaos_used", False):
        surge = roll_wild_magic_surge()
        resources["tides_of_chaos_used"] = False
        narration = f"🌀 混沌反噬！混沌之潮的代价降临——{surge['effect']}"
        return WildMagicResolution(
            surge=surge,
            check={
                "d20": "自动",
                "triggered": True,
                "forced": True,
                "surge_roll": surge.get("index", 0) + 1,
            },
            narration_append=narration,
            log_content=narration,
            updated_class_resources=resources,
        )

    surge_check = roll_dice("1d20")
    d20_val = surge_check["rolls"][0]
    if d20_val != 1:
        return WildMagicResolution(
            check={"d20": d20_val, "triggered": False, "forced": False},
            log_content=f"🎲 野蛮魔法检测: d20={d20_val}（未触发涌动，需要1）",
        )

    surge = roll_wild_magic_surge()
    narration = f"🌀 野蛮魔法涌动！d20={d20_val}——{caster_name} 体内的混沌能量失控！{surge['effect']}"
    return WildMagicResolution(
        surge=surge,
        check={
            "d20": d20_val,
            "triggered": True,
            "forced": False,
            "surge_roll": surge.get("index", 0) + 1,
        },
        narration_append=narration,
        log_content=narration,
        log_dice_result={"type": "wild_magic_surge", "d20": d20_val, **surge},
    )


def apply_wild_magic_mechanical_effect(
    *,
    caster,
    surge: dict[str, Any] | None,
    roll_dice: Callable[[str], dict[str, Any]],
) -> None:
    if not surge:
        return

    mechanical = surge.get("mechanical", {})
    if mechanical.get("type") == "heal":
        heal_roll = roll_dice(mechanical["dice"])
        caster.hp_current = min(
            get_effective_hp_max(caster),
            caster.hp_current + heal_roll["total"],
        )
    elif mechanical.get("type") == "condition":
        conditions = list(caster.conditions or [])
        conditions.append(mechanical["condition"])
        caster.conditions = conditions
