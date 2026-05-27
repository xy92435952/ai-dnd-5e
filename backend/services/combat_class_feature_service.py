from dataclasses import dataclass
from typing import Any, Callable

from services.combat_action_rules_service import CombatActionRuleError, validate_can_take_action
from services.combat_turn_state_service import save_turn_state
from services.dnd_rules import (
    WILD_SHAPE_FORMS,
    _normalize_class,
    apply_character_healing,
    can_receive_ordinary_healing,
    get_effective_hp_max,
    get_temporary_hp,
    grant_temporary_hp,
)


@dataclass
class CombatClassFeatureError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass
class CombatClassFeatureResult:
    narration: str
    dice_roll: dict[str, Any] | None
    turn_state: dict[str, Any]
    class_resources: dict[str, Any]
    character_class: str
    hp_max: int
    temporary_hp: int = 0


def _fail(detail: str, status_code: int = 400) -> None:
    raise CombatClassFeatureError(status_code, detail)


def resolve_combat_class_feature(
    *,
    feature: str,
    player,
    player_id: str,
    combat,
    turn_state: dict[str, Any],
    combat_service,
    roll_dice_fn: Callable[[str], dict[str, Any]],
) -> CombatClassFeatureResult:
    player_class = _normalize_class(player.char_class)
    player_level = player.level
    derived = player.derived or {}
    class_resources = dict(player.class_resources or {})
    narration = ""
    dice_roll = None
    try:
        validate_can_take_action(player)
    except CombatActionRuleError as exc:
        _fail(exc.detail, exc.status_code)

    if feature == "second_wind":
        if player_class != "Fighter":
            _fail("只有战士可以使用活力恢复")
        if class_resources.get("second_wind_used", False):
            _fail("本次休息后已使用过活力恢复")
        if turn_state["bonus_action_used"]:
            _fail("本回合附赠行动已用尽")

        if not can_receive_ordinary_healing(player):
            _fail("Ordinary healing cannot revive a dead character")

        heal_roll = roll_dice_fn(f"1d10+{player_level}")
        heal_amount = heal_roll["total"]
        hp_max = get_effective_hp_max(player, derived.get("hp_max", player.hp_current))
        old_hp = player.hp_current
        apply_character_healing(player, heal_amount)

        class_resources["second_wind_used"] = True
        player.class_resources = class_resources
        turn_state["bonus_action_used"] = True
        save_turn_state(combat, player_id, turn_state)

        narration = (
            f"🛡️ {player.name} 使用「活力恢复」！1d10+{player_level}={heal_amount}，"
            f"恢复 {player.hp_current - old_hp} HP（{player.hp_current}/{hp_max}）"
        )
        dice_roll = {"faces": 10, "result": heal_amount, "label": f"活力恢复 1d10+{player_level}"}

    elif feature == "action_surge":
        if player_class != "Fighter":
            _fail("只有战士可以使用行动奔涌")
        if player_level < 2:
            _fail("需要战士2级以上才能使用行动奔涌")
        if class_resources.get("action_surge_used", False):
            _fail("本次休息后已使用过行动奔涌")

        class_resources["action_surge_used"] = True
        player.class_resources = class_resources
        turn_state["action_used"] = False
        turn_state["attacks_made"] = 0
        save_turn_state(combat, player_id, turn_state)
        narration = f"⚡ {player.name} 使用「行动奔涌」！本回合获得额外一次完整行动！"

    elif feature == "rage":
        if player_class != "Barbarian":
            _fail("只有野蛮人可以使用狂暴")
        if turn_state["bonus_action_used"]:
            _fail("本回合附赠行动已用尽")

        if class_resources.get("raging", False):
            class_resources["raging"] = False
            player.class_resources = class_resources
            conditions = list(player.conditions or [])
            player.conditions = [condition for condition in conditions if condition != "raging"]
            narration = f"😤 {player.name} 停止了狂暴。"
        else:
            rage_remaining = class_resources.get("rage_remaining", combat_service.get_rage_uses(player_level))
            if rage_remaining <= 0:
                _fail("狂暴次数已用尽（长休后恢复）")
            class_resources["raging"] = True
            class_resources["rage_remaining"] = rage_remaining - 1
            player.class_resources = class_resources
            turn_state["bonus_action_used"] = True
            save_turn_state(combat, player_id, turn_state)
            rage_bonus = combat_service.get_rage_bonus(player_level)
            narration = f"🔥 {player.name} 进入狂暴！近战伤害+{rage_bonus}，物理伤害抗性！（剩余{rage_remaining - 1}次）"

    elif feature == "cunning_action_dash":
        if player_class != "Rogue":
            _fail("只有游荡者可以使用灵巧动作")
        if player_level < 2:
            _fail("需要游荡者2级以上才能使用灵巧动作")
        if turn_state["bonus_action_used"]:
            _fail("本回合附赠行动已用尽")

        turn_state["bonus_action_used"] = True
        turn_state["movement_max"] = (
            turn_state["movement_max"]
            + turn_state.get("base_movement_max", turn_state["movement_max"])
        )
        save_turn_state(combat, player_id, turn_state)
        narration = f"💨 {player.name} 使用「灵巧动作-冲刺」！移动力翻倍！"

    elif feature == "cunning_action_disengage":
        if player_class != "Rogue":
            _fail("只有游荡者可以使用灵巧动作")
        if player_level < 2:
            _fail("需要游荡者2级以上才能使用灵巧动作")
        if turn_state["bonus_action_used"]:
            _fail("本回合附赠行动已用尽")

        turn_state["bonus_action_used"] = True
        turn_state["disengaged"] = True
        save_turn_state(combat, player_id, turn_state)
        narration = f"💨 {player.name} 使用「灵巧动作-脱离」！本回合移动不触发借机攻击。"

    elif feature == "cunning_action_hide":
        if player_class != "Rogue":
            _fail("只有游荡者可以使用灵巧动作")
        if player_level < 2:
            _fail("需要游荡者2级以上才能使用灵巧动作")
        if turn_state["bonus_action_used"]:
            _fail("本回合附赠行动已用尽")

        turn_state["bonus_action_used"] = True
        save_turn_state(combat, player_id, turn_state)
        conditions = list(player.conditions or [])
        if "hidden" not in conditions:
            conditions.append("hidden")
            player.conditions = conditions
        narration = f"🫥 {player.name} 使用「灵巧动作-隐匿」！下次攻击获得优势！"

    elif feature == "fighting_spirit":
        if player_class != "Fighter":
            _fail("非战士无法使用战意")
        remaining = class_resources.get("fighting_spirit_remaining", 0)
        if remaining <= 0:
            _fail("战意次数已用完")
        class_resources["fighting_spirit_remaining"] = remaining - 1
        turn_state["fighting_spirit_active"] = True
        player.class_resources = class_resources
        grant_temporary_hp(
            player,
            player.level,
            source="fighting_spirit",
            replace_if_higher=True,
        )
        class_resources = dict(player.class_resources or {})
        save_turn_state(combat, player_id, turn_state)
        narration = f"⚔️ {player.name} 集中精神，燃起不屈的战意！本回合所有攻击获得优势，获得 {player.level} 点临时生命值。"

    elif feature == "bardic_inspiration":
        if player_class != "Bard":
            _fail("非吟游诗人无法使用灵感骰")
        remaining = class_resources.get("bardic_inspiration_remaining", 0)
        if remaining <= 0:
            _fail("灵感骰次数已用完")
        class_resources["bardic_inspiration_remaining"] = remaining - 1
        die = derived.get("subclass_effects", {}).get("inspiration_die", "d6")
        die_faces = int(die.replace("d", "")) if die.startswith("d") else 6
        inspiration_roll = roll_dice_fn(die)
        player.class_resources = class_resources
        narration = f"🎵 {player.name} 演奏了一段鼓舞人心的旋律！一名盟友获得 {die} 灵感骰（{inspiration_roll['rolls'][0]}）。"
        dice_roll = {"faces": die_faces, "result": inspiration_roll["rolls"][0], "label": f"灵感骰 {die}"}

    elif feature == "ki_flurry":
        if player_class != "Monk":
            _fail("非武僧无法使用疾风连击")
        ki = class_resources.get("ki_remaining", 0)
        if ki < 1:
            _fail("气不足")
        class_resources["ki_remaining"] = ki - 1
        turn_state["bonus_action_used"] = True
        save_turn_state(combat, player_id, turn_state)
        attack_mod = derived.get("attack_bonus", 2)
        results = []
        for index in range(2):
            attack_roll = roll_dice_fn("1d20")
            hit_total = attack_roll["rolls"][0] + attack_mod
            results.append(f"攻击{index + 1}: d20={attack_roll['rolls'][0]}+{attack_mod}={hit_total}")
        player.class_resources = class_resources
        narration = f"👊 {player.name} 以气驱动疾风连击！{' | '.join(results)}"
        dice_roll = {"faces": 20, "result": roll_dice_fn("1d20")["rolls"][0], "label": "疾风连击"}

    elif feature == "ki_stunning_strike":
        if player_class != "Monk":
            _fail("非武僧无法使用震慑打击")
        ki = class_resources.get("ki_remaining", 0)
        if ki < 1:
            _fail("气不足")
        class_resources["ki_remaining"] = ki - 1
        player.class_resources = class_resources
        ki_dc = 8 + derived.get("proficiency_bonus", 2) + derived.get("ability_modifiers", {}).get("wis", 0)
        narration = f"💥 {player.name} 将气灌注于一击之中！目标必须进行 DC{ki_dc} 体质豁免，失败则被震慑至你的下一回合结束。"
        dice_roll = {"faces": 20, "result": ki_dc, "label": f"震慑打击 DC{ki_dc}"}

    elif feature == "shadow_step":
        if player_class != "Monk":
            _fail("非武僧无法使用暗影步")
        ki = class_resources.get("ki_remaining", 0)
        if ki < 2:
            _fail("气不足（需要2点）")
        class_resources["ki_remaining"] = ki - 2
        player.class_resources = class_resources
        narration = f"🌑 {player.name} 融入阴影之中，瞬间出现在另一片黑暗处！下一次近战攻击获得优势。"
        dice_roll = {"faces": 20, "result": roll_dice_fn("1d20")["rolls"][0], "label": "暗影步"}

    elif feature == "channel_divinity":
        if player_class != "Paladin":
            _fail("非圣武士无法引导神力")
        if class_resources.get("channel_divinity_used"):
            _fail("引导神力已使用（每次短休恢复）")
        class_resources["channel_divinity_used"] = True
        subclass_effects = derived.get("subclass_effects", {})
        if subclass_effects.get("devotion"):
            narration = f"✨ {player.name} 引导神力——神圣武器！武器散发圣光，攻击加上魅力修正，持续1分钟。"
        elif subclass_effects.get("vengeance"):
            narration = f"⚔️ {player.name} 引导神力——仇敌誓约！标记一个目标，对其攻击获得优势，持续1分钟。"
            turn_state["vow_of_enmity_active"] = True
            save_turn_state(combat, player_id, turn_state)
        elif subclass_effects.get("ancients"):
            narration = f"🌿 {player.name} 引导神力——自然之怒！藤蔓缠绕目标使其束缚！"
        elif subclass_effects.get("glory"):
            narration = f"🌟 {player.name} 引导神力——鼓舞冲锋！30尺内盟友移动速度+10尺，持续10分钟。"
        else:
            narration = f"✨ {player.name} 引导神力！"
        player.class_resources = class_resources

    elif feature == "lay_on_hands":
        if player_class != "Paladin":
            _fail("非圣武士无法使用圣手")
        pool = class_resources.get("lay_on_hands_remaining", 0)
        if pool <= 0:
            _fail("圣手治疗池已耗尽")
        if not can_receive_ordinary_healing(player):
            _fail("Ordinary healing cannot revive a dead character")
        heal_amount = min(5, pool)
        class_resources["lay_on_hands_remaining"] = pool - heal_amount
        hp_max = get_effective_hp_max(player, derived.get("hp_max", player.hp_current))
        apply_character_healing(player, heal_amount)
        player.class_resources = class_resources
        narration = f"🤲 {player.name} 将圣光注入伤口，恢复了 {heal_amount} 点生命值！（剩余治疗池: {pool - heal_amount}）"
        dice_roll = {"faces": 20, "result": heal_amount, "label": f"圣手治疗 +{heal_amount}HP"}

    elif feature == "war_priest_attack":
        if player_class != "Cleric":
            _fail("非牧师无法使用战争牧师")
        remaining = class_resources.get("war_priest_remaining", 0)
        if remaining <= 0:
            _fail("战争牧师额外攻击次数已用完")
        class_resources["war_priest_remaining"] = remaining - 1
        turn_state["bonus_action_used"] = True
        save_turn_state(combat, player_id, turn_state)
        player.class_resources = class_resources
        narration = f"⚔️ {player.name} 以战神之名发动额外攻击！本回合可用附赠动作进行一次武器攻击。"

    elif feature == "destructive_wrath":
        if player_class != "Cleric":
            _fail("非牧师无法使用毁灭之怒")
        if class_resources.get("channel_divinity_used"):
            _fail("引导神力已使用")
        class_resources["channel_divinity_used"] = True
        turn_state["destructive_wrath_active"] = True
        save_turn_state(combat, player_id, turn_state)
        player.class_resources = class_resources
        narration = f"⚡ {player.name} 引导神力——毁灭之怒！下一次闪电或雷鸣伤害将自动取最大值！"

    elif feature == "wild_shape":
        if player_class != "Druid":
            _fail("非德鲁伊无法使用野性形态")
        remaining = class_resources.get("wild_shape_remaining", 0)
        if remaining <= 0:
            _fail("野性形态次数已用完")
        class_resources["wild_shape_remaining"] = remaining - 1
        max_cr = derived.get("subclass_effects", {}).get("wild_shape_max_cr", 0.25)
        form_name = "Bear" if max_cr >= 1 else "Wolf"
        form = WILD_SHAPE_FORMS.get(form_name, {})
        class_resources["wild_shape_active"] = form_name
        class_resources["wild_shape_hp"] = form.get("hp", 20)
        player.class_resources = class_resources
        narration = f"🐻 {player.name} 的身体扭曲变化，化身为{form_name}！获得 {form.get('hp',20)} 点额外生命值，AC {form.get('ac',12)}。"
        dice_roll = {"faces": 20, "result": form.get("hp", 20), "label": f"野性形态·{form_name}"}

    elif feature == "symbiotic_entity":
        if player_class != "Druid":
            _fail("非德鲁伊无法激活共生实体")
        remaining = class_resources.get("wild_shape_remaining", 0)
        if remaining <= 0:
            _fail("需要消耗一次野性形态")
        class_resources["wild_shape_remaining"] = remaining - 1
        temp_hp = derived.get("subclass_effects", {}).get("symbiotic_temp_hp", 4 * player.level)
        class_resources["symbiotic_entity_active"] = True
        player.class_resources = class_resources
        grant_temporary_hp(
            player,
            temp_hp,
            source="symbiotic_entity",
            replace_if_higher=True,
        )
        class_resources = dict(player.class_resources or {})
        narration = f"🍄 {player.name} 激活共生实体！孢子覆盖全身，获得 {temp_hp} 点临时生命值，近战附加毒素伤害。"
        dice_roll = {"faces": 20, "result": temp_hp, "label": f"共生实体 +{temp_hp}临时HP"}

    elif feature == "tides_of_chaos":
        if player_class != "Sorcerer":
            _fail("非术士无法使用混沌之潮")
        if class_resources.get("tides_of_chaos_used"):
            _fail("混沌之潮已使用（每次长休恢复）")
        class_resources["tides_of_chaos_used"] = True
        turn_state["tides_of_chaos_active"] = True
        save_turn_state(combat, player_id, turn_state)
        player.class_resources = class_resources
        narration = f"🌀 {player.name} 引导体内不稳定的魔法能量！下一次攻击/检定/豁免获得优势。但这可能触发野蛮魔法涌动..."

    elif feature == "portent":
        if player_class != "Wizard":
            _fail("非法师无法使用预言骰")
        remaining = class_resources.get("portent_remaining", 0)
        if remaining <= 0:
            _fail("预言骰已用完（每次长休恢复）")
        class_resources["portent_remaining"] = remaining - 1
        portent_roll = roll_dice_fn("1d20")
        class_resources["portent_value"] = portent_roll["rolls"][0]
        player.class_resources = class_resources
        narration = f"🔮 {player.name} 预见了命运的走向——预言骰: {portent_roll['rolls'][0]}！可以用此值替换任意一次d20检定。"
        dice_roll = {"faces": 20, "result": portent_roll["rolls"][0], "label": "预言骰"}

    else:
        _fail(f"未知职业特性：{feature}")

    return CombatClassFeatureResult(
        narration=narration,
        dice_roll=dice_roll,
        turn_state=turn_state,
        class_resources=class_resources,
        character_class=player_class,
        hp_max=get_effective_hp_max(player, derived.get("hp_max", player.hp_current)),
        temporary_hp=get_temporary_hp(player),
    )
