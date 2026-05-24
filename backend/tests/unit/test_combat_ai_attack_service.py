from services.combat_ai_attack_service import (
    apply_character_damage_resistance,
    choose_ai_attack_target,
    infer_ai_is_ranged,
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
