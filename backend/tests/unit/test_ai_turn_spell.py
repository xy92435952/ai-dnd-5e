from services.combat_ai_spell_models import AiSpellResolution


def test_build_ai_spell_dice_result_persists_spell_attack_payload():
    from api.combat.ai_turn_spell import _build_ai_spell_dice_result

    resolution = AiSpellResolution(
        spell_name="Fire Bolt",
        spell_level=0,
        spell_target="hero-1",
        spell_data={
            "level": 0,
            "type": "damage",
            "damage": "1d10",
            "damage_type": "fire",
            "save": None,
        },
        is_cantrip=True,
        attack_roll={
            "d20": 17,
            "attack_bonus": 5,
            "attack_total": 22,
            "target_ac": 14,
            "hit": True,
            "spell_attack": True,
            "cover_bonus": 2,
        },
        damage=8,
        dice_detail={"formula": "1d10", "total": 8},
        damage_type="fire",
        target_new_hp=4,
        target_state={
            "target_id": "hero-1",
            "target_name": "Smoke Sentinel",
            "hp_current": 4,
            "new_hp": 4,
        },
    )
    tactical_decision = {
        "role": "striker",
        "reason": "using available damage spell Fire Bolt",
        "action_type": "spell",
        "action_name": "Fire Bolt",
    }

    dice = _build_ai_spell_dice_result(resolution, tactical_decision)

    assert dice["type"] == "ai_spell"
    assert dice["spell"] == {
        "name": "Fire Bolt",
        "spell_name": "Fire Bolt",
        "level": 0,
        "spell_level": 0,
        "is_cantrip": True,
        "type": "damage",
        "damage_dice": "1d10",
        "damage_type": "fire",
        "is_aoe": False,
    }
    assert dice["attack"]["spell_attack"] is True
    assert dice["attack"]["cover_bonus"] == 2
    assert dice["damage"] == 8
    assert dice["damage_roll"] == {"formula": "1d10", "total": 8}
    assert dice["damage_type"] == "fire"
    assert dice["target_state"]["target_name"] == "Smoke Sentinel"
    assert dice["tactical_decision"] == tactical_decision
    assert "save_result" not in dice


def test_build_ai_spell_dice_result_persists_control_save_without_damage_roll():
    from api.combat.ai_turn_spell import _build_ai_spell_dice_result

    save_result = {
        "ability": "wis",
        "d20": 7,
        "modifier": 1,
        "total": 8,
        "dc": 14,
        "success": False,
    }
    resolution = AiSpellResolution(
        spell_name="Hold Person",
        spell_level=2,
        spell_target="hero-1",
        spell_data={
            "level": 2,
            "type": "control",
            "save": "wis",
            "concentration": True,
        },
        is_cantrip=False,
        save_result=save_result,
        target_state={
            "target_id": "hero-1",
            "target_name": "Smoke Sentinel",
            "conditions": ["paralyzed"],
            "condition_durations": {"paralyzed": 10},
            "save": save_result,
        },
    )

    dice = _build_ai_spell_dice_result(resolution)

    assert dice["spell"] == {
        "name": "Hold Person",
        "spell_name": "Hold Person",
        "level": 2,
        "spell_level": 2,
        "is_cantrip": False,
        "type": "control",
        "save": "wis",
        "is_aoe": False,
        "concentration": True,
    }
    assert dice["save_result"] == save_result
    assert dice["target_state"]["save"] == save_result
    assert dice["target_state"]["conditions"] == ["paralyzed"]
    assert "damage_roll" not in dice
    assert "attack" not in dice
