from dataclasses import dataclass
from typing import Any, Callable

from services.combat_action_rules_service import CombatActionRuleError, validate_can_take_action
from services.combat_turn_state_service import (
    record_mobile_dash_difficult_terrain_ignore,
    save_turn_state,
)
from services.dnd_rules import (
    WILD_SHAPE_FORMS,
    _normalize_class,
    apply_character_healing,
    can_receive_ordinary_healing,
    get_effective_hp_max,
    get_temporary_hp,
    grant_temporary_hp,
    normalize_condition,
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
    target: Any | None = None


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
    target=None,
    target_id: str | None = None,
) -> CombatClassFeatureResult:
    player_class = _normalize_class(player.char_class)
    player_level = player.level
    derived = player.derived or {}
    class_resources = dict(player.class_resources or {})
    narration = ""
    dice_roll = None
    target_character = player

    try:
        validate_can_take_action(player)
    except CombatActionRuleError as exc:
        _fail(exc.detail, exc.status_code)

    if feature == "second_wind":
        if player_class != "Fighter":
            _fail("只有战士可以使用活力恢复")
        if class_resources.get("second_wind_used", False):
            _fail("Second Wind has already been used since the last rest.")
        _require_bonus_action(turn_state)
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
            f"{player.name} uses Second Wind: 1d10+{player_level}={heal_amount}, "
            f"healing {player.hp_current - old_hp} HP ({player.hp_current}/{hp_max})."
        )
        dice_roll = {"faces": 10, "result": heal_amount, "label": f"Second Wind 1d10+{player_level}"}

    elif feature == "action_surge":
        if player_class != "Fighter":
            _fail("只有战士可以使用行动奔涌")
        if player_level < 2:
            _fail("Action Surge requires Fighter level 2 or higher.")
        if class_resources.get("action_surge_used", False):
            _fail("Action Surge has already been used since the last rest.")

        class_resources["action_surge_used"] = True
        player.class_resources = class_resources
        turn_state["action_used"] = False
        turn_state["attacks_made"] = 0
        save_turn_state(combat, player_id, turn_state)
        narration = f"{player.name} uses Action Surge and gains one additional action this turn."

    elif feature == "rage":
        if player_class != "Barbarian":
            _fail("Only barbarians can rage.")
        _require_bonus_action(turn_state)

        if class_resources.get("raging", False):
            class_resources["raging"] = False
            player.class_resources = class_resources
            conditions = list(player.conditions or [])
            player.conditions = [condition for condition in conditions if condition != "raging"]
            narration = f"{player.name} ends Rage."
        else:
            rage_remaining = class_resources.get("rage_remaining", combat_service.get_rage_uses(player_level))
            if rage_remaining <= 0:
                _fail("No Rage uses remaining.")
            class_resources["raging"] = True
            class_resources["rage_remaining"] = rage_remaining - 1
            player.class_resources = class_resources
            turn_state["bonus_action_used"] = True
            save_turn_state(combat, player_id, turn_state)
            rage_bonus = combat_service.get_rage_bonus(player_level)
            narration = (
                f"{player.name} enters Rage: melee damage +{rage_bonus}, "
                f"physical damage resistance. Remaining uses: {rage_remaining - 1}."
            )

    elif feature == "cunning_action_dash":
        _require_class_level(player_class, player_level, "Rogue", 2, "Cunning Action")
        _require_bonus_action(turn_state)
        turn_state["bonus_action_used"] = True
        turn_state["movement_max"] = (
            turn_state["movement_max"]
            + turn_state.get("base_movement_max", turn_state["movement_max"])
        )
        turn_state = record_mobile_dash_difficult_terrain_ignore(turn_state, actor_derived=derived)
        save_turn_state(combat, player_id, turn_state)
        narration = f"{player.name} uses Cunning Action: Dash."

    elif feature == "cunning_action_disengage":
        _require_class_level(player_class, player_level, "Rogue", 2, "Cunning Action")
        _require_bonus_action(turn_state)
        turn_state["bonus_action_used"] = True
        turn_state["disengaged"] = True
        save_turn_state(combat, player_id, turn_state)
        narration = f"{player.name} uses Cunning Action: Disengage."

    elif feature == "cunning_action_hide":
        _require_class_level(player_class, player_level, "Rogue", 2, "Cunning Action")
        _require_bonus_action(turn_state)
        turn_state["bonus_action_used"] = True
        save_turn_state(combat, player_id, turn_state)
        conditions = list(player.conditions or [])
        if "hidden" not in conditions:
            conditions.append("hidden")
            player.conditions = conditions
        narration = f"{player.name} uses Cunning Action: Hide."

    elif feature == "fighting_spirit":
        if player_class != "Fighter":
            _fail("Only fighters can use Fighting Spirit.")
        remaining = class_resources.get("fighting_spirit_remaining", 0)
        if remaining <= 0:
            _fail("No Fighting Spirit uses remaining.")
        _require_bonus_action(turn_state)
        class_resources["fighting_spirit_remaining"] = remaining - 1
        turn_state["bonus_action_used"] = True
        turn_state["fighting_spirit_active"] = True
        player.class_resources = class_resources
        grant_temporary_hp(player, player.level, source="fighting_spirit", replace_if_higher=True)
        class_resources = dict(player.class_resources or {})
        save_turn_state(combat, player_id, turn_state)
        narration = (
            f"{player.name} uses Fighting Spirit, gaining advantage on attacks "
            f"this turn and {player.level} temporary HP."
        )

    elif feature == "bardic_inspiration":
        if player_class != "Bard":
            _fail("Only bards can grant Bardic Inspiration.")
        _require_bonus_action(turn_state)
        if target is None or not target_id:
            _fail("Bardic Inspiration requires a target ally.")
        if str(target_id) == str(player_id):
            _fail("Bardic Inspiration cannot target yourself.")
        remaining = class_resources.get("bardic_inspiration_remaining", 0)
        if remaining <= 0:
            _fail("No Bardic Inspiration uses remaining.")

        die = derived.get("subclass_effects", {}).get("inspiration_die", "d6")
        die_faces = int(die.replace("d", "")) if isinstance(die, str) and die.startswith("d") else 6
        target_resources = dict(getattr(target, "class_resources", None) or {})
        existing_inspiration = target_resources.get("bardic_inspiration") or {}
        if existing_inspiration and int(existing_inspiration.get("uses_remaining", 1) or 0) > 0:
            _fail("Target already has an unused Bardic Inspiration die.")

        class_resources["bardic_inspiration_remaining"] = remaining - 1
        target_resources["bardic_inspiration"] = {
            "die": die,
            "uses_remaining": 1,
            "source_character_id": str(player_id),
            "source_character_name": getattr(player, "name", "") or "",
        }
        player.class_resources = class_resources
        target.class_resources = target_resources
        turn_state["bonus_action_used"] = True
        save_turn_state(combat, player_id, turn_state)
        target_character = target
        narration = f"{player.name} grants Bardic Inspiration ({die}) to {target.name}."
        dice_roll = {
            "faces": die_faces,
            "result": None,
            "label": f"Bardic Inspiration {die}",
            "granted": True,
        }

    elif feature == "ki_flurry":
        _require_class_level(player_class, player_level, "Monk", 2, "Flurry of Blows")
        _require_bonus_action(turn_state)
        ki = _spend_ki(class_resources)
        class_resources["ki_remaining"] = ki
        turn_state["bonus_action_used"] = True
        save_turn_state(combat, player_id, turn_state)
        attack_mod = derived.get("attack_bonus", 2)
        results = []
        for index in range(2):
            attack_roll = roll_dice_fn("1d20")
            hit_total = attack_roll["rolls"][0] + attack_mod
            results.append(f"attack {index + 1}: d20={attack_roll['rolls'][0]}+{attack_mod}={hit_total}")
        player.class_resources = class_resources
        narration = f"{player.name} spends 1 ki for Flurry of Blows: {' | '.join(results)}"
        dice_roll = {"faces": 20, "result": roll_dice_fn("1d20")["rolls"][0], "label": "Flurry of Blows"}

    elif feature == "ki_patient_defense":
        _require_class_level(player_class, player_level, "Monk", 2, "Patient Defense")
        _require_bonus_action(turn_state)
        class_resources["ki_remaining"] = _spend_ki(class_resources)
        player.class_resources = class_resources
        turn_state["bonus_action_used"] = True
        turn_state["dodging"] = True
        save_turn_state(combat, player_id, turn_state)
        narration = f"{player.name} spends 1 ki for Patient Defense and takes the Dodge action."

    elif feature in {"ki_step_of_the_wind_dash", "ki_step_of_the_wind_disengage"}:
        _require_class_level(player_class, player_level, "Monk", 2, "Step of the Wind")
        _require_bonus_action(turn_state)
        class_resources["ki_remaining"] = _spend_ki(class_resources)
        player.class_resources = class_resources
        turn_state["bonus_action_used"] = True
        if feature == "ki_step_of_the_wind_dash":
            turn_state["movement_max"] = (
                turn_state["movement_max"]
                + turn_state.get("base_movement_max", turn_state["movement_max"])
            )
            turn_state = record_mobile_dash_difficult_terrain_ignore(turn_state, actor_derived=derived)
            narration = f"{player.name} spends 1 ki for Step of the Wind: Dash."
        else:
            turn_state["disengaged"] = True
            narration = f"{player.name} spends 1 ki for Step of the Wind: Disengage."
        save_turn_state(combat, player_id, turn_state)

    elif feature == "ki_stunning_strike":
        _require_class_level(player_class, player_level, "Monk", 5, "Stunning Strike")
        class_resources["ki_remaining"] = _spend_ki(class_resources)
        player.class_resources = class_resources
        ki_dc = 8 + derived.get("proficiency_bonus", 2) + derived.get("ability_modifiers", {}).get("wis", 0)
        narration = f"{player.name} spends 1 ki for Stunning Strike. Target must make a DC {ki_dc} CON save."
        dice_roll = {"faces": 20, "result": ki_dc, "label": f"Stunning Strike DC{ki_dc}"}

    elif feature == "shadow_step":
        if player_class != "Monk":
            _fail("Only monks can use Shadow Step.")
        ki = class_resources.get("ki_remaining", 0)
        if ki < 2:
            _fail("Not enough ki points.")
        class_resources["ki_remaining"] = ki - 2
        player.class_resources = class_resources
        narration = f"{player.name} uses Shadow Step and gains advantage on the next melee attack."
        dice_roll = {"faces": 20, "result": roll_dice_fn("1d20")["rolls"][0], "label": "Shadow Step"}

    elif feature == "channel_divinity":
        if player_class != "Paladin":
            _fail("Only paladins can use this Channel Divinity feature.")
        if class_resources.get("channel_divinity_used"):
            _fail("Channel Divinity has already been used since the last short rest.")
        class_resources["channel_divinity_used"] = True
        subclass_effects = derived.get("subclass_effects", {})
        if subclass_effects.get("vengeance"):
            turn_state["vow_of_enmity_active"] = True
            save_turn_state(combat, player_id, turn_state)
            narration = f"{player.name} uses Channel Divinity: Vow of Enmity."
        elif subclass_effects.get("devotion"):
            narration = f"{player.name} uses Channel Divinity: Sacred Weapon."
        elif subclass_effects.get("ancients"):
            narration = f"{player.name} uses Channel Divinity: Nature's Wrath."
        elif subclass_effects.get("glory"):
            narration = f"{player.name} uses Channel Divinity: Inspiring Smite."
        else:
            narration = f"{player.name} uses Channel Divinity."
        player.class_resources = class_resources

    elif feature == "lay_on_hands":
        if player_class != "Paladin":
            _fail("Only paladins can use Lay on Hands.")
        _require_action(turn_state)
        pool = class_resources.get("lay_on_hands_remaining", 0)
        if pool <= 0:
            _fail("No Lay on Hands pool remaining.")
        if not can_receive_ordinary_healing(player):
            _fail("Ordinary healing cannot revive a dead character")
        heal_amount = min(5, pool)
        class_resources["lay_on_hands_remaining"] = pool - heal_amount
        hp_max = get_effective_hp_max(player, derived.get("hp_max", player.hp_current))
        apply_character_healing(player, heal_amount)
        player.class_resources = class_resources
        turn_state["action_used"] = True
        save_turn_state(combat, player_id, turn_state)
        narration = (
            f"{player.name} uses Lay on Hands to heal {heal_amount} HP "
            f"({player.hp_current}/{hp_max}). Remaining pool: {pool - heal_amount}."
        )
        dice_roll = {"faces": 20, "result": heal_amount, "label": f"Lay on Hands +{heal_amount}HP"}

    elif feature in {"lay_on_hands_cure_poison", "lay_on_hands_cure_disease"}:
        if player_class != "Paladin":
            _fail("Only paladins can use Lay on Hands.")
        _require_action(turn_state)
        pool = class_resources.get("lay_on_hands_remaining", 0)
        if pool < 5:
            _fail("Lay on Hands requires 5 pool points to cure a condition.")
        aliases = {"poisoned"} if feature == "lay_on_hands_cure_poison" else {"disease", "diseased"}
        if not _remove_matching_conditions(player, aliases):
            _fail("No matching condition to cure.")
        class_resources["lay_on_hands_remaining"] = pool - 5
        player.class_resources = class_resources
        turn_state["action_used"] = True
        save_turn_state(combat, player_id, turn_state)
        condition_label = "poison" if feature == "lay_on_hands_cure_poison" else "disease"
        narration = f"{player.name} uses Lay on Hands to cure {condition_label}. Remaining pool: {pool - 5}."
        dice_roll = {"faces": 20, "result": 5, "label": f"Lay on Hands cure {condition_label}"}

    elif feature == "war_priest_attack":
        if player_class != "Cleric":
            _fail("Only clerics can use War Priest.")
        remaining = class_resources.get("war_priest_remaining", 0)
        if remaining <= 0:
            _fail("No War Priest uses remaining.")
        _require_bonus_action(turn_state)
        class_resources["war_priest_remaining"] = remaining - 1
        turn_state["bonus_action_used"] = True
        save_turn_state(combat, player_id, turn_state)
        player.class_resources = class_resources
        narration = f"{player.name} invokes War Priest and can make a bonus weapon attack."

    elif feature == "destructive_wrath":
        if player_class != "Cleric":
            _fail("Only clerics can use Destructive Wrath.")
        if class_resources.get("channel_divinity_used"):
            _fail("Channel Divinity has already been used.")
        class_resources["channel_divinity_used"] = True
        turn_state["destructive_wrath_active"] = True
        save_turn_state(combat, player_id, turn_state)
        player.class_resources = class_resources
        narration = f"{player.name} uses Channel Divinity: Destructive Wrath."

    elif feature == "wild_shape":
        if player_class != "Druid":
            _fail("Only druids can use Wild Shape.")
        remaining = class_resources.get("wild_shape_remaining", 0)
        if remaining <= 0:
            _fail("No Wild Shape uses remaining.")
        class_resources["wild_shape_remaining"] = remaining - 1
        max_cr = derived.get("subclass_effects", {}).get("wild_shape_max_cr", 0.25)
        form_name = "Bear" if max_cr >= 1 else "Wolf"
        form = WILD_SHAPE_FORMS.get(form_name, {})
        class_resources["wild_shape_active"] = form_name
        class_resources["wild_shape_hp"] = form.get("hp", 20)
        player.class_resources = class_resources
        narration = f"{player.name} uses Wild Shape: {form_name}, gaining {form.get('hp', 20)} form HP."
        dice_roll = {"faces": 20, "result": form.get("hp", 20), "label": f"Wild Shape {form_name}"}

    elif feature == "symbiotic_entity":
        if player_class != "Druid":
            _fail("Only druids can use Symbiotic Entity.")
        remaining = class_resources.get("wild_shape_remaining", 0)
        if remaining <= 0:
            _fail("Symbiotic Entity requires one Wild Shape use.")
        class_resources["wild_shape_remaining"] = remaining - 1
        temp_hp = derived.get("subclass_effects", {}).get("symbiotic_temp_hp", 4 * player.level)
        class_resources["symbiotic_entity_active"] = True
        player.class_resources = class_resources
        grant_temporary_hp(player, temp_hp, source="symbiotic_entity", replace_if_higher=True)
        class_resources = dict(player.class_resources or {})
        narration = f"{player.name} activates Symbiotic Entity and gains {temp_hp} temporary HP."
        dice_roll = {"faces": 20, "result": temp_hp, "label": f"Symbiotic Entity +{temp_hp} temp HP"}

    elif feature == "tides_of_chaos":
        if player_class != "Sorcerer":
            _fail("Only sorcerers can use Tides of Chaos.")
        if class_resources.get("tides_of_chaos_used"):
            _fail("Tides of Chaos has already been used since the last long rest.")
        class_resources["tides_of_chaos_used"] = True
        turn_state["tides_of_chaos_active"] = True
        save_turn_state(combat, player_id, turn_state)
        player.class_resources = class_resources
        narration = f"{player.name} uses Tides of Chaos and 获得优势 on the next d20 roll."

    elif feature == "portent":
        if player_class != "Wizard":
            _fail("Only wizards can use Portent.")
        remaining = class_resources.get("portent_remaining", 0)
        if remaining <= 0:
            _fail("No Portent dice remaining.")
        class_resources["portent_remaining"] = remaining - 1
        portent_roll = roll_dice_fn("1d20")
        class_resources["portent_value"] = portent_roll["rolls"][0]
        player.class_resources = class_resources
        narration = f"{player.name} records a Portent die: {portent_roll['rolls'][0]}."
        dice_roll = {"faces": 20, "result": portent_roll["rolls"][0], "label": "Portent"}

    else:
        _fail(f"Unknown class feature: {feature}")

    return CombatClassFeatureResult(
        narration=narration,
        dice_roll=dice_roll,
        turn_state=turn_state,
        class_resources=class_resources,
        character_class=player_class,
        hp_max=get_effective_hp_max(player, derived.get("hp_max", player.hp_current)),
        temporary_hp=get_temporary_hp(player),
        target=target_character,
    )


