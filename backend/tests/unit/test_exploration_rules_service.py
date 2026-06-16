from types import SimpleNamespace

import pytest

from services.exploration_rules_service import (
    apply_trap_attack_to_target,
    apply_trap_trigger_to_target,
    build_exploration_context,
    can_attempt_hide,
    character_passive_summary,
    group_stealth_result,
    light_perception,
    noise_adjusted_detection_dc,
    party_best_passive,
    passive_detects,
    passive_investigation,
    passive_perception,
    resolve_passive_discoveries,
    resolve_hidden_status,
    resolve_surprise,
    resolve_trap_attack,
    resolve_trap_disarm,
    resolve_trap_trigger,
    passive_score,
)


def _character(
    *,
    char_id: str = "c1",
    name: str = "Scout",
    mods: dict | None = None,
    proficiency_bonus: int = 2,
    proficient_skills: list[str] | None = None,
    feats: list | None = None,
    conditions: list[str] | None = None,
    darkvision: int = 0,
) -> dict:
    derived = {
        "ability_modifiers": mods or {},
        "proficiency_bonus": proficiency_bonus,
    }
    if darkvision:
        derived["darkvision"] = darkvision
    return {
        "id": char_id,
        "name": name,
        "derived": derived,
        "proficient_skills": proficient_skills or [],
        "feats": feats or [],
        "conditions": conditions or [],
    }


def test_passive_perception_uses_wisdom_and_proficiency():
    character = _character(
        mods={"wis": 3},
        proficiency_bonus=3,
        proficient_skills=["perception"],
    )

    assert passive_perception(character) == 16


def test_passive_score_normalizes_chinese_skill_aliases():
    character = _character(
        mods={"wis": 2, "dex": 4},
        proficiency_bonus=2,
        proficient_skills=["\u611f\u77e5", "\u9690\u533f"],
    )

    assert passive_score(character, "\u5bdf\u89c9") == 14
    assert passive_score(character, "\u6f5c\u884c") == 16


def test_passive_score_accepts_flat_character_snapshots():
    snapshot = {
        "id": "flat",
        "name": "Flat Snapshot",
        "ability_modifiers": {"wis": 2},
        "proficiency_bonus": 3,
        "proficient_skills": ["perception"],
    }

    assert passive_perception(snapshot) == 15


def test_passive_investigation_uses_intelligence_and_observant_bonus():
    character = _character(
        mods={"int": 1, "wis": 4},
        proficiency_bonus=2,
        proficient_skills=["investigation"],
        feats=[{"name": "Observant", "effects": {}}],
    )

    assert passive_investigation(character) == 18


def test_passive_observant_bonus_uses_trusted_effects_for_perception_and_investigation():
    character = _character(
        mods={"int": 2, "wis": 3},
        proficiency_bonus=2,
        feats=[{"name": "Observant", "effects": {"passive_perception_bonus": 0}}],
    )

    assert passive_perception(character) == 18
    assert passive_investigation(character) == 17


def test_passive_score_ignores_client_supplied_bonus_on_other_feats():
    character = _character(
        mods={"int": 2, "wis": 3},
        proficiency_bonus=2,
        feats=[{
            "name": "Actor",
            "effects": {
                "passive_perception_bonus": 99,
                "passive_investigation_bonus": 99,
            },
        }],
    )

    assert passive_perception(character) == 13
    assert passive_investigation(character) == 12


def test_passive_detects_compares_passive_score_to_dc():
    character = _character(mods={"wis": 2}, proficient_skills=["perception"])

    assert passive_detects(character, 14)
    assert not passive_detects(character, 15)


def test_party_best_passive_returns_highest_score_and_character_identity():
    characters = [
        _character(char_id="low", name="Low", mods={"wis": 0}),
        _character(char_id="high", name="High", mods={"wis": 3}, proficient_skills=["perception"]),
    ]

    result = party_best_passive(characters)

    assert result == {
        "character_id": "high",
        "name": "High",
        "score": 15,
        "skill": "perception",
    }


def test_party_best_passive_accepts_object_like_characters():
    character = SimpleNamespace(
        id="obj-1",
        name="Object Scout",
        derived={"ability_modifiers": {"wis": 1}, "proficiency_bonus": 3},
        proficient_skills=["perception"],
        feats=[],
    )

    assert party_best_passive([character])["score"] == 14


