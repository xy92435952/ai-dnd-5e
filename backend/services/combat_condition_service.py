from typing import Optional

from services.dnd_rules import has_exhaustion_effect


def get_attack_modifiers(conditions: list[str], character: dict | object | None = None) -> tuple[bool, bool]:
    adv_conditions = {"invisible", "hidden"}
    dis_conditions = {"poisoned", "frightened", "prone", "blinded", "restrained"}
    adv = any(c in adv_conditions for c in conditions)
    dis = any(c in dis_conditions for c in conditions) or has_exhaustion_effect(
        character,
        "attack_save_disadvantage",
    )
    return adv, dis


def get_defense_modifiers(conditions: list[str]) -> tuple[bool, bool]:
    adv_to_attacker = {
        "paralyzed",
        "petrified",
        "stunned",
        "unconscious",
        "prone",
        "blinded",
        "restrained",
        "faerie_fire",
    }
    dis_to_attacker = {"invisible", "dodging"}
    adv = any(c in adv_to_attacker for c in conditions)
    dis = any(c in dis_to_attacker for c in conditions)
    return adv, dis


def check_concentration(character_dict: dict, damage: int) -> Optional[dict]:
    if not character_dict.get("concentration") or damage <= 0:
        return None

    from services.dnd_rules import roll_saving_throw
    dc = max(10, damage // 2)

    derived = character_dict.get("derived", {})
    feat_effects = derived.get("feat_effects", {})
    has_war_caster = bool(feat_effects.get("War Caster")) or derived.get("subclass_effects", {}).get("concentration_advantage", False)
    roll_result = roll_saving_throw(character_dict, "con", dc, advantage=has_war_caster)

    return {
        "required": True,
        "dc": dc,
        "spell_name": character_dict["concentration"],
        "broke": not roll_result["success"],
        "roll_result": roll_result,
        "war_caster": has_war_caster,
    }
