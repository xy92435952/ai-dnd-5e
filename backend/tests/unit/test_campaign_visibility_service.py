import json

from services.campaign_visibility_service import public_campaign_state, public_game_state, public_log_entry, public_text


def test_public_campaign_state_hides_clues_recent_updates_and_related_refs():
    state = {
        "quest_log": [{
            "quest": "Find the gate",
            "status": "active",
            "related_clues": ["visible-door", "hidden-vault", "Secret vault under moonwell"],
        }],
        "clues": [
            {"id": "visible-door", "text": "Visible moon door", "category": "location"},
            {"id": "hidden-vault", "text": "Secret vault under moonwell", "category": "secret", "hidden": True},
            {"id": "private-oath", "text": "Mara oath is false", "visibility": {"scope": "private"}},
            {"id": "future-watch", "text": "Blacksmith reports to the watch", "revealed": False},
        ],
        "recent_updates": [
            {"type": "quest", "label": "Find the gate", "detail": "visible"},
            {"type": "clue", "clue_id": "visible-door", "label": "Visible moon door", "detail": "location"},
            {"type": "clue", "clue_id": "hidden-vault", "label": "Secret vault under moonwell", "detail": "secret"},
            {"type": "clue", "label": "Blacksmith reports to the watch", "detail": "npc"},
        ],
        "companion_bonds": {
            "ally-1": {
                "name": "Mara",
                "personal_quest": {
                    "title": "Old oath",
                    "related_clues": ["visible-door", "private-oath"],
                },
            },
        },
    }

    public = public_campaign_state(state)
    payload = json.dumps(public, ensure_ascii=False)

    assert [clue["id"] for clue in public["clues"]] == ["visible-door"]
    assert public["quest_log"][0]["related_clues"] == ["visible-door"]
    assert public["companion_bonds"]["ally-1"]["personal_quest"]["related_clues"] == ["visible-door"]
    assert [item["label"] for item in public["recent_updates"]] == ["Find the gate", "Visible moon door"]
    assert "hidden-vault" not in payload
    assert "Secret vault under moonwell" not in payload
    assert "private-oath" not in payload
    assert "Mara oath is false" not in payload
    assert "future-watch" not in payload
    assert "Blacksmith reports to the watch" not in payload


def test_public_campaign_state_keeps_explicit_public_scoped_clue():
    public = public_campaign_state({
        "clues": [{
            "id": "group-note",
            "text": "Shared with the table",
            "visibility": {"scope": "group", "public": True},
        }],
        "recent_updates": [{
            "type": "clue",
            "clue_id": "group-note",
            "label": "Shared with the table",
        }],
    })

    assert public["clues"][0]["id"] == "group-note"
    assert public["recent_updates"][0]["clue_id"] == "group-note"


def test_public_campaign_state_keeps_legacy_uncatalogued_clue_updates():
    public = public_campaign_state({
        "recent_updates": [
            {"type": "clue", "label": "Legacy clue update"},
            {"type": "clue", "label": "Hidden legacy update", "hidden": True},
        ],
    })

    assert [item["label"] for item in public["recent_updates"]] == ["Legacy clue update"]


def test_public_game_state_filters_last_turn_hidden_clue_refs():
    campaign_state = {
        "clues": [
            {"id": "visible-door", "text": "Visible moon door"},
            {"id": "hidden-vault", "text": "Secret vault under moonwell", "hidden": True},
        ],
    }
    game_state = {
        "scene_vibe": {"location": "Well"},
        "last_turn": {
            "player_choices": [
                {
                    "text": "Study the public sigil",
                    "related_clues": ["visible-door", "hidden-vault", "Secret vault under moonwell"],
                },
                {
                    "text": "Open the secret vault",
                    "related_clues": ["hidden-vault"],
                    "hidden": True,
                },
                {
                    "text": "Secret vault under moonwell",
                    "skill_check": False,
                },
            ],
            "needs_check": {
                "required": True,
                "context": "Secret vault under moonwell",
                "related_clues": ["visible-door", "hidden-vault"],
            },
        },
    }

    public = public_game_state(game_state, campaign_state)

    assert public["scene_vibe"]["location"] == "Well"
    assert public["last_turn"]["player_choices"] == [{
        "text": "Study the public sigil",
        "related_clues": ["visible-door"],
    }]
    assert "context" not in public["last_turn"]["needs_check"]
    assert public["last_turn"]["needs_check"]["related_clues"] == ["visible-door"]


