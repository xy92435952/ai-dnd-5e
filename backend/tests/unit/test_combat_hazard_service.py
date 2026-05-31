from types import SimpleNamespace


def test_resolve_movement_hazard_rolls_hazard_cell(monkeypatch):
    from services import combat_hazard_service as hazards

    monkeypatch.setattr(
        hazards,
        "roll_dice",
        lambda expr: {"notation": expr, "rolls": [4], "bonus": 0, "total": 4},
    )

    result = hazards.resolve_movement_hazard(
        {
            "_encounter_template": {
                "hazards": ["sparking conduit"],
            },
            "2_2": "hazard",
        },
        {"x": 2, "y": 2},
    )

    assert result["triggered"] is True
    assert result["cell"] == "2_2"
    assert result["label"] == "sparking conduit"
    assert result["damage_type"] == "lightning"
    assert result["final_damage"] == 4


def test_resolve_movement_hazard_preserves_authored_save_metadata(monkeypatch):
    from services import combat_hazard_service as hazards

    monkeypatch.setattr(
        hazards,
        "roll_dice",
        lambda expr: {"notation": expr, "rolls": [2, 5], "bonus": 0, "total": 7},
    )

    result = hazards.resolve_movement_hazard(
        {
            "_encounter_template": {
                "hazards": [{
                    "name": "fire jet",
                    "damage_dice": "2d6",
                    "damage_type": "fire",
                    "save_dc": 13,
                    "save_ability": "dexterity",
                    "half_on_save": True,
                }],
            },
            "2_2": "hazard",
        },
        {"x": 2, "y": 2},
    )

    assert result["label"] == "fire jet"
    assert result["damage_dice"] == "2d6"
    assert result["damage_type"] == "fire"
    assert result["save_dc"] == 13
    assert result["save_ability"] == "dex"
    assert result["half_on_save"] is True


def test_resolve_movement_hazard_ignores_difficult_terrain():
    from services.combat_hazard_service import resolve_movement_hazard

    assert resolve_movement_hazard({"2_2": "difficult"}, {"x": 2, "y": 2}) is None


def test_apply_hazard_damage_to_enemy_uses_resistance():
    from services.combat_hazard_service import apply_hazard_damage_to_enemy

    enemy = {
        "id": "enemy-1",
        "name": "Resistant Ooze",
        "hp_current": 12,
        "hp_max": 12,
        "resistances": ["fire"],
        "immunities": [],
        "vulnerabilities": [],
    }
    result = apply_hazard_damage_to_enemy(
        enemy,
        {
            "triggered": True,
            "label": "burning oil",
            "damage_type": "fire",
            "rolled_damage": 7,
            "damage": 7,
            "final_damage": 7,
        },
    )

    assert result["damage"] == 3
    assert result["resistance_applied"] is True
    assert result["hp_before"] == 12
    assert result["hp_after"] == 9
    assert enemy["hp_current"] == 9


def test_apply_hazard_damage_to_character_updates_hp():
    from services.combat_hazard_service import apply_hazard_damage_to_character

    character = SimpleNamespace(
        id="char-1",
        name="Hero",
        hp_current=10,
        derived={},
        conditions=[],
        class_resources={},
        death_saves=None,
        char_class="Fighter",
    )

    result = apply_hazard_damage_to_character(
        character,
        {
            "triggered": True,
            "label": "acid vent",
            "damage_type": "acid",
            "rolled_damage": 4,
            "damage": 4,
            "final_damage": 4,
        },
    )

    assert result["hp_before"] == 10
    assert result["hp_after"] == 6
    assert character.hp_current == 6


def test_apply_hazard_damage_to_character_halves_damage_on_successful_save(monkeypatch):
    from services import combat_hazard_service as hazards

    monkeypatch.setattr(
        hazards,
        "roll_saving_throw",
        lambda target, ability, dc: {
            "ability": ability,
            "d20": 14,
            "modifier": 2,
            "total": 16,
            "dc": dc,
            "success": True,
        },
    )
    character = SimpleNamespace(
        id="char-1",
        name="Hero",
        hp_current=20,
        ability_scores={"dex": 14},
        derived={"ability_modifiers": {"dex": 2}},
        conditions=[],
        class_resources={},
        death_saves=None,
        char_class="Fighter",
    )

    result = hazards.apply_hazard_damage_to_character(
        character,
        {
            "triggered": True,
            "label": "fire jet",
            "damage_type": "fire",
            "rolled_damage": 9,
            "damage": 9,
            "final_damage": 9,
            "save_dc": 13,
            "save_ability": "dex",
        },
    )

    assert result["saving_throw"]["success"] is True
    assert result["damage_after_save"] == 4
    assert result["damage"] == 4
    assert result["hp_after"] == 16
    assert character.hp_current == 16


def test_apply_hazard_damage_to_enemy_can_negate_on_successful_save(monkeypatch):
    from services import combat_hazard_service as hazards

    monkeypatch.setattr(
        hazards,
        "roll_saving_throw",
        lambda target, ability, dc: {
            "ability": ability,
            "d20": 18,
            "modifier": 1,
            "total": 19,
            "dc": dc,
            "success": True,
        },
    )
    enemy = {
        "id": "enemy-1",
        "name": "Goblin",
        "hp_current": 7,
        "hp_max": 7,
        "ability_scores": {"dex": 12},
        "derived": {"ability_modifiers": {"dex": 1}},
    }

    result = hazards.apply_hazard_damage_to_enemy(
        enemy,
        {
            "triggered": True,
            "label": "dart launcher",
            "damage_type": "piercing",
            "rolled_damage": 5,
            "damage": 5,
            "final_damage": 5,
            "save_dc": 12,
            "save_ability": "dex",
            "no_damage_on_save": True,
        },
    )

    assert result["save_success"] is True
    assert result["damage_after_save"] == 0
    assert result["damage"] == 0
    assert enemy["hp_current"] == 7
