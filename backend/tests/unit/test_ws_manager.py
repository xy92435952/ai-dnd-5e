from services.ws_manager import WSManager


def test_ws_manager_stats_counts_rooms_and_connections():
    manager = WSManager()
    ws1 = object()
    ws2 = object()
    ws3 = object()
    manager.rooms = {
        "s1": {ws1, ws2},
        "s2": {ws3},
    }
    manager.user_ws = {
        ("s1", "u1"): ws1,
        ("s1", "u2"): ws2,
        ("s2", "u3"): ws3,
    }
    manager.ws_meta = {
        ws1: ("s1", "u1"),
        ws2: ("s1", "u2"),
        ws3: ("s2", "u3"),
    }

    assert manager.stats() == {
        "rooms": 2,
        "connections": 3,
        "users": 3,
        "room_connections": {
            "s1": 2,
            "s2": 1,
        },
    }
