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
    from api.combat import attack_damage

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


async def test_apply_attack_damage_to_enemy_updates_enemy_hp(db_session):
    from api.combat.attack_damage import apply_attack_damage_to_target

    enemies = [{
        "id": "goblin-1",
        "name": "哥布林",
        "hp_current": 9,
        "derived": {"hp_max": 9},
    }]

    new_hp, conc_log = await apply_attack_damage_to_target(
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
