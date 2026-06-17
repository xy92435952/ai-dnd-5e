"""
单元测试：schemas/ws_events.py 所有事件类型。

验证：
  - 每种事件都能正常构造、model_dump 出合法 payload
  - type 字段被 Literal 固定，不能随便改
  - WS_EVENT_TYPES 集合与 Union 成员严格一一对应（防止"定义了新类但忘了注册"）
  - ws_manager.broadcast 接受 Pydantic 实例能正确序列化
"""
import json
import pytest
import pytest_asyncio

from schemas.ws_events import (
    WSEvent, WS_EVENT_TYPES,
    MemberJoined, MemberLeft, RoomDissolved, GameStarted,
    AiCompanionsFilled, MemberKicked, HostTransferred, CharacterClaimed,
    MemberOnline, MemberOffline, Typing, WSError,
    DMThinkingStart, DMResponded, DMSpeakTurn, ExplorationReactionPrompt,
    RoomStateUpdated, CombatUpdate, TurnChanged, EntityMoved,
)


ALL_CLASSES = [
    MemberJoined, MemberLeft, RoomDissolved, GameStarted,
    AiCompanionsFilled, MemberKicked, HostTransferred, CharacterClaimed,
    MemberOnline, MemberOffline, Typing, WSError,
    DMThinkingStart, DMResponded, DMSpeakTurn, ExplorationReactionPrompt,
    RoomStateUpdated, CombatUpdate, TurnChanged, EntityMoved,
]


class DummyCombat:
    turn_order = []


class DummySession:
    is_multiplayer = True


class TestEventShape:
    def test_all_classes_have_type_field(self):
        """每个事件类都应定义 `type: Literal[...]`。"""
        for cls in ALL_CLASSES:
            assert "type" in cls.model_fields
            t = cls.model_fields["type"].default
            assert isinstance(t, str) and len(t) > 0

    def test_ws_event_types_matches_union(self):
        """WS_EVENT_TYPES 集合必须与类列表一一对应，避免漏注册。"""
        from_classes = {cls.model_fields["type"].default for cls in ALL_CLASSES}
        assert from_classes == set(WS_EVENT_TYPES)

    def test_model_dump_contains_type_key(self):
        """model_dump 产生的 payload 必须含 type 字段（前端 switch 依赖它）。"""
        e = DMThinkingStart(by_user_id="u1", action_text="试探")
        d = e.model_dump(mode="json")
        assert d["type"] == "dm_thinking_start"
        assert d["by_user_id"] == "u1"
        assert d["action_text"] == "试探"


