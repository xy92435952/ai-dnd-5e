from services.dnd_rules import roll_dice


def get_attack_count(char_derived: dict, level: int, char_class: str) -> int:
    cls = char_class
    if cls in ("Fighter",) and level >= 20:
        return 4
    if cls in ("Fighter",) and level >= 11:
        return 3
    if cls in ("Fighter", "Paladin", "Ranger", "Barbarian", "Monk") and level >= 5:
        return 2
    return 1


def calc_sneak_attack_dice(level: int) -> int:
    return (level + 1) // 2


def check_sneak_attack(
    attacker_class: str,
    has_advantage: bool,
    ally_adjacent_to_target: bool,
    swashbuckler: bool = False,
    no_other_enemy_adjacent: bool = False,
) -> bool:
    if attacker_class not in ("Rogue", "游荡者"):
        return False
    if has_advantage or ally_adjacent_to_target:
        return True
    if swashbuckler and no_other_enemy_adjacent:
        return True
    return False


def calc_divine_smite_damage(
    slot_level: int,
    target_is_undead: bool = False,
    is_crit: bool = False,
) -> dict:
    dice_count = 1 + slot_level
    if target_is_undead:
        dice_count += 1
    dice_count = min(dice_count, 6)
    base_dice_count = dice_count
    if is_crit:
        dice_count *= 2
    result = roll_dice(f"{dice_count}d8")
    return {
        "damage": result["total"],
        "dice": f"{dice_count}d8",
        "roll": result,
        "base_dice": f"{base_dice_count}d8",
        "is_crit": is_crit,
    }


def get_rage_bonus(level: int) -> int:
    if level >= 16:
        return 4
    if level >= 9:
        return 3
    return 2


def get_rage_uses(level: int) -> int:
    if level >= 20:
        return 999
    if level >= 17:
        return 6
    if level >= 12:
        return 5
    if level >= 6:
        return 4
    if level >= 3:
        return 3
    return 2