def test_character_passive_summary_contains_core_exploration_scores():
    character = _character(
        char_id="scout",
        name="Scout",
        mods={"wis": 2, "int": 1, "dex": 4},
        proficiency_bonus=2,
        proficient_skills=["perception", "stealth"],
    )

    assert character_passive_summary(character) == {
        "character_id": "scout",
        "name": "Scout",
        "passive_perception": 14,
        "passive_investigation": 11,
        "passive_stealth": 16,
    }


def test_build_exploration_context_summarizes_party_passives():
    characters = [
        _character(char_id="wizard", name="Wizard", mods={"int": 4, "wis": 0, "dex": 1}),
        _character(
            char_id="rogue",
            name="Rogue",
            mods={"int": 0, "wis": 2, "dex": 4},
            proficient_skills=["perception", "stealth"],
        ),
    ]

    context = build_exploration_context(characters)

    assert context["character_passives"][0]["passive_investigation"] == 14
    assert context["party_best_passive"]["perception"]["character_id"] == "rogue"
    assert context["party_best_passive"]["perception"]["score"] == 14
    assert context["party_best_passive"]["investigation"]["character_id"] == "wizard"
    assert context["party_best_passive"]["investigation"]["score"] == 14
    assert context["party_best_passive"]["stealth"]["character_id"] == "rogue"
    assert context["party_best_passive"]["stealth"]["score"] == 16
    assert context["group_stealth"]["success_rule"] == "at_least_half_members_meet_or_exceed_dc"
    assert context["surprise"]["rule"] == "compare_each_ambusher_stealth_total_to_each_target_passive_perception"
    assert context["light_and_hidden"]["hide_rule"] == "cannot_hide_from_observer_that_can_see_actor_clearly"
    assert context["light_and_hidden"]["noise_dc_modifiers"]["loud"] == -5
    assert context["passive_discovery"]["features"] == []


def test_light_perception_applies_darkvision_one_step_improvement():
    observer = _character(darkvision=60)

    darkness = light_perception(observer, "darkness", distance_ft=30)
    dim = light_perception(observer, "dim", distance_ft=30)
    far_darkness = light_perception(observer, "darkness", distance_ft=90)

    assert darkness["ambient_light"] == "darkness"
    assert darkness["effective_light"] == "dim"
    assert darkness["within_darkvision"] is True
    assert darkness["sight_check_disadvantage"] is True
    assert darkness["sight_blocked"] is False
    assert dim["effective_light"] == "bright"
    assert dim["sight_check_disadvantage"] is False
    assert far_darkness["effective_light"] == "darkness"
    assert far_darkness["sight_blocked"] is True


def test_noise_adjusted_detection_dc_makes_loud_targets_easier_to_detect():
    assert noise_adjusted_detection_dc(15, "silent")["dc"] == 20
    assert noise_adjusted_detection_dc(15, "quiet")["dc"] == 17
    assert noise_adjusted_detection_dc(15, "normal")["dc"] == 15
    assert noise_adjusted_detection_dc(15, "loud")["dc"] == 10
    assert noise_adjusted_detection_dc(15, "very_loud")["dc"] == 5


def test_can_attempt_hide_requires_visual_obscurement_and_no_loud_noise():
    actor = _character(char_id="rogue", name="Rogue")
    observer = _character(char_id="guard", name="Guard")

    open_bright = can_attempt_hide(actor, observer, cover="none", light_level="bright")
    behind_cover = can_attempt_hide(actor, observer, cover="total", light_level="bright")
    invisible = can_attempt_hide(
        _character(char_id="rogue", name="Rogue", conditions=["invisible"]),
        observer,
        cover="none",
        light_level="bright",
    )
    noisy = can_attempt_hide(actor, observer, cover="total", light_level="bright", noise_level="loud")

    assert open_bright["can_attempt"] is False
    assert open_bright["blockers"] == ["observer_can_see_actor_clearly"]
    assert behind_cover["can_attempt"] is True
    assert behind_cover["enablers"] == ["total_cover"]
    assert invisible["can_attempt"] is True
    assert invisible["enablers"] == ["invisible"]
    assert noisy["can_attempt"] is False
    assert "loud_noise_reveals_position" in noisy["blockers"]