def test_public_game_state_filters_explicit_hidden_last_turn_without_clue_catalog():
    public = public_game_state(
        {
            "last_turn": {
                "player_choices": [
                    {"text": "Public fallback choice"},
                    {"text": "Hidden fallback choice", "private": True},
                ],
            },
        },
        None,
    )

    assert public["last_turn"]["player_choices"] == [{"text": "Public fallback choice"}]


def test_public_log_entry_redacts_hidden_clue_texts():
    campaign_state = {
        "clues": [
            {"id": "visible-door", "text": "Visible moon door"},
            {"id": "hidden-vault", "text": "Secret vault under moonwell", "hidden": True},
        ],
    }
    public = public_log_entry(
        {
            "role": "dm",
            "content": "Secret vault under moonwell is still behind hidden-vault.",
            "dice_result": {"label": "Secret vault under moonwell"},
            "table_decision": {"note": "hidden-vault"},
        },
        campaign_state,
    )

    assert public["content"] == "[hidden] is still behind [hidden]."
    assert public["dice_result"]["label"] == "[hidden]"
    assert public["table_decision"]["note"] == "[hidden]"


def test_public_log_entry_redacts_other_character_ready_action_declaration():
    public = public_log_entry(
        {
            "role": "player",
            "content": "Ready Hero readies: When the guest crosses the hidden sigil, strike.",
            "dice_result": {
                "type": "ready_action_declared",
                "ready_action": {
                    "type": "ready_action",
                    "actor_id": "host-char",
                    "actor_name": "Ready Hero",
                    "target_id": "guest-char",
                    "target_name": "Guest",
                    "action_type": "spell",
                    "spell_name": "Magic Missile",
                    "condition_text": "When the guest crosses the hidden sigil, strike.",
                    "slot_key": "1st",
                    "slots_remaining": 0,
                },
            },
        },
        None,
        viewer_character_id="guest-char",
    )

    assert public["content"] == "Ready Hero readies an action."
    assert public["dice_result"] == {
        "type": "ready_action_declared",
        "ready_action": {
            "type": "ready_action",
            "redacted": True,
            "visibility": "other_character",
            "actor_id": "host-char",
            "actor_name": "Ready Hero",
        },
    }
    assert "hidden sigil" not in json.dumps(public)
    assert "guest-char" not in json.dumps(public)
    assert "Magic Missile" not in json.dumps(public)


def test_public_log_entry_keeps_own_ready_action_declaration():
    public = public_log_entry(
        {
            "role": "player",
            "content": "Ready Hero readies: When the guest crosses the hidden sigil, strike.",
            "dice_result": {
                "type": "ready_action_declared",
                "ready_action": {
                    "type": "ready_action",
                    "actor_id": "host-char",
                    "actor_name": "Ready Hero",
                    "target_id": "guest-char",
                    "condition_text": "When the guest crosses the hidden sigil, strike.",
                },
            },
        },
        None,
        viewer_character_id="host-char",
    )

    assert public["dice_result"]["ready_action"]["target_id"] == "guest-char"
    assert public["dice_result"]["ready_action"]["condition_text"] == "When the guest crosses the hidden sigil, strike."


def test_public_log_entry_redacts_other_character_enemy_inspect_details():
    public = public_log_entry(
        {
            "role": "system",
            "content": "[Inspect] Scout inspected Private Stalker: 19 vs DC 12 (success)",
            "dice_result": {
                "type": "enemy_inspect",
                "actor_id": "scout-char",
                "actor_name": "Scout",
                "target_id": "enemy-1",
                "target_name": "Private Stalker",
                "skill": "investigation",
                "dc": 12,
                "check": {"d20": 18, "modifier": 1, "total": 19, "success": True},
                "success": True,
                "revealed_stats": ["actions", "resistances"],
                "enemy": {
                    "id": "enemy-1",
                    "name": "Private Stalker",
                    "actions": [{"name": "Shadow Strike"}],
                    "resistances": ["necrotic"],
                },
            },
        },
        None,
        viewer_character_id="guest-char",
    )

    assert public["dice_result"] == {
        "type": "enemy_inspect",
        "redacted": True,
        "visibility": "other_character",
        "actor_id": "scout-char",
        "actor_name": "Scout",
        "target_id": "enemy-1",
        "target_name": "Private Stalker",
        "skill": "investigation",
        "dc": 12,
        "success": True,
        "check": {"d20": 18, "modifier": 1, "total": 19, "success": True},
    }
    assert "Shadow Strike" not in json.dumps(public)
    assert "necrotic" not in json.dumps(public)
    assert "revealed_stats" not in public["dice_result"]
    assert "enemy" not in public["dice_result"]