class TestSampleEvents:
    """给关键事件各写一个构造样例，确保必填字段都没遗漏。"""

    def test_member_joined(self):
        e = MemberJoined(user_id="u1", members=[{"user_id": "u1"}])
        assert e.type == "member_joined"

    def test_member_left_optional_host(self):
        """host_transferred_to 是 Optional。"""
        e = MemberLeft(user_id="u1", members=[])
        assert e.host_transferred_to is None

    def test_member_online_offline_can_carry_member_snapshots(self):
        """在线/离线事件可直接携带成员快照，前端不用再额外拉房间。"""
        members = [{"user_id": "u1", "display_name": "A", "is_online": True}]
        online = MemberOnline(user_id="u1", members=members)
        offline = MemberOffline(user_id="u1", members=members)
        assert online.model_dump(mode="json")["members"] == members
        assert offline.model_dump(mode="json")["members"] == members

    def test_dm_responded_defaults(self):
        """companion_reactions / dice_display 等有合理默认值。"""
        e = DMResponded(
            by_user_id="u1",
            action_type="exploration",
            narrative="你推开门",
        )
        assert e.companion_reactions == ""
        assert e.dice_display == []
        assert e.combat_triggered is False
        assert e.combat_ended is False
        assert e.visibility == {}

    def test_dm_responded_can_carry_visibility(self):
        """多人分队私密回应可携带可见范围。"""
        visibility = {"scope": "group", "group_id": "alley", "visible_to_user_ids": ["u1", "u2"]}
        table_decision = {"decision": "switch_focus", "target_group_id": "alley"}
        e = DMResponded(
            by_user_id="u1",
            action_type="multiplayer_table",
            narrative="镜头转向后巷组。",
            visibility=visibility,
            table_decision=table_decision,
        )
        assert e.model_dump(mode="json")["visibility"] == visibility
        assert e.model_dump(mode="json")["table_decision"] == table_decision

    def test_dm_speak_turn_auto_default_false(self):
        """auto 默认 False（玩家手动推进）；自动推进时调用方显式传 True。"""
        e = DMSpeakTurn(user_id="u1")
        assert e.auto is False

    def test_ws_error_shape(self):
        e = WSError(code="not_current_speaker", message="Only current speaker")
        d = e.model_dump(mode="json")
        assert d["type"] == "error"
        assert d["code"] == "not_current_speaker"
        assert d["message"] == "Only current speaker"

    def test_room_state_updated_carries_full_room_snapshot(self):
        """房间协作状态变化时可广播完整 room 快照，前端直接合并。"""
        e = RoomStateUpdated(room={"session_id": "s1", "party_groups": []})
        d = e.model_dump(mode="json")
        assert d["type"] == "room_state_updated"
        assert d["room"]["session_id"] == "s1"

    def test_exploration_reaction_prompt_carries_private_prompt(self):
        prompt = {
            "type": "feather_fall",
            "reactor_character_id": "bard-1",
            "reactor_user_id": "user-2",
            "options": [{"type": "feather_fall"}],
        }
        e = ExplorationReactionPrompt(prompt=prompt)
        d = e.model_dump(mode="json")

        assert d["type"] == "exploration_reaction_prompt"
        assert d["prompt"] == prompt

    def test_combat_update_carries_reaction_and_control_payloads(self):
        reaction_prompt = {
            "trigger": "incoming_attack",
            "reactor_character_id": "hero-1",
            "options": [{"type": "shield"}],
        }
        lair_prompt = {
            "trigger": "lair_action",
            "actions": [{"id": "pulse"}],
        }
        legendary_action = {
            "type": "legendary_action",
            "actor_id": "dragon-1",
            "action_id": "tail",
        }

        event = CombatUpdate(
            combat={"current_turn_index": 0},
            player_can_react=True,
            reaction_prompt=reaction_prompt,
            reaction_type="shield",
            reaction_effect={"damage_prevented": 5, "hp_restored": 5},
            target_state={"target_id": "hero-1", "target_name": "Smoke Sentinel", "hp_after": 9},
            lair_action_prompt=lair_prompt,
            legendary_action_prompt=None,
            legendary_action=legendary_action,
        )
        data = event.model_dump(mode="json")

        assert data["type"] == "combat_update"
        assert data["player_can_react"] is True
        assert data["reaction_prompt"] == reaction_prompt
        assert data["reaction_type"] == "shield"
        assert data["reaction_effect"] == {"damage_prevented": 5, "hp_restored": 5}
        assert data["target_state"] == {"target_id": "hero-1", "target_name": "Smoke Sentinel", "hp_after": 9}
        assert data["lair_action_prompt"] == lair_prompt
        assert data["legendary_action_prompt"] is None
        assert data["legendary_action"] == legendary_action

    def test_reaction_prompt_projection_keeps_prompt_only_for_reactor(self):
        from api.combat._shared import _project_combat_event_for_viewer

        payload = {
            "type": "combat_update",
            "player_can_react": True,
            "reaction_prompt": {
                "trigger": "incoming_attack",
                "reactor_character_id": "guest-char",
                "options": [{"type": "shield", "character_id": "guest-char"}],
            },
        }

        own = _project_combat_event_for_viewer(payload, viewer_character_id="guest-char")
        other = _project_combat_event_for_viewer(payload, viewer_character_id="host-char")

        assert own["player_can_react"] is True
        assert own["reaction_prompt"]["reactor_character_id"] == "guest-char"
        assert other["player_can_react"] is False
        assert other["reaction_prompt"] is None

    def test_condition_update_projection_redacts_nested_ready_action_failure_for_other_viewer(self):
        from api.combat._shared import _project_combat_event_for_viewer

        ready_action_failed = {
            "type": "ready_action_failed",
            "actor_id": "host-char",
            "actor_name": "Ready Hero",
            "target_id": "enemy-1",
            "target_name": "Clockwork Sentry",
            "spell_name": "Magic Missile",
            "slot_key": "1st",
            "reason": "concentration_lost",
        }
        dice_result = {
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
        }

        projected = _project_combat_event_for_viewer(
            {
                "type": "combat_update",
                "actor_id": "host-char",
                "actor_name": "Ready Hero",
                "action": "condition_add",
                "target_id": "host-char",
                "target_name": "Ready Hero",
                "target_state": dice_result["target_state"],
                "dice_result": dice_result,
                "special_action": dice_result,
            },
            viewer_character_id="guest-char",
        )

        redacted = {
            "type": "ready_action_failed",
            "redacted": True,
            "visibility": "other_character",
            "actor_id": "host-char",
            "actor_name": "Ready Hero",
        }
        assert projected["target_state"]["ready_action_failed"] == redacted
        assert projected["dice_result"]["target_state"]["ready_action_failed"] == redacted
        assert projected["special_action"] == projected["dice_result"]
        assert "Magic Missile" not in json.dumps(projected)
        assert "enemy-1" not in json.dumps(projected)

    def test_condition_update_projection_keeps_nested_ready_action_failure_for_actor(self):
        from api.combat._shared import _project_combat_event_for_viewer

        ready_action_failed = {
            "type": "ready_action_failed",
            "actor_id": "host-char",
            "actor_name": "Ready Hero",
            "target_id": "enemy-1",
            "spell_name": "Magic Missile",
            "reason": "concentration_lost",
        }
        target_state = {
            "target_id": "host-char",
            "target_name": "Ready Hero",
            "conditions": ["paralyzed"],
            "ready_action_failed": ready_action_failed,
        }
        dice_result = {
            "type": "condition_update",
            "target_id": "host-char",
            "target_name": "Ready Hero",
            "target_state": target_state,
        }

        projected = _project_combat_event_for_viewer(
            {
                "type": "combat_update",
                "actor_id": "host-char",
                "action": "condition_add",
                "target_id": "host-char",
                "target_state": target_state,
                "dice_result": dice_result,
                "special_action": dice_result,
            },
            viewer_character_id="host-char",
        )

        assert projected["target_state"]["ready_action_failed"]["spell_name"] == "Magic Missile"
        assert projected["dice_result"]["target_state"]["ready_action_failed"]["target_id"] == "enemy-1"

    def test_ready_action_result_projection_redacts_trigger_details_for_other_viewer(self):
        from api.combat._shared import _project_combat_event_for_viewer

        ready_result = {
            "type": "ready_action",
            "action_type": "spell",
            "applied": True,
            "trigger": "target_moves",
            "trigger_match": "leaves_reach",
            "condition_text": "When the guest crosses the hidden sigil, cast Magic Missile.",
            "actor_id": "host-char",
            "actor_name": "Ready Hero",
            "target_id": "guest-char",
            "target_name": "Guest",
            "spell_name": "Magic Missile",
            "damage": 8,
            "slot_already_consumed": True,
            "slot_key": "1st",
            "slots_remaining": 0,
            "movement_stop": {"applied": True, "to": {"x": 4, "y": 5}},
            "turn_state": {
                "reaction_used": True,
                "ready_action_resolved": {
                    "trigger": "target_moves",
                    "trigger_match": "leaves_reach",
                    "condition_text": "When the guest crosses the hidden sigil, cast Magic Missile.",
                    "slot_key": "1st",
                    "damage": 8,
                },
                "ready_action_failed": {
                    "type": "ready_action_failed",
                    "actor_id": "host-char",
                    "actor_name": "Ready Hero",
                    "target_id": "guest-char",
                    "condition_text": "When the guest crosses the hidden sigil, cast Magic Missile.",
                },
            },
        }

        projected = _project_combat_event_for_viewer(
            {
                "type": "entity_moved",
                "entity_id": "guest-char",
                "position": {"x": 4, "y": 5},
                "ready_action_results": [ready_result],
            },
            viewer_character_id="guest-char",
        )

        result = projected["ready_action_results"][0]
        assert result["actor_id"] == "host-char"
        assert result["actor_name"] == "Ready Hero"
        assert result["spell_name"] == "Magic Missile"
        assert result["damage"] == 8
        assert result["movement_stop"] == {"applied": True, "to": {"x": 4, "y": 5}}
        assert result["turn_state"]["ready_action_resolved"]["damage"] == 8
        assert result["turn_state"]["ready_action_failed"] == {
            "type": "ready_action_failed",
            "redacted": True,
            "visibility": "other_character",
            "actor_id": "host-char",
            "actor_name": "Ready Hero",
        }
        payload = json.dumps(result)
        assert "hidden sigil" not in payload
        assert "condition_text" not in payload
        assert "trigger_match" not in payload
        assert "slot_key" not in payload
        assert "slots_remaining" not in payload

    def test_ready_action_result_projection_keeps_trigger_details_for_actor(self):
        from api.combat._shared import _project_combat_event_for_viewer

        ready_result = {
            "type": "ready_action",
            "action_type": "spell",
            "applied": True,
            "trigger": "target_moves",
            "trigger_match": "leaves_reach",
            "condition_text": "When the guest crosses the hidden sigil, cast Magic Missile.",
            "actor_id": "host-char",
            "actor_name": "Ready Hero",
            "target_id": "guest-char",
            "spell_name": "Magic Missile",
            "slot_already_consumed": True,
            "slot_key": "1st",
            "slots_remaining": 0,
            "turn_state": {
                "ready_action_resolved": {
                    "condition_text": "When the guest crosses the hidden sigil, cast Magic Missile.",
                    "slot_key": "1st",
                },
            },
        }

        projected = _project_combat_event_for_viewer(
            {
                "type": "entity_moved",
                "entity_id": "guest-char",
                "position": {"x": 4, "y": 5},
                "ready_action_results": [ready_result],
            },
            viewer_character_id="host-char",
        )

        result = projected["ready_action_results"][0]
        assert result["condition_text"] == "When the guest crosses the hidden sigil, cast Magic Missile."
        assert result["trigger_match"] == "leaves_reach"
        assert result["slot_key"] == "1st"
        assert result["turn_state"]["ready_action_resolved"]["condition_text"] == "When the guest crosses the hidden sigil, cast Magic Missile."

    def test_turn_state_projection_redacts_ready_action_resolved_for_other_viewer(self):
        from api.combat._shared import _project_turn_states_for_viewer

        turn_states = {
            "host-char": {
                "reaction_used": True,
                "ready_action_resolved": {
                    "trigger": "target_moves",
                    "trigger_match": "leaves_reach",
                    "condition_text": "When the guest crosses the hidden sigil, cast Magic Missile.",
                    "slot_already_consumed": True,
                    "slot_key": "1st",
                    "slots_remaining": 0,
                    "spell_name": "Magic Missile",
                    "damage": 8,
                },
            },
        }

        projected = _project_turn_states_for_viewer(turn_states, viewer_character_id="guest-char")
        resolved = projected["host-char"]["ready_action_resolved"]
        assert resolved == {
            "spell_name": "Magic Missile",
            "damage": 8,
        }
        assert "hidden sigil" not in json.dumps(projected)

        own = _project_turn_states_for_viewer(turn_states, viewer_character_id="host-char")
        assert own["host-char"]["ready_action_resolved"]["condition_text"] == "When the guest crosses the hidden sigil, cast Magic Missile."
        assert own["host-char"]["ready_action_resolved"]["slot_key"] == "1st"

    def test_combat_update_carries_ai_turn_action_payload(self):
        attack_result = {
            "d20": 16,
            "attack_total": 21,
            "target_ac": 14,
            "hit": True,
        }
        target_state = {
            "target_id": "hero-1",
            "target_name": "Smoke Sentinel",
            "hp_after": 9,
        }
        tactical_decision = {
            "role": "striker",
            "reason": "focus wounded hero",
        }

        event = CombatUpdate(
            actor_id="enemy-1",
            actor_name="Goblin Guard",
            narration="Goblin Guard slashes Smoke Sentinel.",
            next_turn_index=1,
            round_number=2,
            target_id="hero-1",
            target_name="Smoke Sentinel",
            target_new_hp=9,
            target_state=target_state,
            player_targeted=True,
            attack_result=attack_result,
            damage=5,
            total_damage=5,
            damage_roll={"notation": "1d6+2", "rolls": [3], "total": 5},
            damage_type="piercing",
            damage_before_resistance=10,
            damage_after_resistance=5,
            resistance_applied=True,
            resistance_sources=["piercing"],
            crit_extra=0,
            sneak_attack=False,
            sneak_attack_damage=0,
            extra_damage_notes=["target resisted piercing"],
            defender_interception={"defender_name": "Shield Guard"},
            weapon_resource={"weapon": "Shortbow", "ammo_remaining": 0},
            tactical_decision=tactical_decision,
        )
        data = event.model_dump(mode="json")

        assert data["type"] == "combat_update"
        assert data["actor_id"] == "enemy-1"
        assert data["actor_name"] == "Goblin Guard"
        assert data["narration"] == "Goblin Guard slashes Smoke Sentinel."
        assert data["next_turn_index"] == 1
        assert data["round_number"] == 2
        assert data["target_id"] == "hero-1"
        assert data["target_name"] == "Smoke Sentinel"
        assert data["target_new_hp"] == 9
        assert data["target_state"] == target_state
        assert data["player_targeted"] is True
        assert data["attack_result"] == attack_result
        assert data["damage"] == 5
        assert data["total_damage"] == 5
        assert data["damage_roll"] == {"notation": "1d6+2", "rolls": [3], "total": 5}
        assert data["damage_type"] == "piercing"
        assert data["damage_before_resistance"] == 10
        assert data["damage_after_resistance"] == 5
        assert data["resistance_applied"] is True
        assert data["resistance_sources"] == ["piercing"]
        assert data["crit_extra"] == 0
        assert data["sneak_attack"] is False
        assert data["sneak_attack_damage"] == 0
        assert data["extra_damage_notes"] == ["target resisted piercing"]
        assert data["defender_interception"] == {"defender_name": "Shield Guard"}
        assert data["weapon_resource"] == {"weapon": "Shortbow", "ammo_remaining": 0}
        assert data["tactical_decision"] == tactical_decision

    def test_combat_update_carries_spell_confirm_payload(self):
        spell_result = {
            "dice": {"notation": "3d4+3", "rolls": [1, 2, 3], "total": 9},
            "damage": 9,
            "heal": 0,
            "target_state": {"target_id": "enemy-1", "hp_after": 2},
            "caster_state": {"target_id": "caster-1", "concentration": "Bless"},
        }
        concentration_update = {
            "caster_id": "caster-1",
            "spell_name": "Shield of Faith",
            "ended": True,
        }
        resurrection_result = {
            "target_id": "ally-1",
            "hp_after": 1,
            "revived": True,
        }
        wild_magic_check = {"d20": 1, "triggered": True}
        wild_magic_surge = {"roll": 7, "effect": "glows brightly"}

        event = CombatUpdate(
            actor_id="caster-1",
            actor_name="Spell Caster",
            narration="Spell Caster releases a spell.",
            action="spell",
            target_id="enemy-1",
            target_new_hp=2,
            target_state={"target_id": "enemy-1", "hp_after": 2},
            actor_state={"target_id": "caster-1", "concentration": "Bless"},
            caster_state={"target_id": "caster-1", "concentration": "Bless"},
            damage=9,
            heal=0,
            dice_result=spell_result,
            spell_result=spell_result,
            aoe_results=[{"target_id": "enemy-1", "damage": 9}],
            resurrection_results=[resurrection_result],
            concentration_effect_updates=[concentration_update],
            remaining_slots={"1st": 0},
            concentration_check={"spell_name": "Bless", "broke": False},
            concentration_checks=[{"spell_name": "Bless", "broke": False}],
            wild_magic_check=wild_magic_check,
            wild_magic_surge=wild_magic_surge,
        )
        data = event.model_dump(mode="json")

        assert data["type"] == "combat_update"
        assert data["action"] == "spell"
        assert data["actor_state"] == {"target_id": "caster-1", "concentration": "Bless"}
        assert data["caster_state"] == {"target_id": "caster-1", "concentration": "Bless"}
        assert data["damage"] == 9
        assert data["heal"] == 0
        assert data["dice_result"] == spell_result
        assert data["spell_result"] == spell_result
        assert data["aoe_results"] == [{"target_id": "enemy-1", "damage": 9}]
        assert data["resurrection_results"] == [resurrection_result]
        assert data["concentration_effect_updates"] == [concentration_update]
        assert data["remaining_slots"] == {"1st": 0}
        assert data["concentration_check"] == {"spell_name": "Bless", "broke": False}
        assert data["concentration_checks"] == [{"spell_name": "Bless", "broke": False}]
        assert data["wild_magic_check"] == wild_magic_check
        assert data["wild_magic_surge"] == wild_magic_surge

    @pytest.mark.asyncio
    async def test_ai_turn_broadcast_carries_main_action_payload(self, monkeypatch):
        import api.combat.ai_turn as ai_turn_module

        captured = {}

        async def fake_broadcast(session, combat, event, db=None):
            captured["event"] = event

        monkeypatch.setattr(ai_turn_module, "_broadcast_combat", fake_broadcast)
        attack_result = {
            "d20": 16,
            "attack_total": 21,
            "target_ac": 14,
            "hit": True,
        }
        spell_result = {
            "type": "ai_spell",
            "spell_name": "Burning Hands",
            "damage": 8,
        }
        special_action = {
            "name": "Fire Breath",
            "damage_type": "fire",
        }
        target_results = [{
            "target_id": "hero-1",
            "target_name": "Smoke Sentinel",
            "damage": 8,
        }]

        result = await ai_turn_module._broadcast_ai_turn_result(
            DummySession(),
            DummyCombat(),
            object(),
            {
                "actor_id": "enemy-1",
                "actor_name": "Goblin Guard",
                "narration": "Goblin Guard slashes Smoke Sentinel.",
                "next_turn_index": 1,
                "round_number": 2,
                "target_id": "hero-1",
                "target_new_hp": 9,
                "target_state": {"target_id": "hero-1", "hp_after": 9},
                "entity_positions": {"enemy-1": {"x": 4, "y": 5}},
                "player_targeted": True,
                "legendary_action_prompt": {
                    "trigger": "legendary_action",
                    "actor_id": "dragon-1",
                    "actions": [{"id": "tail"}],
                },
                "attack_result": attack_result,
                "damage": 5,
                "damage_roll": {"notation": "1d6+2", "total": 5},
                "weapon_resource": {"weapon": "Shortbow", "ammo_remaining": 0},
                "weapon_resources": [{"weapon": "Shortbow", "ammo_remaining": 0}],
                "enemy_action": {"name": "Shortbow"},
                "enemy_actions": [{"name": "Move"}, {"name": "Shortbow"}],
                "tactical_decision": {"role": "striker"},
                "dice_result": spell_result,
                "spell_result": spell_result,
                "special_action": special_action,
                "save": {"ability": "dex", "dc": 13, "success": False},
                "target_results": target_results,
                "aoe_results": target_results,
                "dc_source": {"type": "monster_ability", "dc": 13},
                "concentration_check": {"broke": True, "spell_name": "Bless"},
                "concentration_checks": [{"broke": True, "spell_name": "Bless"}],
                "skirmisher_reposition": {
                    "from": {"x": 4, "y": 5},
                    "to": {"x": 6, "y": 5},
                    "steps": 2,
                },
                "confusion_turn": {"outcome": "move_randomly"},
            },
        )
        data = captured["event"].model_dump(mode="json")

        assert result["actor_id"] == "enemy-1"
        assert data["type"] == "combat_update"
        assert data["actor_id"] == "enemy-1"
        assert data["narration"] == "Goblin Guard slashes Smoke Sentinel."
        assert data["attack_result"] == attack_result
        assert data["damage"] == 5
        assert data["damage_roll"] == {"notation": "1d6+2", "total": 5}
        assert data["weapon_resource"] == {"weapon": "Shortbow", "ammo_remaining": 0}
        assert data["weapon_resources"] == [{"weapon": "Shortbow", "ammo_remaining": 0}]
        assert data["enemy_action"] == {"name": "Shortbow"}
        assert data["enemy_actions"] == [{"name": "Move"}, {"name": "Shortbow"}]
        assert data["tactical_decision"] == {"role": "striker"}
        assert data["dice_result"] == spell_result
        assert data["spell_result"] == spell_result
        assert data["special_action"] == special_action
        assert data["save"] == {"ability": "dex", "dc": 13, "success": False}
        assert data["target_results"] == target_results
        assert data["aoe_results"] == target_results
        assert data["dc_source"] == {"type": "monster_ability", "dc": 13}
        assert data["legendary_action_prompt"] == {
            "trigger": "legendary_action",
            "actor_id": "dragon-1",
            "actions": [{"id": "tail"}],
        }
        assert data["entity_positions"] == {"enemy-1": {"x": 4, "y": 5}}
        assert data["concentration_check"] == {"broke": True, "spell_name": "Bless"}
        assert data["concentration_checks"] == [{"broke": True, "spell_name": "Bless"}]
        assert data["skirmisher_reposition"] == {
            "from": {"x": 4, "y": 5},
            "to": {"x": 6, "y": 5},
            "steps": 2,
        }
        assert data["confusion_turn"] == {"outcome": "move_randomly"}

    def test_entity_moved_position(self):
        movement = {
            "type": "movement",
            "entity_id": "g1",
            "movement_cost": 2,
            "movement_path": [{"x": 2, "y": 5}, {"x": 3, "y": 5}],
        }
        e = EntityMoved(
            entity_id="g1",
            position={"x": 3, "y": 5},
            narration="Goblin moves.",
            movement=movement,
            dice_result=movement,
            special_action=movement,
        )
        d = e.model_dump(mode="json")
        assert d["position"] == {"x": 3, "y": 5}
        assert d["narration"] == "Goblin moves."
        assert d["movement"] == movement
        assert d["dice_result"] == movement
        assert d["special_action"] == movement

    def test_entity_moved_carries_combat_over_outcome(self):
        e = EntityMoved(
            entity_id="hero-1",
            position={"x": 4, "y": 5},
            combat_over=True,
            outcome="victory",
        )
        d = e.model_dump(mode="json")

        assert d["type"] == "entity_moved"
        assert d["combat_over"] is True
        assert d["outcome"] == "victory"

    def test_turn_changed_requires_round_fields(self):
        with pytest.raises(Exception):
            TurnChanged()  # 缺 round_number / next_turn_index


    def test_turn_changed_carries_control_prompts_and_delay_payload(self):
        reaction_prompt = {
            "trigger": "spell_cast",
            "reactor_character_id": "hero-1",
            "options": [{"type": "counterspell"}],
        }
        prompt = {
            "trigger": "lair_action",
            "timing": "initiative_count_20",
            "actions": [{"id": "seismic-pulse", "name": "Seismic Pulse"}],
        }
        delayed_turn = {
            "actor_id": "hero-1",
            "after_entity_id": "goblin-1",
            "moved": True,
        }

        event = TurnChanged(
            round_number=1,
            next_turn_index=0,
            player_can_react=True,
            reaction_prompt=reaction_prompt,
            lair_action_prompt=prompt,
            legendary_action_prompt=None,
            turn_order_delayed=True,
            delayed_turn=delayed_turn,
        )
        data = event.model_dump(mode="json")

        assert data["type"] == "turn_changed"
        assert data["player_can_react"] is True
        assert data["reaction_prompt"] == reaction_prompt
        assert data["lair_action_prompt"] == prompt
        assert data["legendary_action_prompt"] is None
        assert data["turn_order_delayed"] is True
        assert data["delayed_turn"] == delayed_turn