def test_darkness_allows_hiding_only_when_observer_sight_is_blocked():
    actor = _character(char_id="rogue", name="Rogue")
    human_guard = _character(char_id="human", name="Human Guard")
    elf_guard = _character(char_id="elf", name="Elf Guard", darkvision=60)

    unseen_by_human = can_attempt_hide(actor, human_guard, light_level="darkness", distance_ft=30)
    seen_by_darkvision = can_attempt_hide(actor, elf_guard, light_level="darkness", distance_ft=30)

    assert unseen_by_human["can_attempt"] is True
    assert unseen_by_human["enablers"] == ["darkness_or_heavy_obscurement"]
    assert seen_by_darkvision["light"]["effective_light"] == "dim"
    assert seen_by_darkvision["can_attempt"] is False


def test_resolve_hidden_status_uses_passive_perception_and_noise_adjusted_dc():
    actor = _character(
        char_id="rogue",
        name="Rogue",
        mods={"dex": 4},
        proficient_skills=["stealth"],
    )
    guard = _character(
        char_id="guard",
        name="Guard",
        mods={"wis": 2},
        proficient_skills=["perception"],
    )

    quiet_result = resolve_hidden_status(
        actor,
        [guard],
        stealth_total=15,
        cover="total",
        noise_level="quiet",
    )
    loud_result = resolve_hidden_status(
        actor,
        [guard],
        stealth_total=15,
        cover="total",
        noise_level="loud",
    )

    assert quiet_result["detection_dc"]["dc"] == 17
    assert quiet_result["hidden"] is True
    assert quiet_result["condition"] == "hidden"
    assert quiet_result["detected_by_ids"] == []
    assert loud_result["detection_dc"]["dc"] == 10
    assert loud_result["hidden"] is False
    assert loud_result["detected_by_ids"] == ["guard"]


def test_resolve_surprise_marks_targets_that_notice_no_ambushers():
    targets = [
        _character(char_id="fighter", name="Fighter", mods={"wis": 0}),
        _character(char_id="scout", name="Scout", mods={"wis": 3}, proficient_skills=["perception"]),
    ]

    result = resolve_surprise(
        targets,
        [
            {"character_id": "goblin-a", "name": "Goblin A", "total": 16},
            {"character_id": "goblin-b", "name": "Goblin B", "total": 11},
        ],
    )

    assert result["rule"] == "target_is_surprised_if_it_notices_no_ambusher_before_combat"
    assert result["ambushers"][0]["character_id"] == "goblin-a"
    assert result["targets"][0]["target_id"] == "fighter"
    assert result["targets"][0]["passive_score"] == 10
    assert result["targets"][0]["noticed_ambusher_ids"] == []
    assert result["targets"][0]["surprised"] is True
    assert result["targets"][1]["target_id"] == "scout"
    assert result["targets"][1]["passive_score"] == 15
    assert result["targets"][1]["noticed_ambusher_ids"] == ["goblin-b"]
    assert result["targets"][1]["surprised"] is False
    assert result["surprised_target_ids"] == ["fighter"]


def test_resolve_surprise_respects_alert_feat_no_surprise():
    targets = [
        _character(char_id="ranger", name="Ranger", mods={"wis": 0}, feats=["Alert"]),
        _character(
            char_id="monk",
            name="Monk",
            mods={"wis": 0},
            feats=[{"name": "Custom Sense", "effects": {"no_surprise": True}}],
        ),
    ]

    result = resolve_surprise(
        targets,
        [{"character_id": "assassin", "total": 25}],
    )

    assert result["surprised_target_ids"] == []
    assert all(item["no_surprise"] for item in result["targets"])
    assert all(not item["surprised"] for item in result["targets"])


