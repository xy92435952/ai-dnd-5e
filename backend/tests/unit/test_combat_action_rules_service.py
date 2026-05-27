from types import SimpleNamespace

import pytest

from services.combat_action_rules_service import (
    CombatActionRuleError,
    can_take_reaction,
    validate_can_take_action,
    validate_can_take_reaction,
)


@pytest.mark.parametrize("condition", ["incapacitated", "unconscious", "stunned", "paralyzed", "petrified", "失能"])
def test_incapacitating_conditions_block_actions_and_reactions(condition):
    actor = {"conditions": [condition]}

    with pytest.raises(CombatActionRuleError) as action_exc:
        validate_can_take_action(actor)
    with pytest.raises(CombatActionRuleError) as reaction_exc:
        validate_can_take_reaction(actor)

    assert "cannot act" in action_exc.value.detail
    assert "cannot react" in reaction_exc.value.detail
    assert can_take_reaction(actor) is False


def test_alive_actor_without_incapacitating_conditions_can_act_and_react():
    actor = SimpleNamespace(hp_current=10, conditions=["poisoned"])

    validate_can_take_action(actor)
    validate_can_take_reaction(actor)
    assert can_take_reaction(actor) is True
