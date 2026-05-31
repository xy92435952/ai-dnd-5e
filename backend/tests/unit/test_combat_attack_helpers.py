"""
Unit tests for combat attack helper modules.

These helpers keep endpoint files focused while preserving the old combat
contracts used by /action and /attack-roll.
"""
import pytest


async def test_resolve_attack_target_defaults_to_first_alive_enemy(db_session):
    from api.combat.attack_targeting import resolve_attack_target

    enemies = [
        {"id": "dead-goblin", "name": "倒下的哥布林", "hp_current": 0, "derived": {"ac": 12}},
        {"id": "orc-1", "name": "兽人", "hp_current": 9, "derived": {"ac": 13}},
    ]

    target = await resolve_attack_target(db_session, None, enemies, allow_auto_enemy=True)

    assert target.id == "orc-1"
    assert target.name == "兽人"
    assert target.derived == {"ac": 13}
    assert target.is_enemy is True


async def test_resolve_attack_target_loads_character(db_session, sample_character):
    from api.combat.attack_targeting import resolve_attack_target

    target = await resolve_attack_target(db_session, sample_character.id, [], allow_auto_enemy=False)

    assert target.id == sample_character.id
    assert target.name == sample_character.name
    assert target.is_enemy is False
    assert target.derived["ac"] == 16


def test_apply_ranged_close_penalty_respects_crossbow_expert():
    from api.combat.attack_modifiers import apply_ranged_close_penalty

    enemies = [{"id": "goblin-1", "hp_current": 7}]
    positions = {
        "hero-1": {"x": 5, "y": 5},
        "goblin-1": {"x": 6, "y": 5},
    }

    atk_dis, ranged_penalty = apply_ranged_close_penalty(
        atk_dis=False,
        is_ranged=True,
        attacker_id="hero-1",
        enemies=enemies,
        positions=positions,
        attacker_derived={},
    )
    assert atk_dis is True
    assert ranged_penalty is True

    atk_dis, ranged_penalty = apply_ranged_close_penalty(
        atk_dis=False,
        is_ranged=True,
        attacker_id="hero-1",
        enemies=enemies,
        positions=positions,
        attacker_derived={
            "feat_effects": {
                "Crossbow Expert": {"crossbow_expert": True},
            },
        },
    )
    assert atk_dis is False
    assert ranged_penalty is False


def test_choose_feat_power_attack_and_build_deriveds_for_sharpshooter():
    from api.combat.attack_modifiers import (
        build_attack_deriveds,
        choose_feat_power_attack,
    )

    power = choose_feat_power_attack(
        attacker_derived={
            "ranged_attack_bonus": 9,
            "feat_effects": {"Sharpshooter": True},
        },
        target_derived={"ac": 12},
        cover_bonus=2,
        is_ranged=True,
    )

    assert power.active is True
    assert power.hit_penalty == 5
    assert power.bonus_damage == 10

    attacker, target = build_attack_deriveds(
        attacker_derived={"ranged_attack_bonus": 9},
        target_derived={"ac": 12},
        cover_bonus=2,
        is_ranged=True,
        power=power,
    )

    assert attacker["ranged_attack_bonus"] == 4
    assert target["ac"] == 14


def test_calculate_cover_info_explains_sharpshooter_bypass():
    from api.combat.attack_modifiers import calculate_cover_info

    info = calculate_cover_info(
        grid_data={"2_0": "wall"},
        positions={"hero": {"x": 0, "y": 0}, "goblin": {"x": 5, "y": 0}},
        attacker_id="hero",
        target_id="goblin",
        attacker_derived={"feat_effects": {"Sharpshooter": True}},
        is_ranged=True,
    )

    assert info.bonus == 0
    assert info.raw_bonus == 2
    assert info.ignored_by == "Sharpshooter"
    assert info.to_prediction_detail() == {
        "bonus": 0,
        "raw_bonus": 2,
        "ignored_by": "Sharpshooter",
        "cells": [{"cell": "2_0", "terrain": "wall", "weight": 1}],
    }


def test_build_weapon_damage_dice_uses_equipped_weapon_and_offhand_rules(sample_character):
    from api.combat.attack_modifiers import build_weapon_damage_dice

    sample_character.equipment = {
        "weapons": [
            {"name": "匕首", "damage": "1d4", "equipped": False},
            {"name": "长剑", "damage": "1d8", "equipped": True},
        ],
    }
    sample_character.derived = {
        **(sample_character.derived or {}),
        "hit_die": 6,
        "ability_modifiers": {"str": 3, "dex": 2},
    }

    main_hand = build_weapon_damage_dice(sample_character, is_ranged=False, is_offhand=False)
    assert main_hand.damage_dice == "1d8+3"
    assert main_hand.hit_die == 6
    assert main_hand.dmg_mod == 3

    offhand = build_weapon_damage_dice(sample_character, is_ranged=False, is_offhand=True)
    assert offhand.damage_dice == "1d8+0"
    assert offhand.dmg_mod == 0