def test_resolve_passive_discoveries_detects_hidden_features_by_best_passive_score():
    characters = [
        _character(char_id="fighter", name="Fighter", mods={"wis": 0, "int": 0}),
        _character(char_id="scout", name="Scout", mods={"wis": 3, "int": 1}, proficient_skills=["perception"]),
    ]

    result = resolve_passive_discoveries(
        characters,
        [
            {"id": "wire", "name": "Tripwire", "kind": "trap", "dc": 15},
            {"id": "door", "name": "False Wall", "kind": "secret_door", "dc": 16},
        ],
    )

    assert result["rule"] == "party_best_passive_for_feature_skill_meets_dc"
    assert result["detected_feature_ids"] == ["wire"]
    assert result["hidden_feature_ids"] == ["door"]
    assert result["features"][0]["skill"] == "perception"
    assert result["features"][0]["detected_by"]["character_id"] == "scout"
    assert result["features"][0]["best_score"] == 15
    assert result["features"][1]["detected_by"] is None


def test_resolve_passive_discoveries_uses_investigation_for_clues_and_mechanisms():
    characters = [
        _character(char_id="sage", name="Sage", mods={"int": 4, "wis": 0}, proficient_skills=["investigation"]),
    ]

    result = resolve_passive_discoveries(
        characters,
        [
            {"name": "Ledger clue", "kind": "clue", "dc": 15},
            {"name": "Poison needle", "kind": "trap", "detection_skill": "investigation", "dc": 17},
        ],
    )

    assert result["detected_feature_ids"] == ["Ledger clue"]
    assert result["hidden_feature_ids"] == ["Poison needle"]
    assert result["features"][0]["feature_id"] == "Ledger clue"
    assert result["features"][0]["skill"] == "investigation"
    assert result["features"][0]["best_score"] == 16
    assert result["features"][1]["skill"] == "investigation"


def test_resolve_trap_trigger_halves_damage_on_successful_save():
    target = _character(
        char_id="rogue",
        name="Rogue",
        mods={"dex": 3},
    )
    target["derived"]["saving_throws"] = {"dex": 5}

    result = resolve_trap_trigger(
        {
            "id": "dart",
            "name": "Poison Dart",
            "save_ability": "dex",
            "save_dc": 14,
            "damage_dice": "2d10",
            "damage_type": "poison",
        },
        target,
        d20_roller=lambda _expr: {"rolls": [12], "total": 12},
        damage_roller=lambda expr: {"notation": expr, "rolls": [8, 6], "total": 14},
    )

    assert result["trap_id"] == "dart"
    assert result["target_id"] == "rogue"
    assert result["saved"] is True
    assert result["save"]["total"] == 17
    assert result["rolled_damage"] == 14
    assert result["final_damage"] == 7
    assert result["conditions_applied"] == []
    assert result["mutates_hp"] is False


def test_resolve_trap_trigger_applies_full_damage_and_failed_conditions():
    target = _character(char_id="fighter", name="Fighter", mods={"dex": 0})
    target["derived"]["saving_throws"] = {"dex": 0}

    result = resolve_trap_trigger(
        {
            "name": "Net Snare",
            "dc": 13,
            "damage": "1d6",
            "condition_on_fail": "restrained",
            "half_on_save": False,
        },
        target,
        d20_roller=lambda _expr: {"rolls": [7], "total": 7},
        damage_roller=lambda expr: {"notation": expr, "rolls": [5], "total": 5},
    )

    assert result["trap_id"] == "Net Snare"
    assert result["save_ability"] == "dex"
    assert result["save_dc"] == 13
    assert result["saved"] is False
    assert result["damage_dice"] == "1d6"
    assert result["half_on_save"] is False
    assert result["final_damage"] == 5
    assert result["conditions_applied"] == ["restrained"]


def test_resolve_trap_trigger_accepts_object_like_targets_and_ability_aliases():
    target = SimpleNamespace(
        id="wizard",
        name="Wizard",
        ability_scores={"wis": 14},
        derived={"saving_throws": {"wis": 4}, "ability_modifiers": {"wis": 2}},
        conditions=[],
        condition_durations={},
    )

    result = resolve_trap_trigger(
        {
            "id": "glyph",
            "saving_throw": "wisdom",
            "save_dc": 15,
            "damage_dice": "3d8",
            "conditions_on_fail": ["frightened"],
        },
        target,
        d20_roller=lambda _expr: {"rolls": [10], "total": 10},
        damage_roller=lambda expr: {"notation": expr, "rolls": [4, 4, 4], "total": 12},
    )

    assert result["target_id"] == "wizard"
    assert result["save_ability"] == "wis"
    assert result["saved"] is False
    assert result["final_damage"] == 12
    assert result["conditions_applied"] == ["frightened"]


