def test_healer_role_overrides_attack_to_heal_wounded_enemy_ally():
    from services.combat_ai_role_decision_service import apply_tactical_role_decision

    actor = {
        "id": "cult-priest",
        "name": "Cult Priest",
        "tactical_role": "healer",
        "known_spells": ["Healing Word"],
        "spell_slots": {"1st": 1},
    }

    decision = apply_tactical_role_decision(
        actor=actor,
        decision={"action_type": "attack", "target_id": "hero-1", "reason": "fallback"},
        all_characters=[{"id": "hero-1", "name": "Hero", "hp_current": 24, "hp_max": 24}],
        all_enemies=[
            {**actor, "hp_current": 18, "hp_max": 18},
            {"id": "guard-1", "name": "Guard", "hp_current": 4, "hp_max": 18},
        ],
        positions={
            "cult-priest": {"x": 0, "y": 0},
            "guard-1": {"x": 5, "y": 0},
            "hero-1": {"x": 3, "y": 0},
        },
    )

    assert decision["action_type"] == "spell"
    assert decision["action_name"] == "治愈之语"
    assert decision["target_id"] == "guard-1"
    assert decision["spell_level"] == 1
    assert decision["_tactical_role_override"] == "healer"


def test_healer_role_does_not_override_without_reachable_heal():
    from services.combat_ai_role_decision_service import apply_tactical_role_decision

    actor = {
        "id": "cult-priest",
        "name": "Cult Priest",
        "tactical_role": "healer",
        "known_spells": ["Cure Wounds"],
        "spell_slots": {"1st": 1},
    }
    original = {"action_type": "attack", "target_id": "hero-1", "reason": "fallback"}

    decision = apply_tactical_role_decision(
        actor=actor,
        decision=original,
        all_characters=[{"id": "hero-1", "name": "Hero", "hp_current": 24, "hp_max": 24}],
        all_enemies=[
            {**actor, "hp_current": 18, "hp_max": 18},
            {"id": "guard-1", "name": "Guard", "hp_current": 4, "hp_max": 18},
        ],
        positions={
            "cult-priest": {"x": 0, "y": 0},
            "guard-1": {"x": 5, "y": 0},
        },
    )

    assert decision == original


def test_controller_role_prefers_available_control_recharge_ability():
    from services.combat_ai_role_decision_service import apply_tactical_role_decision

    decision = apply_tactical_role_decision(
        actor={
            "id": "spider-queen",
            "name": "Spider Queen",
            "tactical_role": "controller",
            "recharge_abilities": [{
                "id": "web-burst",
                "name": "Web Burst",
                "recharge": "5-6",
                "available": True,
                "damage_dice": "2d6",
                "condition_on_failed_save": "restrained",
            }],
        },
        decision={"action_type": "attack", "target_id": "hero-1", "reason": ""},
        all_characters=[{"id": "hero-1", "name": "Hero", "hp_current": 24, "hp_max": 24}],
        all_enemies=[],
        positions={},
    )

    assert decision["action_type"] == "special"
    assert decision["action_name"] == "Web Burst"
    assert decision["target_id"] == "hero-1"
    assert decision["_tactical_role_override"] == "controller"


def test_controller_role_prefers_control_spell_when_available():
    from services.combat_ai_role_decision_service import apply_tactical_role_decision

    decision = apply_tactical_role_decision(
        actor={
            "id": "enemy-mage",
            "name": "Enemy Mage",
            "tactical_role": "controller",
            "known_spells": ["Web"],
            "spell_slots": {"2nd": 1},
        },
        decision={"action_type": "attack", "target_id": "hero-1", "reason": ""},
        all_characters=[
            {"id": "hero-1", "name": "Hero", "hp_current": 24, "hp_max": 24, "ac": 16},
            {"id": "barbarian-1", "name": "Barbarian", "hp_current": 42, "hp_max": 42, "ac": 13},
        ],
        all_enemies=[],
        positions={},
    )

    assert decision["action_type"] == "spell"
    assert decision["action_name"] == "网"
    assert decision["target_id"] == "barbarian-1"
    assert decision["spell_level"] == 2
    assert decision["_tactical_role_override"] == "controller"


def test_defender_role_can_hold_guard_near_vulnerable_support():
    from services.combat_ai_role_decision_service import apply_tactical_role_decision

    decision = apply_tactical_role_decision(
        actor={
            "id": "shield-guard",
            "name": "Shield Guard",
            "tactical_role": "defender",
            "hp_current": 30,
            "hp_max": 36,
        },
        decision={"action_type": "attack", "target_id": "hero-1", "reason": ""},
        all_characters=[{"id": "hero-1", "name": "Hero", "hp_current": 24, "hp_max": 24}],
        all_enemies=[
            {"id": "shield-guard", "hp_current": 30, "hp_max": 36, "tactical_role": "defender"},
            {"id": "enemy-mage", "name": "Enemy Mage", "hp_current": 12, "hp_max": 24, "tactical_role": "controller"},
        ],
        positions={
            "shield-guard": {"x": 3, "y": 3},
            "enemy-mage": {"x": 4, "y": 3},
        },
    )

    assert decision["action_type"] == "dodge"
    assert decision["target_id"] is None
    assert decision["_tactical_role_override"] == "defender"
