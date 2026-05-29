from types import SimpleNamespace

from services.combat_skill_bar_service import build_skill_bar


def _character(char_class, level=1, slots=None, resources=None, equipment=None):
    return SimpleNamespace(
        char_class=char_class,
        level=level,
        spell_slots=slots or {},
        derived={"class_resources": resources or {}},
        equipment=equipment or {},
    )


def test_build_skill_bar_returns_ten_slots_with_attack_first():
    bar = build_skill_bar(_character("Fighter", level=1))

    assert len(bar) == 10
    assert bar[0]["k"] == "atk"
    assert bar[-1]["key"] == "0"
    assert bar[-1]["k"] == "pot_heal"
    assert bar[-1]["kind"] == "item"
    assert bar[-1]["cost"] == "动作"
    assert any(slot["k"] == "grapple" and slot["available"] is True for slot in bar)


def test_paladin_smite_reflects_first_level_slot_availability():
    bar = build_skill_bar(_character("Paladin", level=3, slots={"1st": 0}))

    smite = bar[1]
    assert smite["k"] == "smite"
    assert smite["available"] is False
    assert smite["reason"] == "需要 1 环法术位"


def test_rogue_skill_bar_keeps_sneak_attack_hint_scaling():
    bar = build_skill_bar(_character("Rogue", level=5))

    assert bar[1]["k"] == "sneak"
    assert "+3d6" in bar[1]["dmg_hint"]


def test_rogue_skill_bar_exposes_cunning_action_options_at_level_two():
    bar = build_skill_bar(_character("Rogue", level=2))
    slots = {slot["k"]: slot for slot in bar}

    assert slots["cunning_action_hide"]["key"] == "6"
    assert slots["cunning_action_hide"]["cost"] == "附赠"
    assert slots["cunning_action_dash"]["key"] == "7"
    assert slots["cunning_action_dash"]["cost"] == "附赠"
    assert slots["cunning_action_disengage"]["key"] == "8"
    assert slots["cunning_action_disengage"]["cost"] == "附赠"
    assert "dash" not in slots
    assert "disg" not in slots


def test_first_level_rogue_uses_normal_dash_and_disengage():
    bar = build_skill_bar(_character("Rogue", level=1))
    slots = {slot["k"]: slot for slot in bar}

    assert slots["dash"]["key"] == "7"
    assert slots["dash"]["cost"] == "动作"
    assert slots["disg"]["key"] == "8"
    assert slots["disg"]["cost"] == "动作"
    assert "cunning_action_dash" not in slots
    assert "cunning_action_disengage" not in slots


def test_action_cost_skills_are_not_labeled_as_bonus_actions():
    bar = build_skill_bar(_character("Paladin", level=3))
    slots = {slot["k"]: slot for slot in bar}

    assert slots["lay"]["cost"] == "动作"
    assert slots["lay"]["kind"] == "action"
    assert slots["divine_sense"]["cost"] == "动作"
    assert slots["divine_sense"]["kind"] == "action"
    assert slots["pot_heal"]["kind"] == "item"


def test_wizard_shield_is_shown_as_reaction_prompt_not_active_cast():
    bar = build_skill_bar(_character("Wizard", level=3, slots={"1st": 1}))
    slots = {slot["k"]: slot for slot in bar}

    assert slots["shield"]["cost"] == "反应·1环"
    assert slots["shield"]["available"] is False
    assert slots["shield"]["reason"] == "反应法术会在被攻击时自动提示"


def test_wizard_shield_still_reports_missing_slots_first():
    bar = build_skill_bar(_character("Wizard", level=3, slots={"1st": 0}))
    slots = {slot["k"]: slot for slot in bar}

    assert slots["shield"]["available"] is False
    assert slots["shield"]["reason"] == "需要 1 环法术位"


def test_offhand_skill_requires_two_equipped_light_melee_weapons():
    equipment = {
        "weapons": [
            {"name": "Longsword", "equipped": True},
            {"name": "Dagger", "equipped": True},
        ],
        "shield": {"name": "Shield", "equipped": False},
    }
    bar = build_skill_bar(_character("Bard", equipment=equipment))
    slots = {slot["k"]: slot for slot in bar}

    assert slots["off_attack"]["available"] is False
    assert "two equipped light melee weapons" in slots["off_attack"]["reason"]


def test_offhand_skill_available_for_two_equipped_light_melee_weapons():
    equipment = {
        "weapons": [
            {"name": "Shortsword", "equipped": True},
            {"name": "Dagger", "equipped": True},
        ],
        "shield": {"name": "Shield", "equipped": False},
    }
    bar = build_skill_bar(_character("Bard", equipment=equipment))
    slots = {slot["k"]: slot for slot in bar}

    assert slots["off_attack"]["available"] is True
    assert slots["off_attack"]["reason"] is None
