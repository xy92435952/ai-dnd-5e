import pytest

from services.combat_service import AttackResult


class FakeDb:
    async def get(self, *_args):
        return None


class FakeSession:
    id = "sess-1"
    player_character_id = "char-1"
    combat_active = True


class FakeCombat:
    def __init__(self):
        self.turn_states = {
            "char-1": {
                "action_used": True,
                "bonus_action_used": False,
            }
        }
        self.entity_positions = {
            "char-1": {"x": 0, "y": 0},
            "goblin-1": {"x": 1, "y": 0},
        }


class FakePlayer:
    derived = {"attack_bonus": 5}
    concentration = None


class FakeCombatService:
    def resolve_melee_attack(self, **kwargs):
        self.last_attack_kwargs = kwargs
        return AttackResult(
            attack_roll={
                "d20": 13,
                "attack_total": 18,
                "target_ac": 12,
                "hit": True,
                "is_crit": False,
                "is_fumble": False,
            },
            damage=4,
            damage_roll={"formula": "1d6", "rolls": [4], "total": 4},
            narration="命中",
        )

    def _build_narration(self, actor_name, target_name, attack_roll, damage):
        return f"{actor_name} 攻击 {target_name}，造成 {damage} 伤害"

    def apply_damage(self, current_hp, damage, _max_hp):
        return max(0, current_hp - damage)

    def apply_damage_with_resistance(self, damage, *_args):
        return damage

    def check_combat_over(self, enemies, _player_hp):
        return not any(enemy.get("hp_current", 0) > 0 for enemy in enemies), "victory"


def save_turn_state(combat, entity_id, turn_state):
    combat.turn_states[str(entity_id)] = turn_state


@pytest.mark.asyncio
async def test_resolve_offhand_attack_damages_enemy_and_spends_bonus_action():
    from services.combat_offhand_attack_service import resolve_offhand_attack

    enemies = [{
        "id": "goblin-1",
        "name": "哥布林",
        "hp_current": 6,
        "derived": {"hp_max": 6, "ac": 12},
    }]
    combat = FakeCombat()
    service = FakeCombatService()

    result = await resolve_offhand_attack(
        FakeDb(),
        session_id="sess-1",
        session=FakeSession(),
        combat=combat,
        player=FakePlayer(),
        player_id="char-1",
        player_name="战士",
        target_id="goblin-1",
        state={"enemies": enemies},
        enemies=enemies,
        combat_service=service,
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
    )

    assert service.last_attack_kwargs["is_offhand"] is True
    assert result.target_id == "goblin-1"
    assert result.target_new_hp == 2
    assert result.turn_state["bonus_action_used"] is True
    assert enemies[0]["hp_current"] == 2


@pytest.mark.asyncio
async def test_resolve_offhand_attack_applies_hex_bonus_damage(monkeypatch):
    from services import combat_damage_bonus_service
    from services.combat_offhand_attack_service import resolve_offhand_attack

    monkeypatch.setattr(combat_damage_bonus_service, "roll_dice", lambda expr: {"formula": expr, "rolls": [3], "total": 3})
    enemies = [{
        "id": "goblin-1",
        "name": "哥布林",
        "hp_current": 10,
        "derived": {"hp_max": 10, "ac": 12},
        "conditions": ["hexed"],
    }]
    player = FakePlayer()
    player.concentration = "Hex"

    result = await resolve_offhand_attack(
        FakeDb(),
        session_id="sess-1",
        session=FakeSession(),
        combat=FakeCombat(),
        player=player,
        player_id="char-1",
        player_name="战士",
        target_id="goblin-1",
        state={"enemies": enemies},
        enemies=enemies,
        combat_service=FakeCombatService(),
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
    )

    assert result.damage == 7
    assert result.extra_damage_notes == ["Hex+3"]
    assert result.target_new_hp == 3
    assert enemies[0]["hp_current"] == 3


@pytest.mark.asyncio
async def test_resolve_offhand_attack_consumes_guiding_bolt_advantage():
    from services.combat_offhand_attack_service import resolve_offhand_attack

    enemies = [{
        "id": "goblin-1",
        "name": "哥布林",
        "hp_current": 10,
        "derived": {"hp_max": 10, "ac": 12},
        "conditions": ["guiding_bolt"],
        "condition_durations": {"guiding_bolt": 1},
    }]
    service = FakeCombatService()

    result = await resolve_offhand_attack(
        FakeDb(),
        session_id="sess-1",
        session=FakeSession(),
        combat=FakeCombat(),
        player=FakePlayer(),
        player_id="char-1",
        player_name="战士",
        target_id="goblin-1",
        state={"enemies": enemies},
        enemies=enemies,
        combat_service=service,
        flag_modified_func=lambda *_args: None,
        save_turn_state_func=save_turn_state,
    )

    assert service.last_attack_kwargs["advantage"] is True
    assert service.last_attack_kwargs["target_conditions"] == []
    assert enemies[0]["conditions"] == []
    assert enemies[0]["condition_durations"] == {}
    assert result.target_new_hp == 6


@pytest.mark.asyncio
async def test_resolve_offhand_attack_requires_main_action_first():
    from services.combat_offhand_attack_service import resolve_offhand_attack
    from services.combat_attack_roll_service import CombatAttackRollError

    combat = FakeCombat()
    combat.turn_states["char-1"]["action_used"] = False

    with pytest.raises(CombatAttackRollError) as exc:
        await resolve_offhand_attack(
            FakeDb(),
            session_id="sess-1",
            session=FakeSession(),
            combat=combat,
            player=FakePlayer(),
            player_id="char-1",
            player_name="战士",
            target_id=None,
            state={"enemies": []},
            enemies=[],
            combat_service=FakeCombatService(),
        )

    assert "副手攻击需要先完成" in exc.value.detail
