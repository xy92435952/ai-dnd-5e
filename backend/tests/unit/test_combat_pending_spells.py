def test_build_and_find_pending_spell():
    from api.combat.pending_spells import build_pending_spell, find_pending_spell

    pending = build_pending_spell(
        caster_id="char-1",
        spell_name="魔法飞弹",
        spell_level=1,
        target_ids=["goblin-1"],
        is_cantrip=False,
        is_aoe=False,
        spell_type="damage",
    )

    caster_entity_id, found = find_pending_spell({
        "char-1": {"pending_spell": pending},
        "char-2": {},
    }, pending["pending_spell_id"])

    assert caster_entity_id == "char-1"
    assert found == pending


def test_complete_pending_spell_clears_pending_and_marks_non_cantrip_action():
    from api.combat.pending_spells import complete_pending_spell
    from models import CombatState

    combat = CombatState(
        id="combat-1",
        session_id="session-1",
        turn_states={
            "char-1": {
                "action_used": False,
                "pending_spell": {"pending_spell_id": "pending-1"},
            },
        },
    )

    updated = complete_pending_spell(combat, "char-1", is_cantrip=False)

    assert "pending_spell" not in updated
    assert updated["action_used"] is True
    assert "pending_spell" not in combat.turn_states["char-1"]