class TestRoundTrip:
    """validate → model → dump → validate 回环，验证字段不丢失。"""

    def test_round_trip(self):
        originals = [
            MemberJoined(user_id="u1", members=[]),
            DMResponded(by_user_id="u1", action_type="combat", narrative="铛！"),
            EntityMoved(entity_id="g1", position={"x": 1, "y": 2}),
        ]
        for e in originals:
            d = e.model_dump(mode="json")
            # 用 JSON 字符串往返确保可序列化
            s = json.dumps(d, ensure_ascii=False)
            d2 = json.loads(s)
            re_constructed = type(e).model_validate(d2)
            assert re_constructed.model_dump() == e.model_dump()


# ─── ws_manager 集成 ──────────────────────────────────────

class FakeWebSocket:
    """伪造 WebSocket，记录所有 send_json 调用。"""
    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        # 模拟 ws 的 send_json 要求参数可序列化
        json.dumps(payload)
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_ws_manager_accepts_pydantic():
    """ws_manager.broadcast 传 Pydantic 实例应该自动 model_dump。"""
    from services.ws_manager import WSManager

    mgr = WSManager()
    ws = FakeWebSocket()
    session_id = "s1"

    # 手动注册（不走完整 connect 流程）
    mgr.rooms[session_id] = {ws}
    mgr.ws_meta[ws] = (session_id, "u1")
    mgr.user_ws[(session_id, "u1")] = ws

    event = DMThinkingStart(by_user_id="u1", action_text="行动")
    ok = await mgr.broadcast(session_id, event)
    assert ok == 1
    assert ws.sent[0]["type"] == "dm_thinking_start"
    assert ws.sent[0]["by_user_id"] == "u1"


@pytest.mark.asyncio
async def test_ws_manager_accepts_dict_backward_compat():
    """老的 dict 广播继续工作（向后兼容）。"""
    from services.ws_manager import WSManager

    mgr = WSManager()
    ws = FakeWebSocket()
    session_id = "s1"
    mgr.rooms[session_id] = {ws}
    mgr.ws_meta[ws] = (session_id, "u1")
    mgr.user_ws[(session_id, "u1")] = ws

    await mgr.broadcast(session_id, {"type": "legacy_event", "x": 1})
    assert ws.sent[0] == {"type": "legacy_event", "x": 1}