def test_apply_trap_trigger_to_object_target_mutates_hp_and_conditions():
    target = SimpleNamespace(
        id="rogue",
        name="Rogue",
        hp_current=9,
        ability_scores={"dex": 16},
        derived={"saving_throws": {"dex": 5}, "ability_modifiers": {"dex": 3}, "hp_max": 12},
        conditions=[],
        condition_durations={},
        death_saves=None,
        class_resources={},
    )

    result = apply_trap_trigger_to_target(
        {
            "id": "snare",
            "save_dc": 14,
            "damage_dice": "2d6",
            "condition_on_fail": "restrained",
        },
        target,
        d20_roller=lambda _expr: {"rolls": [5], "total": 5},
        damage_roller=lambda expr: {"notation": expr, "rolls": [4, 3], "total": 7},
    )

    assert result["mutates_hp"] is True
    assert result["saved"] is False
    assert result["hp_before"] == 9
    assert result["hp_after"] == 2
    assert target.hp_current == 2
    assert target.conditions == ["restrained"]
    assert result["conditions_added"] == ["restrained"]
    assert result["target_state"]["hp_current"] == 2


def test_apply_trap_trigger_to_dict_target_drops_to_zero_and_adds_unconscious():
    target = {
        "id": "fighter",
        "name": "Fighter",
        "hp_current": 4,
        "ability_scores": {"dex": 10},
        "derived": {"saving_throws": {"dex": 0}, "ability_modifiers": {"dex": 0}},
        "conditions": [],
        "condition_durations": {},
        "death_saves": None,
    }

    result = apply_trap_trigger_to_target(
        {"id": "pit", "dc": 14, "damage_dice": "2d8"},
        target,
        d20_roller=lambda _expr: {"rolls": [8], "total": 8},
        damage_roller=lambda expr: {"notation": expr, "rolls": [5, 4], "total": 9},
    )

    assert result["hp_after"] == 0
    assert target["hp_current"] == 0
    assert target["death_saves"] == {"successes": 0, "failures": 0, "stable": False}
    assert "unconscious" in target["conditions"]
    assert result["damage_application"]["dropped_to_zero"] is True
    assert result["target_state"]["conditions"] == ["unconscious"]


def test_apply_trap_trigger_does_not_duplicate_failed_condition():
    target = SimpleNamespace(
        id="cleric",
        name="Cleric",
        hp_current=10,
        ability_scores={"wis": 14},
        derived={"saving_throws": {"wis": 2}, "ability_modifiers": {"wis": 2}, "hp_max": 10},
        conditions=["frightened"],
        condition_durations={},
        death_saves=None,
        class_resources={},
    )

    result = apply_trap_trigger_to_target(
        {
            "id": "glyph",
            "saving_throw": "wis",
            "save_dc": 18,
            "damage_dice": "0",
            "condition_on_fail": "frightened",
        },
        target,
        d20_roller=lambda _expr: {"rolls": [3], "total": 3},
        damage_roller=lambda expr: {"notation": expr, "rolls": [0], "total": 0},
    )

    assert target.conditions == ["frightened"]
    assert result["conditions_applied"] == ["frightened"]
    assert result["conditions_added"] == []


def test_apply_trap_trigger_can_use_feather_fall_to_prevent_fall_damage():
    target = SimpleNamespace(
        id="wizard",
        name="Wizard",
        hp_current=6,
        ability_scores={"dex": 14},
        derived={"saving_throws": {"dex": 2}, "ability_modifiers": {"dex": 2}, "hp_max": 10},
        conditions=[],
        condition_durations={},
        death_saves=None,
        class_resources={},
    )
    caster = SimpleNamespace(
        id="bard-1",
        name="Lyra",
        char_class="Bard",
        level=5,
        known_spells=["Feather Fall"],
        prepared_spells=[],
        spell_slots={"1st": 1},
    )

    result = apply_trap_trigger_to_target(
        {
            "id": "pit",
            "name": "Hidden Pit",
            "damage_type": "fall",
            "fall_distance_ft": 30,
            "save_dc": 14,
            "damage_dice": "2d6",
        },
        target,
        d20_roller=lambda _expr: {"rolls": [1], "total": 1},
        damage_roller=lambda expr: {"notation": expr, "rolls": [4, 3], "total": 7},
        feather_fall_caster=caster,
        feather_fall_reaction_state={},
    )

    assert target.hp_current == 6
    assert result["final_damage"] == 0
    assert result["damage_application"]["damage"] == 0
    assert result["feather_fall"]["spell_name"] == "Feather Fall"
    assert result["feather_fall"]["damage_prevented"] == 7
    assert caster.spell_slots["1st"] == 0


