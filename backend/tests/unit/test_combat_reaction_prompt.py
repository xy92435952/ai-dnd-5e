from types import SimpleNamespace

from api.combat.ai_turn_utils import build_reaction_prompt
from services.combat_service import AttackResult


def _character(**overrides):
    data = {
        "id": "char-1",
        "derived": {"ac": 13},
        "char_class": "Wizard",
        "level": 3,
        "known_spells": ["Shield", "Absorb Elements", "Counterspell"],
        "prepared_spells": ["Hellish Rebuke"],
        "spell_slots": {"1st": 2, "3rd": 1},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_weapon_reaction_prompt_only_offers_supported_reactions():
    attack = AttackResult(
        attack_roll={"attack_total": 17},
        damage=6,
        damage_roll=None,
        narration="hit",
    )

    can_react, has_prompt, prompt = build_reaction_prompt(
        _character(),
        {"reaction_used": False},
        "char-1",
        "Goblin",
        "enemy-1",
        6,
        attack,
    )

    assert can_react is True
    assert has_prompt is True
    ids = [item["id"] for item in prompt["available_reactions"]]
    assert ids == ["shield", "hellish_rebuke"]
    assert "absorb_elements" not in ids
    assert "counterspell" not in ids
    assert prompt["options"] == [
        {
            "type": "shield",
            "label": "Shield",
            "target_id": "enemy-1",
            "cost": "1st-level spell slot",
            "effect": "+5 AC until the start of your next turn",
        },
        {
            "type": "hellish_rebuke",
            "label": "Hellish Rebuke",
            "target_id": "enemy-1",
            "cost": "1st-level spell slot",
            "effect": "Deal 2d10 fire damage to the attacker",
        },
    ]
