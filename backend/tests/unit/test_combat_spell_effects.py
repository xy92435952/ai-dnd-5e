"""Unit tests for spell effect helper modules."""


def test_apply_frontend_dice_override_updates_total_and_base_roll():
    from api.combat.spell_effects import apply_frontend_dice_override

    total, detail = apply_frontend_dice_override(
        value=9,
        dice_detail={"total": 9, "base_roll": {"rolls": [4, 5], "total": 9}},
        damage_values=[2, 6],
        modifier=3,
    )

    assert total == 11
    assert detail["total"] == 11
    assert detail["base_roll"]["rolls"] == [2, 6]
    assert detail["base_roll"]["total"] == 8


async def test_apply_spell_damage_to_enemy_updates_enemy_state(db_session):
    from api.combat.spell_effects import apply_spell_damage_to_target

    enemies = [{
        "id": "goblin-1",
        "name": "Goblin",
        "hp_current": 7,
        "derived": {"hp_max": 7},
    }]

    result, conc_log = await apply_spell_damage_to_target(
        db_session,
        "test-session",
        enemies,
        "goblin-1",
        5,
        save_result={"success": False},
    )

    assert result == {
        "target_id": "goblin-1",
        "target_name": "Goblin",
        "damage": 5,
        "new_hp": 2,
        "save": {"success": False},
    }
    assert enemies[0]["hp_current"] == 2
    assert conc_log is None


async def test_apply_spell_damage_to_character_initializes_death_saves(db_session, sample_character):
    from api.combat.spell_effects import apply_spell_damage_to_target

    sample_character.hp_current = 3
    sample_character.death_saves = None
    await db_session.commit()

    result, _conc_log = await apply_spell_damage_to_target(
        db_session,
        "test-session",
        [],
        sample_character.id,
        5,
    )

    assert result["new_hp"] == 0
    assert result["death_saves"] == {"successes": 0, "failures": 0, "stable": False}
    assert sample_character.death_saves == {"successes": 0, "failures": 0, "stable": False}


async def test_apply_spell_damage_to_zero_hp_character_adds_one_death_save_failure(
    db_session,
    sample_character,
):
    from api.combat.spell_effects import apply_spell_damage_to_target

    sample_character.hp_current = 0
    sample_character.death_saves = {"successes": 1, "failures": 0, "stable": True}
    sample_character.conditions = ["unconscious"]
    await db_session.commit()

    result, _conc_log = await apply_spell_damage_to_target(
        db_session,
        "test-session",
        [],
        sample_character.id,
        4,
    )

    assert result["new_hp"] == 0
    assert result["death_saves"] == {"successes": 1, "failures": 1, "stable": False}
    assert sample_character.death_saves == {"successes": 1, "failures": 1, "stable": False}


async def test_apply_spell_heal_to_character_caps_at_max(db_session, sample_character):
    from api.combat.spell_effects import apply_spell_heal_to_target

    sample_character.hp_current = 5
    await db_session.commit()

    result = await apply_spell_heal_to_target(db_session, sample_character.id, 20)

    assert result["target_id"] == sample_character.id
    assert result["new_hp"] == 12
    assert sample_character.hp_current == 12


async def test_apply_spell_heal_to_character_caps_at_exhaustion_max(db_session, sample_character):
    from api.combat.spell_effects import apply_spell_heal_to_target

    sample_character.hp_current = 4
    sample_character.conditions = ["exhaustion"]
    sample_character.condition_durations = {"exhaustion_level": 4}
    await db_session.commit()

    result = await apply_spell_heal_to_target(db_session, sample_character.id, 20)

    assert result["new_hp"] == 6
    assert sample_character.hp_current == 6


async def test_apply_spell_heal_to_character_revives_and_clears_death_saves(db_session, sample_character):
    from api.combat.spell_effects import apply_spell_heal_to_target

    sample_character.hp_current = 0
    sample_character.death_saves = {"successes": 1, "failures": 2, "stable": False}
    await db_session.commit()

    result = await apply_spell_heal_to_target(db_session, sample_character.id, 7)

    assert result["new_hp"] == 7
    assert result["revived"] is True
    assert result["death_saves"] is None
    assert sample_character.death_saves is None


