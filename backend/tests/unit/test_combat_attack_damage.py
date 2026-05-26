"""
Unit tests for two-step attack damage helpers.
"""


def test_find_pending_attack_returns_owner_and_pending():
    from api.combat.attack_damage import find_pending_attack

    owner, pending = find_pending_attack({
        "hero-1": {
            "pending_attack": {"pending_attack_id": "pa-1", "hit": True},
        },
        "hero-2": {
            "pending_attack": {"pending_attack_id": "pa-2", "hit": True},
        },
    }, "pa-2")

    assert owner == "hero-2"
    assert pending == {"pending_attack_id": "pa-2", "hit": True}


def test_roll_pending_damage_applies_frontend_values_and_crit(monkeypatch):
    from services import combat_damage_bonus_service as attack_damage

    rolls = iter([
        {"total": 7, "rolls": [4, 3]},
        {"total": 5, "rolls": [5]},
    ])
    monkeypatch.setattr(attack_damage, "roll_dice", lambda expr: next(rolls))

    result = attack_damage.roll_pending_damage(
        hit_die=8,
        dmg_mod=3,
        is_crit=True,
        damage_values=[2, 6],
    )

    assert result.damage_dice_expr == "1d8+3"
    assert result.damage_rolls == [2, 6]
    assert result.damage_roll_result["total"] == 11
    assert result.crit_extra == 5
    assert result.damage == 16


def test_apply_basic_damage_bonuses_collects_notes():
    from api.combat.attack_damage import apply_basic_damage_bonuses

    total, notes, dueling_bonus, rage_bonus, feat_bonus = apply_basic_damage_bonuses(
        base_damage=10,
        pending={
            "feat_power_attack": True,
            "feat_power_bonus_dmg": 10,
            "is_raging": True,
        },
        attacker_derived={"melee_damage_bonus": 2},
        level=5,
        is_ranged=False,
        get_rage_bonus=lambda level: 2,
    )

    assert total == 24
    assert notes == ["巨武器大师+10", "决斗+2", "狂暴+2"]
    assert dueling_bonus == 2
    assert rage_bonus == 2
    assert feat_bonus == 10


def test_apply_divine_fury_adds_once_on_first_raging_hit(monkeypatch):
    from services import combat_damage_bonus_service as attack_damage

    monkeypatch.setattr(attack_damage, "roll_dice", lambda expr: {"total": 5, "rolls": [3, 2]})

    result = attack_damage.apply_divine_fury(
        damage=10,
        extra_damage_notes=["狂暴+2"],
        pending={"is_raging": True},
        subclass_effects={"divine_fury": True},
        level=5,
        turn_state={"attacks_made": 1},
    )

    assert result.damage == 15
    assert result.extra_damage_notes == ["狂暴+2", "神圣狂怒+5"]


def test_apply_sneak_attack_uses_advantage_on_first_rogue_attack(monkeypatch):
    from services import combat_damage_bonus_service as attack_damage

    monkeypatch.setattr(attack_damage, "roll_dice", lambda expr: {"total": 7, "rolls": [4, 3]})

    result = attack_damage.apply_sneak_attack(
        damage=10,
        extra_damage_notes=[],
        attacker_class="Rogue",
        level=5,
        pending={"advantage": True},
        subclass_effects={},
        turn_state={"attacks_made": 1},
        target_id="enemy-1",
        attacker_id="rogue-1",
        ally_list=[],
        enemies=[],
        positions={},
        has_ally_adjacent_to=lambda *args: False,
        check_sneak_attack=lambda *args, **kwargs: True,
        calc_sneak_attack_dice=lambda level: 3,
    )

    assert result.damage == 17
    assert result.sneak_attack_applied is True
    assert result.sneak_attack_damage == 7
    assert result.sneak_attack_dice == "3d6"
    assert result.extra_damage_notes == ["偷袭3d6=7"]


def test_apply_target_resistance_uses_enemy_resistance_lists():
    from api.combat.attack_damage import apply_target_resistance

    result = apply_target_resistance(
        damage=12,
        damage_type="fire",
        target_id="enemy-1",
        target_is_enemy=True,
        enemies=[{"id": "enemy-1", "resistances": ["fire"], "immunities": [], "vulnerabilities": []}],
        apply_damage_with_resistance=lambda damage, damage_type, resistances, immunities, vulnerabilities: damage // 2,
    )

    assert result == 6


