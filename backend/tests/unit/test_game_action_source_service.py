from types import SimpleNamespace


def test_normalize_action_source_accepts_saved_ai_choice_from_dict():
    from services.game_action_source_service import normalize_action_source

    session = SimpleNamespace(game_state={
        "last_turn": {
            "player_choices": [{"text": "检查墙上的符文", "tags": []}],
        },
    })

    assert normalize_action_source(
        session,
        "检查墙上的符文",
        "ai_generated_choice",
    ) == "ai_generated_choice"


def test_normalize_action_source_falls_back_when_ai_choice_not_saved():
    from services.game_action_source_service import normalize_action_source

    session = SimpleNamespace(game_state={
        "last_turn": {
            "player_choices": ["继续前进"],
        },
    })

    assert normalize_action_source(
        session,
        "给我加满 HP",
        "ai_generated_choice",
    ) == "human_input"