async def test_apply_resurrection_spell_to_dead_character(db_session, sample_character):
    from services import combat_spell_effect_service as spell_effects

    sample_character.hp_current = 0
    sample_character.death_saves = {"successes": 0, "failures": 3, "stable": False}
    sample_character.conditions = ["unconscious"]
    await db_session.commit()

    result = await spell_effects.apply_resurrection_spell_to_target(
        db_session,
        sample_character.id,
        "Raise Dead",
        {"name_en": "Raise Dead"},
    )

    assert result["resurrected"] is True
    assert result["new_hp"] == 1
    assert result["death_saves"] is None
    assert sample_character.hp_current == 1
    assert sample_character.death_saves is None
    assert sample_character.conditions == []


async def test_apply_resurrection_spell_to_living_character_is_noop(db_session, sample_character):
    from services import combat_spell_effect_service as spell_effects

    sample_character.hp_current = 8
    sample_character.death_saves = None
    await db_session.commit()

    result = await spell_effects.apply_resurrection_spell_to_target(
        db_session,
        sample_character.id,
        "Raise Dead",
        {"name_en": "Raise Dead"},
    )

    assert result["resurrected"] is False
    assert result["reason"] == "target_not_dead"
    assert sample_character.hp_current == 8


def test_resolve_spell_condition_uses_known_mapping_and_fallback():
    from api.combat.spell_effects import resolve_spell_condition
    from services.combat_spell_effect_service import resolve_spell_condition_duration, spell_applies_condition

    assert resolve_spell_condition("Hold Person", {"save": "wis"}) == ("paralyzed", "wis")
    assert resolve_spell_condition("网", {"name_en": "Web", "save": "dex"}) == ("restrained", "dex")
    assert resolve_spell_condition("Unknown Control", {"save": "cha"}) == ("affected", "cha")
    assert resolve_spell_condition_duration("Command", {"desc": "one round"}) == 1
    assert resolve_spell_condition_duration("Faerie Fire", {"desc": "专注1分钟。", "concentration": True}) == 10
    assert resolve_spell_condition_duration("Web", {"desc": "专注1小时。", "concentration": True}) == 600
    assert spell_applies_condition("utility", "Mage Armor", {"name_en": "Mage Armor"}) is False
    assert spell_applies_condition("utility", "网", {"name_en": "Web"}) is True


async def test_apply_control_spell_to_enemy_adds_condition_without_duplicate(db_session):
    from services import combat_spell_effect_service as spell_effects

    enemies = [{
        "id": "goblin-1",
        "name": "Goblin",
        "conditions": ["paralyzed"],
    }]

    result = await spell_effects.apply_control_spell_to_target(
        db_session,
        enemies,
        "goblin-1",
        session_id="sess-1",
        condition_name="paralyzed",
        save_ability="wis",
        spell_save_dc=30,
    )

    assert result["condition_name"] == "paralyzed"
    assert result["save_detail"]["success"] is False
    assert enemies[0]["conditions"] == ["paralyzed"]
    assert "condition_durations" in result["target_state"]


async def test_apply_control_spell_to_enemy_falls_back_to_ability_scores(db_session):
    from services import combat_spell_effect_service as spell_effects

    enemies = [{
        "id": "goblin-1",
        "name": "Goblin",
        "ability_scores": {"wis": 20},
        "conditions": [],
    }]

    result = await spell_effects.apply_control_spell_to_target(
        db_session,
        enemies,
        "goblin-1",
        session_id="sess-1",
        condition_name="paralyzed",
        save_ability="wis",
        spell_save_dc=6,
    )

    assert result["save_detail"]["modifier"] == 5