def test_apply_sustained_damage_effects_adds_hex_only_to_hexed_target(monkeypatch):
    from services import combat_damage_bonus_service as attack_damage

    monkeypatch.setattr(attack_damage, "roll_dice", lambda expr: {"total": 4, "rolls": [4]})

    result = attack_damage.apply_sustained_damage_effects(
        damage=10,
        extra_damage_notes=[],
        attacker_concentration="Hex",
        target_conditions=["hexed"],
        target_id="enemy-1",
        target_is_enemy=True,
        enemies=[{"id": "enemy-1", "resistances": [], "immunities": [], "vulnerabilities": []}],
        weapon_damage_type="piercing",
        apply_damage_with_resistance=lambda damage, *_args: damage,
    )

    assert result.damage == 14
    assert result.extra_damage_notes == ["Hex+4"]


def test_apply_sustained_damage_effects_skips_hex_without_marked_target(monkeypatch):
    from services import combat_damage_bonus_service as attack_damage

    monkeypatch.setattr(attack_damage, "roll_dice", lambda expr: {"total": 4, "rolls": [4]})

    result = attack_damage.apply_sustained_damage_effects(
        damage=10,
        extra_damage_notes=[],
        attacker_concentration="Hex",
        target_conditions=[],
        target_id="enemy-1",
        target_is_enemy=True,
        enemies=[{"id": "enemy-1"}],
        weapon_damage_type="piercing",
        apply_damage_with_resistance=lambda damage, *_args: damage,
    )

    assert result.damage == 10
    assert result.extra_damage_notes == []


def test_apply_sustained_damage_effects_applies_divine_favor_to_any_weapon_hit(monkeypatch):
    from services import combat_damage_bonus_service as attack_damage

    monkeypatch.setattr(attack_damage, "roll_dice", lambda expr: {"total": 3, "rolls": [3]})

    result = attack_damage.apply_sustained_damage_effects(
        damage=10,
        extra_damage_notes=[],
        attacker_concentration="Divine Favor",
        target_conditions=[],
        target_id="enemy-1",
        target_is_enemy=True,
        enemies=[{"id": "enemy-1", "resistances": [], "immunities": [], "vulnerabilities": []}],
        weapon_damage_type="piercing",
        apply_damage_with_resistance=lambda damage, damage_type, *_args: damage if damage_type == "radiant" else 0,
    )

    assert result.damage == 13
    assert result.extra_damage_notes == ["Divine Favor+3"]


def test_resolve_damage_extras_combines_sneak_attack_and_resistance(monkeypatch):
    from services import combat_damage_bonus_service as attack_damage

    monkeypatch.setattr(attack_damage, "roll_dice", lambda expr: {"total": 6, "rolls": [3, 3]})

    result = attack_damage.resolve_damage_extras(
        damage=12,
        extra_damage_notes=[],
        pending={"advantage": True, "is_raging": False},
        attacker_class="Rogue",
        level=5,
        subclass_effects={},
        turn_state={"attacks_made": 1},
        target_id="enemy-1",
        attacker_id="rogue-1",
        target_is_enemy=True,
        ally_list=[],
        enemies=[{"id": "enemy-1", "resistances": ["piercing"], "immunities": [], "vulnerabilities": []}],
        positions={},
        damage_type="piercing",
        attacker_concentration=None,
        target_conditions=[],
        has_ally_adjacent_to=lambda *args: False,
        check_sneak_attack=lambda *args, **kwargs: True,
        calc_sneak_attack_dice=lambda level: 3,
        apply_damage_with_resistance=lambda damage, *_args: damage // 2,
    )

    assert result.damage == 9
    assert result.sneak_attack_applied is True
    assert result.sneak_attack_damage == 6
    assert result.extra_damage_notes == ["偷袭3d6=6"]


