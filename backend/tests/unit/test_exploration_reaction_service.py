from models.character import Character
from models.session import Session
from services.exploration_reaction_service import (
    pending_exploration_reaction,
    persist_pending_exploration_reaction,
    resolve_pending_exploration_reaction,
)


def _target(hp=9):
    return Character(
        id="rogue-1",
        name="Scout",
        race="Human",
        char_class="Rogue",
        level=1,
        background="Urchin",
        ability_scores={"dex": 12},
        derived={"hp_max": 9},
        hp_current=hp,
        conditions=[],
        condition_durations={},
        death_saves=None,
        class_resources={},
    )


def _caster():
    return Character(
        id="bard-1",
        name="Lyra",
        race="Human",
        char_class="Bard",
        level=5,
        background="Entertainer",
        ability_scores={"cha": 18},
        derived={"hp_max": 24},
        hp_current=24,
        conditions=[],
        condition_durations={},
        death_saves=None,
        class_resources={},
        known_spells=["Feather Fall"],
        prepared_spells=[],
        spell_slots={"1st": 1},
    )


def _session_with_pending():
    session = Session(
        id="session-1",
        user_id="user-1",
        module_id="module-1",
        game_state={},
    )
    persist_pending_exploration_reaction(
        session,
        {
            "id": "prompt-1",
            "type": "feather_fall",
            "reactor_character_id": "bard-1",
            "reactor_user_id": "user-1",
            "target_character_id": "rogue-1",
            "trap": {
                "id": "pit",
                "name": "Hidden Pit",
                "damage_type": "fall",
                "fall_distance_ft": 30,
            },
            "trap_resolution": {
                "trap_id": "pit",
                "name": "Hidden Pit",
                "target_id": "rogue-1",
                "target_name": "Scout",
                "save_ability": "dex",
                "save_dc": 15,
                "save": {"d20": 5, "modifier": 1, "total": 6, "success": False},
                "saved": False,
                "damage_dice": "2d6",
                "damage_type": "fall",
                "damage_roll": {"rolls": [3, 4], "total": 7},
                "rolled_damage": 7,
                "half_on_save": True,
                "final_damage": 7,
                "conditions_applied": [],
                "mutates_hp": False,
            },
        },
    )
    return session


def test_accepting_pending_feather_fall_spends_slot_and_prevents_saved_trap_damage():
    session = _session_with_pending()
    target = _target()
    caster = _caster()

    result = resolve_pending_exploration_reaction(
        session=session,
        reactor=caster,
        target=target,
        accept=True,
    )

    assert pending_exploration_reaction(session) is None
    assert target.hp_current == 9
    assert caster.spell_slots["1st"] == 0
    assert result["final_damage"] == 0
    assert result["feather_fall"]["damage_prevented"] == 7
    assert result["feather_fall"]["caster_id"] == "bard-1"


def test_declining_pending_feather_fall_applies_saved_trap_damage_without_spending_slot():
    session = _session_with_pending()
    target = _target()
    caster = _caster()

    result = resolve_pending_exploration_reaction(
        session=session,
        reactor=caster,
        target=target,
        accept=False,
    )

    assert pending_exploration_reaction(session) is None
    assert target.hp_current == 2
    assert caster.spell_slots["1st"] == 1
    assert result["final_damage"] == 7
    assert not result.get("feather_fall")
    assert result["reaction_declined"]["reactor_character_id"] == "bard-1"