def test_apply_trap_trigger_rejects_invalid_feather_fall_caster():
    target = SimpleNamespace(
        id="wizard",
        name="Wizard",
        hp_current=6,
        ability_scores={"dex": 14},
        derived={"saving_throws": {"dex": 2}, "ability_modifiers": {"dex": 2}, "hp_max": 10},
        conditions=[],
        condition_durations={},
        death_saves=None,
        class_resources={},
    )
    caster = SimpleNamespace(
        id="rogue-1",
        name="Nope",
        char_class="Rogue",
        level=5,
        known_spells=[],
        prepared_spells=[],
        spell_slots={},
    )

    with pytest.raises(ValueError):
        apply_trap_trigger_to_target(
            {
                "id": "pit",
                "name": "Hidden Pit",
                "damage_type": "fall",
                "fall_distance_ft": 30,
                "save_dc": 14,
                "damage_dice": "2d6",
            },
            target,
            d20_roller=lambda _expr: {"rolls": [1], "total": 1},
            damage_roller=lambda expr: {"notation": expr, "rolls": [4, 3], "total": 7},
            feather_fall_caster=caster,
            feather_fall_reaction_state={},
        )


def test_resolve_trap_attack_hits_ac_and_rolls_damage():
    target = _character(char_id="rogue", name="Rogue")
    target["derived"]["ac"] = 15

    result = resolve_trap_attack(
        {
            "id": "blade",
            "name": "Swinging Blade",
            "attack_bonus": 6,
            "damage_dice": "1d10",
            "damage_type": "slashing",
            "condition_on_hit": "bleeding",
        },
        target,
        d20_roller=lambda expr: {"notation": expr, "rolls": [12], "total": 12},
        damage_roller=lambda expr: {"notation": expr, "rolls": [7], "total": 7},
    )

    assert result["trap_id"] == "blade"
    assert result["target_id"] == "rogue"
    assert result["attack"]["attack_total"] == 18
    assert result["attack"]["target_ac"] == 15
    assert result["hit"] is True
    assert result["damage_dice"] == "1d10"
    assert result["final_damage"] == 7
    assert result["conditions_applied"] == ["bleeding"]
    assert result["mutates_hp"] is False


def test_resolve_trap_attack_miss_does_not_roll_damage():
    target = _character(char_id="fighter", name="Fighter")
    target["derived"]["ac"] = 18

    result = resolve_trap_attack(
        {"id": "dart", "to_hit": 4, "damage_dice": "1d6"},
        target,
        d20_roller=lambda expr: {"notation": expr, "rolls": [5], "total": 5},
        damage_roller=lambda _expr: (_ for _ in ()).throw(AssertionError("should not roll damage")),
    )

    assert result["attack"]["attack_total"] == 9
    assert result["hit"] is False
    assert result["final_damage"] == 0
    assert result["damage_roll"]["rolls"] == []
    assert result["conditions_applied"] == []


def test_apply_trap_attack_to_target_mutates_hp_and_conditions_on_hit():
    target = SimpleNamespace(
        id="cleric",
        name="Cleric",
        hp_current=10,
        ability_scores={"dex": 10},
        derived={"ac": 14, "hp_max": 10},
        conditions=[],
        condition_durations={},
        death_saves=None,
        class_resources={},
    )

    result = apply_trap_attack_to_target(
        {
            "id": "needle",
            "attack_bonus": 5,
            "damage_dice": "1d6",
            "damage_type": "poison",
            "conditions_on_hit": ["poisoned"],
        },
        target,
        d20_roller=lambda expr: {"notation": expr, "rolls": [11], "total": 11},
        damage_roller=lambda expr: {"notation": expr, "rolls": [4], "total": 4},
    )

    assert result["hit"] is True
    assert result["hp_before"] == 10
    assert result["hp_after"] == 6
    assert target.hp_current == 6
    assert target.conditions == ["poisoned"]
    assert result["conditions_added"] == ["poisoned"]