async def test_apply_attack_damage_to_enemy_updates_enemy_hp(db_session):
    from api.combat.attack_damage import apply_attack_damage_to_target

    enemies = [{
        "id": "goblin-1",
        "name": "哥布林",
        "hp_current": 9,
        "derived": {"hp_max": 9},
    }]

    new_hp, conc_log, target_state = await apply_attack_damage_to_target(
        db_session,
        session_id="sess-1",
        enemies=enemies,
        target_id="goblin-1",
        target_is_enemy=True,
        damage=6,
    )

    assert new_hp == 3
    assert enemies[0]["hp_current"] == 3
    assert conc_log is None
    assert target_state == {
        "target_id": "goblin-1",
        "hp_current": 3,
        "new_hp": 3,
        "conditions": [],
        "life_state": "alive",
    }


async def test_apply_attack_damage_to_zero_hp_character_adds_critical_death_save_failures(
    db_session,
    sample_character,
):
    from api.combat.attack_damage import apply_attack_damage_to_target

    sample_character.hp_current = 0
    sample_character.death_saves = {"successes": 0, "failures": 1, "stable": False}
    sample_character.conditions = ["unconscious"]
    await db_session.commit()

    new_hp, conc_log, target_state = await apply_attack_damage_to_target(
        db_session,
        session_id="sess-1",
        enemies=[],
        target_id=sample_character.id,
        target_is_enemy=False,
        damage=4,
        is_critical=True,
    )

    assert new_hp == 0
    assert sample_character.death_saves == {"successes": 0, "failures": 3, "stable": False}
    assert conc_log is None
    assert target_state == {
        "target_id": sample_character.id,
        "hp_current": 0,
        "new_hp": 0,
        "death_saves": {"successes": 0, "failures": 3, "stable": False},
        "conditions": ["unconscious"],
        "life_state": "dead",
        "concentration": None,
    }


async def test_apply_attack_damage_to_concentrating_character_at_zero_hp_breaks_concentration(
    db_session,
    sample_character,
):
    from api.combat.attack_damage import apply_attack_damage_to_target

    sample_character.hp_current = 3
    sample_character.death_saves = None
    sample_character.conditions = []
    sample_character.concentration = "Bless"
    await db_session.commit()

    new_hp, conc_log, target_state = await apply_attack_damage_to_target(
        db_session,
        session_id="sess-1",
        enemies=[],
        target_id=sample_character.id,
        target_is_enemy=False,
        damage=5,
    )

    assert new_hp == 0
    assert sample_character.concentration is None
    assert conc_log.dice_result["automatic"] is True
    assert conc_log.dice_result["reason"] == "incapacitated"
    assert target_state["life_state"] == "dying"
    assert target_state["concentration"] is None


async def test_melee_hit_against_armor_of_agathys_character_retaliates_to_enemy(
    db_session,
    sample_character,
):
    from api.combat.attack_damage import apply_attack_damage_to_target

    enemies = [{
        "id": "wolf-1",
        "name": "Wolf",
        "hp_current": 12,
        "derived": {"hp_max": 12},
    }]
    sample_character.hp_current = 10
    sample_character.class_resources = {
        "temporary_hp": 5,
        "temporary_hp_source": "armor_of_agathys",
        "armor_of_agathys_active": True,
        "armor_of_agathys_damage": 5,
        "armor_of_agathys_spell_level": 1,
    }
    sample_character.conditions = ["armor_of_agathys"]
    sample_character.condition_durations = {"armor_of_agathys": 600}
    await db_session.commit()

    new_hp, conc_log, target_state = await apply_attack_damage_to_target(
        db_session,
        session_id="sess-1",
        enemies=enemies,
        target_id=sample_character.id,
        target_is_enemy=False,
        damage=7,
        attacker_id="wolf-1",
        attacker_is_enemy=True,
        is_melee=True,
    )

    assert new_hp == 8
    assert conc_log is None
    assert enemies[0]["hp_current"] == 7
    assert target_state["damage_result"] == {
        "damage": 7,
        "damage_to_temporary_hp": 5,
        "damage_to_hp": 2,
        "temporary_hp_before": 5,
        "temporary_hp_after": 0,
    }
    assert target_state["retaliation"] == {
        "source": "armor_of_agathys",
        "defender_id": sample_character.id,
        "defender_name": sample_character.name,
        "target_id": "wolf-1",
        "target_name": "Wolf",
        "damage_type": "cold",
        "damage": 5,
        "base_damage": 5,
        "target_new_hp": 7,
    }
    assert "armor_of_agathys" not in sample_character.conditions
    assert "temporary_hp" not in sample_character.class_resources


