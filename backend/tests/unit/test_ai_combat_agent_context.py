import pytest


def test_enemy_prompt_includes_available_spells_and_slots():
    from services.ai_combat_agent import _build_enemy_prompt
    from services.ai_combat_agent_context import build_ai_combat_context

    actor = {
        "id": "enemy-mage",
        "name": "Enemy Mage",
        "hp_current": 18,
        "hp_max": 18,
        "ac": 12,
        "speed": 30,
        "actions": [{"name": "Dagger", "type": "melee_attack", "damage_dice": "1d4"}],
        "known_spells": ["Web"],
        "cantrips": ["Fire Bolt"],
        "spell_slots": {"1st": 1},
    }
    context = build_ai_combat_context(
        actor=actor,
        actor_is_enemy=True,
        all_characters=[{
            "id": "hero-1",
            "name": "Hero",
            "hp_current": 20,
            "hp_max": 20,
            "ac": 15,
        }],
        all_enemies=[actor],
        positions={"enemy-mage": {"x": 0, "y": 0}, "hero-1": {"x": 3, "y": 0}},
    )

    prompt = _build_enemy_prompt(
        actor=actor,
        context=context,
        module_difficulty="normal",
        module_tactics="Use control magic when useful.",
    )

    assert "Web" in prompt
    assert "Fire Bolt" in prompt
    assert "1st" in prompt
    assert "Dagger" in prompt


def test_enemy_prompt_allows_special_decisions_for_recharge_actions():
    from services.ai_combat_agent import _build_enemy_prompt
    from services.ai_combat_agent_context import build_ai_combat_context

    actor = {
        "id": "dragon-1",
        "name": "Dragon",
        "hp_current": 60,
        "hp_max": 60,
        "ac": 16,
        "speed": 30,
        "actions": [{
            "name": "Fire Breath",
            "type": "special",
            "recharge": "5-6",
            "damage_dice": "6d6",
        }],
    }
    context = build_ai_combat_context(
        actor=actor,
        actor_is_enemy=True,
        all_characters=[{"id": "hero-1", "name": "Hero", "hp_current": 30, "hp_max": 30}],
        all_enemies=[actor],
        positions={"dragon-1": {"x": 0, "y": 0}, "hero-1": {"x": 3, "y": 0}},
    )

    prompt = _build_enemy_prompt(
        actor=actor,
        context=context,
        module_difficulty="normal",
        module_tactics="Use breath when it is available.",
    )

    assert "Fire Breath" in prompt
    assert "Recharge" in prompt
    assert "special" in prompt


class FakeSession:
    id = "session-1"
    is_multiplayer = False
    player_character_id = None
    game_state = {}


class FakeDb:
    async def get(self, *_args):
        return None


@pytest.mark.asyncio
async def test_ai_turn_context_preserves_enemy_spell_fields():
    from api.combat.ai_turn_context import build_ai_turn_context

    enemy = {
        "id": "enemy-mage",
        "name": "Enemy Mage",
        "hp_current": 18,
        "hp_max": 18,
        "ac": 12,
        "speed": 30,
        "known_spells": ["Web"],
        "prepared_spells": ["Shield"],
        "cantrips": ["Fire Bolt"],
        "spell_slots": {"1st": 1},
        "concentration": "Hex",
        "derived": {"spell_save_dc": 13},
    }

    context = await build_ai_turn_context(
        FakeDb(),
        FakeSession(),
        combat=None,
        actor_id="enemy-mage",
        actor_name="Enemy Mage",
        enemies=[enemy],
    )

    actor_full = context["actor_full"]
    assert actor_full["known_spells"] == ["Web"]
    assert actor_full["prepared_spells"] == ["Shield"]
    assert actor_full["cantrips"] == ["Fire Bolt"]
    assert actor_full["spell_slots"] == {"1st": 1}
    assert actor_full["concentration"] == "Hex"


def test_ai_decision_target_validation_accepts_special_action():
    from services.ai_combat_agent_parser import ensure_valid_ai_decision_targets

    decision, replaced = ensure_valid_ai_decision_targets(
        decision={"action_type": "special", "target_id": None},
        targets_alive=[{"id": "hero-1", "hp_current": 30}],
        all_characters=[{"id": "hero-1", "hp_current": 30}],
    )

    assert replaced is False
    assert decision["target_id"] == "hero-1"
