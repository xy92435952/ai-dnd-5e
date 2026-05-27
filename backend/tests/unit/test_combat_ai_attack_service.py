from services.combat_ai_attack_service import (
    apply_character_damage_resistance,
    choose_ai_attack_target,
    infer_ai_is_ranged,
    has_pack_tactics,
    pack_tactics_advantage,
    target_is_dodging,
)


class FakeCombatService:
    def choose_ai_target(self, **_kwargs):
        return {"id": "fallback-1", "name": "备用目标"}


class FakeCharacter:
    def __init__(
        self,
        *,
        char_class="Fighter",
        class_resources=None,
        derived=None,
        conditions=None,
        equipment=None,
    ):
        self.char_class = char_class
        self.class_resources = class_resources or {}
        self.derived = derived or {}
        self.conditions = conditions or []
        self.equipment = equipment or {}


def test_choose_ai_attack_target_prefers_decided_visible_target():
    target = choose_ai_attack_target(
        decided_target_id="enemy-2",
        enemies_alive=[{"id": "enemy-1"}, {"id": "enemy-2", "name": "骷髅"}],
        all_characters=[{"id": "char-1", "name": "队友"}],
        actor_is_enemy=False,
        player=None,
        companions_alive=[],
        combat_service=FakeCombatService(),
    )

    assert target == {"id": "enemy-2", "name": "骷髅"}


def test_choose_ai_attack_target_falls_back_to_combat_service():
    target = choose_ai_attack_target(
        decided_target_id="missing",
        enemies_alive=[],
        all_characters=[],
        actor_is_enemy=True,
        player=FakeCharacter(),
        companions_alive=[],
        combat_service=FakeCombatService(),
    )

    assert target == {"id": "fallback-1", "name": "备用目标"}


def test_enemy_ai_target_fallback_uses_full_party_lowest_hp():
    target = choose_ai_attack_target(
        decided_target_id=None,
        enemies_alive=[],
        all_characters=[
            {"id": "host-char", "name": "Host", "hp_current": 12},
            {"id": "guest-char", "name": "Guest", "hp_current": 5},
        ],
        actor_is_enemy=True,
        player=FakeCharacter(),
        companions_alive=[],
        combat_service=FakeCombatService(),
    )

    assert target == {"id": "guest-char", "name": "Guest", "hp_current": 5}


def test_infer_ai_is_ranged_from_character_equipment_or_enemy_actions():
    archer = FakeCharacter(equipment={"weapons": [{"properties": ["ranged"]}]})
    assert infer_ai_is_ranged(archer=archer, enemies=[], actor_id="ally-1") is True

    enemy_ranged = infer_ai_is_ranged(
        archer=None,
        enemies=[{"id": "enemy-1", "actions": [{"type": "远程武器攻击"}]}],
        actor_id="enemy-1",
    )
    assert enemy_ranged is True


def test_apply_character_damage_resistance_preserves_existing_barbarian_and_fire_rules():
    raging_barbarian = FakeCharacter(
        char_class="Barbarian",
        class_resources={"raging": True},
    )
    assert apply_character_damage_resistance(raging_barbarian, 11, "挥砍") == (5, True)

    fire_resistant = FakeCharacter(conditions=["fire_resistance"])
    assert apply_character_damage_resistance(fire_resistant, 9, "火焰") == (4, True)

    bear_totem = FakeCharacter(
        char_class="Barbarian",
        class_resources={"raging": True},
        derived={"subclass_effects": {"bear_totem": True}},
    )
    assert apply_character_damage_resistance(bear_totem, 9, "psychic") == (9, False)


def test_target_is_dodging_reads_turn_state_and_conditions():
    combat = type("Combat", (), {"turn_states": {"hero-1": {"dodging": True}}})()
    assert target_is_dodging(combat=combat, target_id="hero-1") is True

    condition_target = FakeCharacter(conditions=["dodging"])
    assert target_is_dodging(
        combat=type("Combat", (), {"turn_states": {}})(),
        target_id="hero-2",
        target_character=condition_target,
    ) is True

    assert target_is_dodging(
        combat=type("Combat", (), {"turn_states": {}})(),
        target_id="enemy-1",
        target_data={"conditions": ["poisoned"]},
    ) is False


def test_has_pack_tactics_reads_flag_or_special_ability():
    assert has_pack_tactics({"pack_tactics": True}) is True
    assert has_pack_tactics({"special_abilities": [{"name": "Pack Tactics"}]}) is True
    assert has_pack_tactics({"special_abilities": [{"description": "群体战术：盟友接近时获得优势"}]}) is True
    assert has_pack_tactics({"special_abilities": [{"name": "Keen Smell"}]}) is False


def test_pack_tactics_advantage_requires_adjacent_ally():
    attacker = {"id": "wolf-1", "pack_tactics": True}
    allies = [{"id": "wolf-1", "hp_current": 11}, {"id": "wolf-2", "hp_current": 11}]
    positions = {
        "hero": {"x": 4, "y": 4},
        "wolf-1": {"x": 3, "y": 4},
        "wolf-2": {"x": 5, "y": 4},
    }

    assert pack_tactics_advantage(
        attacker=attacker,
        target_id="hero",
        allies=allies,
        positions=positions,
        has_ally_adjacent_to=lambda target_id, attacker_id, allies, positions: True,
    ) is True
    assert pack_tactics_advantage(
        attacker=attacker,
        target_id="hero",
        allies=allies,
        positions=positions,
        has_ally_adjacent_to=lambda target_id, attacker_id, allies, positions: False,
    ) is False
    assert pack_tactics_advantage(
        attacker={"id": "wolf-1"},
        target_id="hero",
        allies=allies,
        positions=positions,
        has_ally_adjacent_to=lambda *_args: True,
    ) is False
