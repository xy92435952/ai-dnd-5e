def test_find_next_ready_group_id_skips_current_and_chooses_ready_group():
    from services.game_multiplayer_service import find_next_ready_group_id

    room_info = {
        "party_groups": [
            {"id": "alley", "member_user_ids": ["u1", "u2"]},
            {"id": "tavern", "member_user_ids": ["u3"]},
        ],
        "pending_actions_by_group": {
            "alley": [{"text": "撬门"}],
            "tavern": [{"text": "套话"}],
        },
        "group_readiness": {
            "alley": {"u1": "ready", "u2": "ready"},
            "tavern": {"u3": "ready"},
        },
    }

    assert find_next_ready_group_id(room_info, exclude_group_ids={"alley"}) == "tavern"


def test_find_next_ready_group_id_ignores_unready_group():
    from services.game_multiplayer_service import find_next_ready_group_id

    room_info = {
        "party_groups": [{"id": "tavern", "member_user_ids": ["u3", "u4"]}],
        "pending_actions_by_group": {"tavern": [{"text": "套话"}]},
        "group_readiness": {"tavern": {"u3": "ready", "u4": "waiting"}},
    }

    assert find_next_ready_group_id(room_info) is None
