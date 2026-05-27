def test_build_enemy_from_module_preserves_spellcasting_fields():
    from services.game_combat_setup_service import build_enemy_from_module

    enemy = build_enemy_from_module({
        "name": "Cult Mage",
        "hp": 18,
        "ac": 12,
        "ability_scores": {"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 11},
        "actions": [{
            "name": "Dagger",
            "type": "melee_attack",
            "attack_bonus": 4,
            "damage_dice": "1d4+2",
            "damage_type": "piercing",
        }],
        "known_spells": ["Web"],
        "prepared_spells": ["Shield"],
        "cantrips": ["Fire Bolt"],
        "spell_slots": {"1st": 2, "2nd": 1},
        "spell_ability": "int",
        "spell_save_dc": 13,
        "multiattack": 2,
        "condition_immunities": ["charmed"],
        "vulnerabilities": ["radiant"],
        "recharge_abilities": [{
            "name": "Fire Breath",
            "recharge": "5-6",
            "description": "A cone of flame.",
        }],
    })

    assert enemy["known_spells"] == ["Web"]
    assert enemy["prepared_spells"] == ["Shield"]
    assert enemy["cantrips"] == ["Fire Bolt"]
    assert enemy["spell_slots"] == {"1st": 2, "2nd": 1}
    assert enemy["spell_ability"] == "int"
    assert enemy["spell_save_dc"] == 13
    assert enemy["concentration"] is None
    assert enemy["attack_bonus"] == 4
    assert enemy["multiattack"] == 2
    assert enemy["attacks_max"] == 2
    assert enemy["condition_immunities"] == ["charmed"]
    assert enemy["vulnerabilities"] == ["radiant"]
    assert enemy["recharge_abilities"][0]["name"] == "Fire Breath"
    assert enemy["recharge_abilities"][0]["threshold"] == 5
    assert enemy["recharge_abilities"][0]["available"] is True
    assert enemy["derived"]["spell_ability"] == "int"
    assert enemy["derived"]["spell_save_dc"] == 13
    assert enemy["derived"]["ability_modifiers"]["int"] == 3
