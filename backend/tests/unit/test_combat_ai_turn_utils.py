from types import SimpleNamespace

from api.combat.ai_turn_utils import build_reaction_prompt


def test_build_reaction_prompt_surfaces_hp_snapshot_for_ui_preview():
    player = SimpleNamespace(
        id="char-1",
        derived={"ac": 14},
        char_class="Wizard",
        level=3,
        hp_current=0,
        death_saves={"failures": 0, "successes": 0, "stable": False},
        conditions=["unconscious"],
        known_spells=["Shield"],
        prepared_spells=[],
        spell_slots={"1st": 1},
    )
    player_ts = {
        "reaction_used": False,
        "pending_attack_reaction": {
            "trigger": "incoming_attack",
            "target_hp_before_damage": 12,
            "target_temporary_hp_before_damage": 2,
            "target_wild_shape_hp_before_damage": None,
            "target_conditions_before_damage": [],
            "events": [
                {
                    "hit": True,
                    "attack_total": 16,
                    "target_ac": 14,
                    "damage": 9,
                    "damage_type": "slashing",
                },
            ],
        },
    }

    can_react, has_prompt, prompt = build_reaction_prompt(
        player,
        player_ts,
        target_id="char-1",
        actor_name="Goblin",
        actor_id="enemy-1",
        total_damage=9,
        result_obj=SimpleNamespace(attack_roll={"attack_total": 16}),
    )

    assert can_react is True
    assert has_prompt is True
    assert prompt["target_hp_before_damage"] == 12
    assert prompt["target_temporary_hp_before_damage"] == 2
    assert prompt["incoming_damage"] == 9
    assert prompt["available_reactions"][0]["type"] == "shield"
    assert prompt["available_reactions"][0]["damage_prevented"] == 9