def _require_class_level(player_class: str, level: int, required_class: str, required_level: int, name: str) -> None:
    if player_class != required_class:
        _fail(f"{name} requires {required_class}.")
    if level < required_level:
        _fail(f"{name} requires {required_class} level {required_level} or higher.")


def _require_action(turn_state: dict[str, Any]) -> None:
    if turn_state["action_used"]:
        _fail("Action already used")


def _require_bonus_action(turn_state: dict[str, Any]) -> None:
    if turn_state["bonus_action_used"]:
        _fail("Bonus action already used")


def _spend_ki(class_resources: dict[str, Any]) -> int:
    ki = class_resources.get("ki_remaining", 0)
    if ki < 1:
        _fail("Not enough ki points.")
    return ki - 1


def _remove_matching_conditions(character, aliases: set[str]) -> bool:
    normalized_aliases = {normalize_condition(alias) for alias in aliases}
    conditions = list(getattr(character, "conditions", None) or [])
    kept_conditions = [
        condition
        for condition in conditions
        if normalize_condition(condition) not in normalized_aliases
    ]
    removed = len(kept_conditions) != len(conditions)
    if removed:
        character.conditions = kept_conditions

    durations = dict(getattr(character, "condition_durations", None) or {})
    kept_durations = {
        key: value
        for key, value in durations.items()
        if normalize_condition(key) not in normalized_aliases
    }
    if len(kept_durations) != len(durations):
        character.condition_durations = kept_durations
        removed = True
    return removed