def test_resolve_trap_disarm_uses_configured_ability_and_tool_proficiency():
    actor = _character(
        char_id="rogue",
        name="Rogue",
        mods={"dex": 4},
        proficiency_bonus=3,
    )
    actor["tool_proficiencies"] = ["Thieves' Tools"]

    result = resolve_trap_disarm(
        {
            "id": "needle",
            "name": "Poison Needle",
            "disarm_dc": 15,
            "disarm_ability": "dexterity",
            "disarm_tool": "thieves' tools",
        },
        actor,
        d20_roller=lambda expr: {"notation": expr, "rolls": [8], "total": 8},
    )

    assert result["trap_id"] == "needle"
    assert result["actor_id"] == "rogue"
    assert result["ability"] == "dex"
    assert result["tool"] == "thieves' tools"
    assert result["tool_proficient"] is True
    assert result["ability_modifier"] == 4
    assert result["proficiency_bonus"] == 3
    assert result["modifier"] == 7
    assert result["total"] == 15
    assert result["success"] is True
    assert result["triggered"] is False
    assert result["mutates_state"] is False


def test_resolve_trap_disarm_failed_attempt_triggers_by_default():
    actor = _character(char_id="fighter", name="Fighter", mods={"dex": 1})

    result = resolve_trap_disarm(
        {"id": "wire", "dc": 13},
        actor,
        d20_roller=lambda expr: {"notation": expr, "rolls": [7], "total": 7},
    )

    assert result["dc"] == 13
    assert result["tool"] == "thieves' tools"
    assert result["tool_proficient"] is False
    assert result["proficiency_bonus"] == 0
    assert result["total"] == 8
    assert result["success"] is False
    assert result["triggered"] is True


def test_resolve_trap_disarm_can_fail_without_triggering():
    actor = _character(char_id="wizard", name="Wizard", mods={"int": 4})

    result = resolve_trap_disarm(
        {
            "id": "glyph",
            "disable_dc": 18,
            "disable_ability": "intelligence",
            "tool": "arcana kit",
            "trigger_on_failed_disarm": False,
        },
        actor,
        d20_roller=lambda expr: {"notation": expr, "rolls": [10], "total": 10},
    )

    assert result["ability"] == "int"
    assert result["dc"] == 18
    assert result["total"] == 14
    assert result["success"] is False
    assert result["triggered"] is False
    assert result["trigger_on_failed_disarm"] is False


def test_resolve_trap_disarm_accepts_object_like_actor_and_tool_alias():
    actor = SimpleNamespace(
        id="artificer",
        name="Artificer",
        derived={"ability_modifiers": {"dex": 2}, "proficiency_bonus": 2},
        tool_proficiencies=["Thieves Tools"],
    )

    result = resolve_trap_disarm(
        {"id": "lock", "disarm_dc": 14, "disarm_tool": "thieves' tools"},
        actor,
        d20_roller=lambda expr: {"notation": expr, "rolls": [10], "total": 10},
    )

    assert result["actor_id"] == "artificer"
    assert result["tool_proficient"] is True
    assert result["total"] == 14
    assert result["success"] is True


def test_group_stealth_succeeds_when_at_least_half_succeed():
    result = group_stealth_result(
        [
            {"character_id": "a", "total": 18},
            {"character_id": "b", "total": 11},
            {"character_id": "c", "success": True},
            {"character_id": "d", "success": False},
        ],
        dc=14,
    )

    assert result == {
        "dc": 14,
        "members": 4,
        "successes": 2,
        "needed": 2,
        "success": True,
        "failed_member_ids": ["b", "d"],
    }


def test_group_stealth_fails_empty_or_less_than_half_successes():
    assert group_stealth_result([], 12)["success"] is False

    result = group_stealth_result(
        [
            {"id": "a", "total": 8},
            {"id": "b", "total": 12},
            {"id": "c", "total": 9},
        ],
        dc=12,
    )

    assert result["needed"] == 2
    assert result["successes"] == 1
    assert result["success"] is False
    assert result["failed_member_ids"] == ["a", "c"]