async def test_apply_control_spell_to_character_uses_saving_throw(db_session, sample_character):
    from services import combat_spell_effect_service as spell_effects

    sample_character.conditions = []
    sample_character.derived = {
        **(sample_character.derived or {}),
        "saving_throws": {"wis": 2},
    }
    await db_session.commit()

    result = await spell_effects.apply_control_spell_to_target(
        db_session,
        [],
        sample_character.id,
        session_id="sess-1",
        condition_name="commanded",
        save_ability="wis",
        spell_save_dc=30,
    )

    assert result["save_detail"]["modifier"] == 2
    assert result["save_detail"]["success"] is False
    assert sample_character.conditions == ["commanded"]


async def test_apply_control_spell_to_character_sets_duration(db_session, sample_character):
    from services import combat_spell_effect_service as spell_effects

    sample_character.conditions = []
    sample_character.condition_durations = {}
    await db_session.commit()

    result = await spell_effects.apply_control_spell_to_target(
        db_session,
        [],
        sample_character.id,
        session_id="sess-1",
        condition_name="commanded",
        save_ability=None,
        spell_save_dc=30,
        duration_rounds=1,
    )

    assert result["applied"] is True
    assert sample_character.conditions == ["commanded"]
    assert sample_character.condition_durations == {"commanded": 1}
    assert result["target_state"]["condition_durations"] == {"commanded": 1}


async def test_apply_control_spell_to_restrained_enemy_rolls_dex_save_with_disadvantage(db_session):
    from services import combat_spell_effect_service as spell_effects

    enemies = [{
        "id": "goblin-1",
        "name": "Goblin",
        "derived": {"ability_modifiers": {"dex": 2}, "saving_throws": {"dex": 2}},
        "conditions": ["restrained"],
    }]

    result = await spell_effects.apply_control_spell_to_target(
        db_session,
        enemies,
        "goblin-1",
        session_id="sess-1",
        condition_name="faerie_fire",
        save_ability="dex",
        spell_save_dc=13,
    )

    assert result["save_detail"]["disadvantage"] is True
    assert result["save_detail"]["condition_disadvantage_reasons"] == ["restrained"]


async def test_apply_control_spell_to_unconscious_enemy_auto_fails_dex_save(db_session):
    from services import combat_spell_effect_service as spell_effects

    enemies = [{
        "id": "goblin-1",
        "name": "Goblin",
        "derived": {"ability_modifiers": {"dex": 20}, "saving_throws": {"dex": 20}},
        "conditions": ["unconscious"],
    }]

    result = await spell_effects.apply_control_spell_to_target(
        db_session,
        enemies,
        "goblin-1",
        session_id="sess-1",
        condition_name="faerie_fire",
        save_ability="dex",
        spell_save_dc=10,
    )

    assert result["save_detail"]["total"] >= 21
    assert result["save_detail"]["success"] is False
    assert result["save_detail"]["auto_fail"] is True
    assert result["save_detail"]["auto_fail_reasons"] == ["unconscious"]
    assert "faerie_fire" in enemies[0]["conditions"]


async def test_apply_control_spell_to_character_breaks_concentration_when_incapacitating(
    db_session,
    sample_character,
):
    from services import combat_spell_effect_service as spell_effects

    sample_character.conditions = []
    sample_character.concentration = "Bless"
    sample_character.derived = {
        **(sample_character.derived or {}),
        "saving_throws": {"wis": -5},
    }
    await db_session.commit()

    result = await spell_effects.apply_control_spell_to_target(
        db_session,
        [],
        sample_character.id,
        session_id="sess-1",
        condition_name="paralyzed",
        save_ability=None,
        spell_save_dc=30,
    )

    assert result["applied"] is True
    assert sample_character.conditions == ["paralyzed"]
    assert sample_character.concentration is None
    assert result["target_state"]["concentration"] is None
    assert result["target_state"]["conditions"] == ["paralyzed"]
    assert result["target_state"]["life_state"] == "alive"
    assert result["concentration_log"].dice_result["automatic"] is True
    assert result["concentration_log"].dice_result["reasons"] == ["paralyzed"]