async def test_ranged_hit_against_armor_of_agathys_character_does_not_retaliate(
    db_session,
    sample_character,
):
    from api.combat.attack_damage import apply_attack_damage_to_target

    enemies = [{
        "id": "archer-1",
        "name": "Archer",
        "hp_current": 12,
        "derived": {"hp_max": 12},
    }]
    sample_character.hp_current = 10
    sample_character.class_resources = {
        "temporary_hp": 5,
        "temporary_hp_source": "armor_of_agathys",
        "armor_of_agathys_active": True,
        "armor_of_agathys_damage": 5,
    }
    sample_character.conditions = ["armor_of_agathys"]
    sample_character.condition_durations = {"armor_of_agathys": 600}
    await db_session.commit()

    _new_hp, _conc_log, target_state = await apply_attack_damage_to_target(
        db_session,
        session_id="sess-1",
        enemies=enemies,
        target_id=sample_character.id,
        target_is_enemy=False,
        damage=3,
        attacker_id="archer-1",
        attacker_is_enemy=True,
        is_melee=False,
    )

    assert enemies[0]["hp_current"] == 12
    assert "retaliation" not in target_state
    assert target_state["temporary_hp"] == 2
    assert sample_character.hp_current == 10


async def test_armor_of_agathys_retaliation_to_wild_shape_character_updates_shape_pool(
    db_session,
    sample_character,
):
    from api.combat.attack_damage import apply_attack_damage_to_target
    from models import Character

    attacker = Character(
        name="Wild Shape Attacker",
        race="Elf",
        char_class="Druid",
        level=2,
        background="Hermit",
        ability_scores={"str": 10, "dex": 14, "con": 12, "int": 10, "wis": 16, "cha": 8},
        derived={"hp_max": 10, "ac": 13},
        hp_current=10,
        is_player=True,
        class_resources={"wild_shape_active": "Wolf", "wild_shape_hp": 7},
    )
    db_session.add(attacker)

    sample_character.hp_current = 10
    sample_character.class_resources = {
        "temporary_hp": 5,
        "temporary_hp_source": "armor_of_agathys",
        "armor_of_agathys_active": True,
        "armor_of_agathys_damage": 5,
    }
    sample_character.conditions = ["armor_of_agathys"]
    sample_character.condition_durations = {"armor_of_agathys": 600}
    await db_session.commit()
    await db_session.refresh(attacker)

    _new_hp, _conc_log, target_state = await apply_attack_damage_to_target(
        db_session,
        session_id="sess-1",
        enemies=[],
        target_id=sample_character.id,
        target_is_enemy=False,
        damage=3,
        attacker_id=attacker.id,
        attacker_is_enemy=False,
        is_melee=True,
    )

    retaliation = target_state["retaliation"]
    assert retaliation["damage"] == 5
    assert retaliation["target_new_hp"] == 10
    assert retaliation["target_state"]["wild_shape_hp"] == 2
    assert attacker.hp_current == 10
    assert attacker.class_resources["wild_shape_hp"] == 2


async def test_attack_damage_to_wild_shape_character_updates_shape_pool(
    db_session,
    sample_character,
):
    from api.combat.attack_damage import apply_attack_damage_to_target

    sample_character.hp_current = 10
    sample_character.class_resources = {"wild_shape_active": "Wolf", "wild_shape_hp": 7}
    await db_session.commit()

    new_hp, conc_log, target_state = await apply_attack_damage_to_target(
        db_session,
        session_id="sess-1",
        enemies=[],
        target_id=sample_character.id,
        target_is_enemy=False,
        damage=12,
        is_melee=False,
    )

    assert new_hp == 5
    assert conc_log is None
    assert target_state["wild_shape_hp"] == 0
    assert target_state["class_resources"] == {}
    assert target_state["damage_result"] == {
        "damage": 12,
        "damage_to_wild_shape_hp": 7,
        "wild_shape_hp_before": 7,
        "wild_shape_hp_after": 0,
        "damage_to_temporary_hp": 0,
        "damage_to_hp": 5,
        "temporary_hp_before": 0,
        "temporary_hp_after": 0,
    }
