from dataclasses import dataclass, field
from typing import Any


SLOT_KEYS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th"]

CONTROL_CONDITION_MAP = {
    "Hold Person": "paralyzed",
    "定身术": "paralyzed",
    "Entangle": "restrained",
    "纠缠术": "restrained",
    "Web": "restrained",
    "蛛网": "restrained",
    "Sleep": "unconscious",
    "睡眠术": "unconscious",
    "Command": "commanded",
    "命令术": "commanded",
    "Faerie Fire": "faerie_fire",
    "妖火": "faerie_fire",
    "Blindness/Deafness": "blinded",
    "目盲/耳聋": "blinded",
    "Fear": "frightened",
    "恐惧术": "frightened",
    "Silence": "silenced",
    "沉默术": "silenced",
}


@dataclass
class AiSpellResolution:
    spell_name: str
    spell_level: int
    spell_target: str | None
    spell_data: dict[str, Any]
    is_cantrip: bool
    damage: int = 0
    heal: int = 0
    target_new_hp: int | None = None
    target_state: dict[str, Any] | None = None
    target_name: str = ""
    narration_parts: list[str] = field(default_factory=list)
    mechanical_narration: str = ""


def consume_ai_spell_slot(caster, spell_level: int) -> bool:
    slots = dict(caster.spell_slots or {})
    slot_key = SLOT_KEYS[min(spell_level - 1, 8)]
    if slots.get(slot_key, 0) <= 0:
        return False
    slots[slot_key] -= 1
    caster.spell_slots = slots
    return True


def build_ai_spell_narration(
    *,
    actor_name: str,
    spell_name: str,
    spell_level: int,
    is_cantrip: bool,
    damage: int,
    heal: int,
    narration_parts: list[str],
    decided_reason: str,
) -> str:
    level_str = f"{spell_level}环" if not is_cantrip else "戏法"
    narration = f"✨ {actor_name} 施放了【{spell_name}】（{level_str}）！"
    if damage > 0:
        narration += f"造成 {damage} 点伤害！"
    if heal > 0:
        narration += f"恢复 {heal} HP！"
    if narration_parts:
        narration += " ".join(narration_parts)
    if decided_reason:
        narration += f"（{decided_reason}）"
    return narration


def spell_modifier(actor_derived: dict[str, Any]) -> int:
    spell_ability = actor_derived.get("spell_ability")
    if not spell_ability:
        return 0
    return actor_derived.get("ability_modifiers", {}).get(spell_ability, 0)