def test_public_log_entry_keeps_own_enemy_inspect_details():
    public = public_log_entry(
        {
            "role": "system",
            "content": "[Inspect] Scout inspected Private Stalker: 19 vs DC 12 (success)",
            "dice_result": {
                "type": "enemy_inspect",
                "actor_id": "scout-char",
                "target_id": "enemy-1",
                "revealed_stats": ["actions"],
                "enemy": {"actions": [{"name": "Shadow Strike"}]},
            },
        },
        None,
        viewer_character_id="scout-char",
    )

    assert public["dice_result"]["revealed_stats"] == ["actions"]
    assert public["dice_result"]["enemy"]["actions"] == [{"name": "Shadow Strike"}]


def test_public_log_entry_redacts_condition_update_ready_action_failure_for_other_viewer():
    ready_action_failed = {
        "type": "ready_action_failed",
        "actor_id": "host-char",
        "actor_name": "Ready Hero",
        "target_id": "enemy-1",
        "target_name": "Clockwork Sentry",
        "spell_name": "Magic Missile",
        "slot_key": "1st",
        "slot_already_consumed": True,
        "reason": "concentration_lost",
    }
    public = public_log_entry(
        {
            "role": "system",
            "content": "Ready Hero gains condition: paralyzed.",
            "dice_result": {
                "type": "condition_update",
                "condition": "paralyzed",
                "target_id": "host-char",
                "target_name": "Ready Hero",
                "target_state": {
                    "target_id": "host-char",
                    "target_name": "Ready Hero",
                    "conditions": ["paralyzed"],
                    "ready_action_failed": ready_action_failed,
                },
            },
        },
        None,
        viewer_character_id="guest-char",
    )

    redacted = public["dice_result"]["target_state"]["ready_action_failed"]
    assert redacted == {
        "type": "ready_action_failed",
        "redacted": True,
        "visibility": "other_character",
        "actor_id": "host-char",
        "actor_name": "Ready Hero",
    }
    assert "Magic Missile" not in json.dumps(public)
    assert "enemy-1" not in json.dumps(public)
    assert "slot_key" not in json.dumps(public)


def test_public_log_entry_keeps_condition_update_ready_action_failure_for_actor():
    ready_action_failed = {
        "type": "ready_action_failed",
        "actor_id": "host-char",
        "actor_name": "Ready Hero",
        "target_id": "enemy-1",
        "spell_name": "Magic Missile",
        "slot_key": "1st",
        "reason": "concentration_lost",
    }
    public = public_log_entry(
        {
            "role": "system",
            "content": "Ready Hero gains condition: paralyzed.",
            "dice_result": {
                "type": "condition_update",
                "target_id": "host-char",
                "target_name": "Ready Hero",
                "target_state": {
                    "target_id": "host-char",
                    "target_name": "Ready Hero",
                    "conditions": ["paralyzed"],
                    "ready_action_failed": ready_action_failed,
                },
            },
        },
        None,
        viewer_character_id="host-char",
    )

    assert public["dice_result"]["target_state"]["ready_action_failed"]["spell_name"] == "Magic Missile"
    assert public["dice_result"]["target_state"]["ready_action_failed"]["target_id"] == "enemy-1"


def test_public_text_redacts_hidden_clue_texts():
    campaign_state = {
        "clues": [
            {"id": "visible-door", "text": "Visible moon door"},
            {"id": "hidden-vault", "text": "Secret vault under moonwell", "hidden": True},
        ],
    }

    assert public_text(
        "The Secret vault under moonwell is hidden-vault.",
        campaign_state,
    ) == "The [hidden] is [hidden]."
