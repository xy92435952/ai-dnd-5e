"""战斗规则服务兼容门面。

纯规则实现按职责拆分到 combat_attack_service / combat_damage_service /
combat_condition_service / combat_feature_rules / combat_tactical_service。
这里保留 CombatService 类和 AttackResult 导出，避免端点和测试感知拆分。
"""

from services.combat_attack_service import AttackResult, build_attack_narration, resolve_melee_attack
from services.combat_condition_service import (
    check_concentration,
    get_attack_modifiers,
    get_defense_modifiers,
)
from services.combat_damage_service import (
    apply_damage,
    apply_damage_with_resistance,
    apply_heal,
    check_combat_over,
)
from services.combat_feature_rules import (
    calc_divine_smite_damage,
    calc_sneak_attack_dice,
    check_sneak_attack,
    get_attack_count,
    get_rage_bonus,
    get_rage_uses,
)
from services.combat_tactical_service import (
    choose_ai_target,
    get_cover_bonus,
    resolve_grapple,
    resolve_shove,
)


class CombatService:
    """5e 战斗规则服务。所有方法均为静态/纯函数，可独立测试。"""

    resolve_melee_attack = staticmethod(resolve_melee_attack)
    _build_narration = staticmethod(build_attack_narration)
    apply_damage = staticmethod(apply_damage)
    apply_heal = staticmethod(apply_heal)
    check_combat_over = staticmethod(check_combat_over)
    get_attack_modifiers = staticmethod(get_attack_modifiers)
    get_defense_modifiers = staticmethod(get_defense_modifiers)
    check_concentration = staticmethod(check_concentration)
    get_attack_count = staticmethod(get_attack_count)
    calc_sneak_attack_dice = staticmethod(calc_sneak_attack_dice)
    check_sneak_attack = staticmethod(check_sneak_attack)
    calc_divine_smite_damage = staticmethod(calc_divine_smite_damage)
    get_rage_bonus = staticmethod(get_rage_bonus)
    get_rage_uses = staticmethod(get_rage_uses)
    apply_damage_with_resistance = staticmethod(apply_damage_with_resistance)
    get_cover_bonus = staticmethod(get_cover_bonus)
    resolve_grapple = staticmethod(resolve_grapple)
    resolve_shove = staticmethod(resolve_shove)
    choose_ai_target = staticmethod(choose_ai_target)


__all__ = [
    "AttackResult",
    "CombatService",
]
