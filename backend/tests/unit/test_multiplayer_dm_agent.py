import pytest

from models import SessionMember, User
from services import room_service
from services.graphs.multiplayer_dm_agent import run_multiplayer_dm_agent
from api.game import _find_next_ready_group_id


def test_find_next_ready_group_only_returns_pending_all_ready_group():
    room = {
        "party_groups": [
            {"id": "alley", "member_user_ids": ["u1"]},
            {"id": "tavern", "member_user_ids": ["u2"]},
            {"id": "tower", "member_user_ids": ["u3", "u4"]},
        ],
        "pending_actions_by_group": {
            "alley": [{"text": "done"}],
            "tavern": [{"text": "wait"}],
            "tower": [{"text": "go"}],
        },
        "group_readiness": {
            "alley": {"u1": "ready"},
            "tavern": {"u2": "waiting"},
            "tower": {"u3": "ready", "u4": "ready"},
        },
    }

    assert _find_next_ready_group_id(room, exclude_group_ids={"alley"}) == "tower"


@pytest.mark.asyncio
async def test_multiplayer_dm_agent_processes_actor_group_without_v2_when_other_group_is_waiting(
    db_session,
    sample_module,
    sample_user,
):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="多人 DM readiness 测试",
        max_players=4,
    )
    ally = User(username="ready_ally", password_hash="x", display_name="艾拉")
    tavern = User(username="waiting_other", password_hash="x", display_name="凯伦")
    db_session.add_all([ally, tavern])
    await db_session.flush()
    db_session.add_all([
        SessionMember(session_id=session.id, user_id=ally.id, role="player"),
        SessionMember(session_id=session.id, user_id=tavern.id, role="player"),
    ])
    await db_session.commit()

    await room_service.set_member_group(db_session, session.id, sample_user.id, "alley", "后巷组", "酒馆后巷")
    await room_service.set_member_group(db_session, session.id, ally.id, "alley", "后巷组", "酒馆后巷")
    await room_service.set_member_group(db_session, session.id, tavern.id, "tavern", "酒馆组", "酒馆大厅")
    await room_service.submit_group_action(db_session, session.id, ally.id, "alley", "我检查仓库门锁。")
    await room_service.submit_group_action(db_session, session.id, tavern.id, "tavern", "我等老板回应。")
    await room_service.set_group_readiness(db_session, session.id, sample_user.id, "alley", "ready")
    await room_service.set_group_readiness(db_session, session.id, ally.id, "alley", "ready")
    await room_service.set_group_readiness(db_session, session.id, tavern.id, "tavern", "waiting")
    await db_session.refresh(session)

    calls = {"v2": 0}

    async def should_not_call_v2(context, action_text):
        calls["v2"] += 1
        return {
            "decision": "switch_focus",
            "focus_group_id": "tavern",
            "knowledge_scope": "group",
            "visible_to_user_ids": [tavern.id],
            "clear_pending_group_ids": [],
            "table_message": "不应触发的 v2 决策。",
            "reason": "这个场景应由 readiness 本地策略处理。",
        }

    decision = await run_multiplayer_dm_agent(
        db=db_session,
        session=session,
        actor_user_id=sample_user.id,
        action_text="我撬开后门。",
        table_decider=should_not_call_v2,
    )

    assert decision.should_call_base_dm is True
    assert decision.focus_group_id == "alley"
    assert calls["v2"] == 0
    assert decision.clear_pending_group_ids == ["alley"]
    assert "艾拉：我检查仓库门锁。" in decision.effective_action_text
    assert "凯伦" not in decision.effective_action_text
    assert "分队确认状态：测试玩家: 已确认；艾拉: 已确认" in decision.effective_action_text


@pytest.mark.asyncio
async def test_multiplayer_dm_agent_uses_v2_when_multiple_ready_groups_have_pending_actions(
    db_session,
    sample_module,
    sample_user,
):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="多人 DM 多 ready 分队测试",
        max_players=4,
    )
    ally = User(username="multi_ready_ally", password_hash="x", display_name="艾拉")
    tavern = User(username="multi_ready_other", password_hash="x", display_name="凯伦")
    db_session.add_all([ally, tavern])
    await db_session.flush()
    db_session.add_all([
        SessionMember(session_id=session.id, user_id=ally.id, role="player"),
        SessionMember(session_id=session.id, user_id=tavern.id, role="player"),
    ])
    await db_session.commit()

    await room_service.set_member_group(db_session, session.id, sample_user.id, "alley", "后巷组", "酒馆后巷")
    await room_service.set_member_group(db_session, session.id, ally.id, "alley", "后巷组", "酒馆后巷")
    await room_service.set_member_group(db_session, session.id, tavern.id, "tavern", "酒馆组", "酒馆大厅")
    await room_service.submit_group_action(db_session, session.id, ally.id, "alley", "我检查仓库门锁。")
    await room_service.submit_group_action(db_session, session.id, tavern.id, "tavern", "我继续套老板的话。")
    await room_service.set_group_readiness(db_session, session.id, sample_user.id, "alley", "ready")
    await room_service.set_group_readiness(db_session, session.id, ally.id, "alley", "ready")
    await room_service.set_group_readiness(db_session, session.id, tavern.id, "tavern", "ready")
    await db_session.refresh(session)

    calls = {"v2": 0}

    async def fake_table_decider(context, action_text):
        calls["v2"] += 1
        return {
            "decision": "process_actor_group",
            "focus_group_id": "alley",
            "knowledge_scope": "group",
            "visible_to_user_ids": [sample_user.id, ally.id],
            "clear_pending_group_ids": ["alley"],
            "table_message": None,
            "reason": "多个分队都已确认，按当前行动分队先处理。",
        }

    decision = await run_multiplayer_dm_agent(
        db=db_session,
        session=session,
        actor_user_id=sample_user.id,
        action_text="我撬开后门。",
        table_decider=fake_table_decider,
    )

    assert calls["v2"] == 1
    assert decision.should_call_base_dm is True
    assert decision.focus_group_id == "alley"
    assert decision.table_reason == "多个分队都已确认，按当前行动分队先处理。"


@pytest.mark.asyncio
async def test_multiplayer_dm_agent_builds_effective_action_from_actor_group(
    db_session,
    sample_module,
    sample_user,
):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="多人 DM 编排测试",
        max_players=4,
    )
    supporter = User(username="supporter", password_hash="x", display_name="艾拉")
    db_session.add(supporter)
    await db_session.flush()
    db_session.add(SessionMember(session_id=session.id, user_id=supporter.id, role="player"))
    await db_session.commit()

    await room_service.set_member_group(
        db_session,
        session_id=session.id,
        user_id=sample_user.id,
        group_id="alley",
        group_name="后巷组",
        location="酒馆后巷",
    )
    await room_service.set_member_group(
        db_session,
        session_id=session.id,
        user_id=supporter.id,
        group_id="alley",
        group_name="后巷组",
        location="酒馆后巷",
    )
    await room_service.submit_group_action(
        db_session,
        session_id=session.id,
        user_id=supporter.id,
        group_id="alley",
        action_text="我检查仓库门锁。",
    )
    await room_service.set_active_group(db_session, session.id, "main", actor_user_id=sample_user.id)
    await db_session.refresh(session)

    decision = await run_multiplayer_dm_agent(
        db=db_session,
        session=session,
        actor_user_id=sample_user.id,
        action_text="我撬开后门。",
    )

    assert decision.should_call_base_dm is True
    assert decision.actor_group_id == "alley"
    assert decision.focus_group_id == "alley"
    assert decision.clear_pending_group_ids == ["alley"]
    assert decision.room_updates == {"active_group_id": "alley"}
    assert "我撬开后门。" in decision.effective_action_text
    assert "【多人分队上下文】" in decision.effective_action_text
    assert "当前焦点分队：后巷组" in decision.effective_action_text
    assert "位置：酒馆后巷" in decision.effective_action_text
    assert "【同分队队友意图】" in decision.effective_action_text
    assert "艾拉：我检查仓库门锁。" in decision.effective_action_text


@pytest.mark.asyncio
async def test_multiplayer_dm_agent_does_not_pull_other_group_actions(
    db_session,
    sample_module,
    sample_user,
):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="多人 DM 编排测试",
        max_players=4,
    )
    other = User(username="tavern_player", password_hash="x", display_name="凯伦")
    db_session.add(other)
    await db_session.flush()
    db_session.add(SessionMember(session_id=session.id, user_id=other.id, role="player"))
    await db_session.commit()

    await room_service.set_member_group(db_session, session.id, sample_user.id, "alley", "后巷组", "酒馆后巷")
    await room_service.set_member_group(db_session, session.id, other.id, "tavern", "酒馆组", "酒馆大厅")
    await room_service.submit_group_action(
        db_session,
        session_id=session.id,
        user_id=other.id,
        group_id="tavern",
        action_text="我继续套老板的话。",
    )
    await db_session.refresh(session)

    decision = await run_multiplayer_dm_agent(
        db=db_session,
        session=session,
        actor_user_id=sample_user.id,
        action_text="我撬开后门。",
    )

    assert decision.clear_pending_group_ids == []
    assert "我继续套老板的话" not in decision.effective_action_text
    assert "其他分队待处理：酒馆组 1 条" in decision.effective_action_text


@pytest.mark.asyncio
async def test_multiplayer_dm_agent_uses_table_decision_for_multi_group_pressure(
    db_session,
    sample_module,
    sample_user,
):
    """多分队都有待处理动作时，v2 桌面裁决层应介入，但仍只把焦点组交给基础 DM。"""
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="多人 DM v2 测试",
        max_players=4,
    )
    ally = User(username="alley_support", password_hash="x", display_name="艾拉")
    tavern = User(username="tavern_support", password_hash="x", display_name="凯伦")
    db_session.add_all([ally, tavern])
    await db_session.flush()
    db_session.add_all([
        SessionMember(session_id=session.id, user_id=ally.id, role="player"),
        SessionMember(session_id=session.id, user_id=tavern.id, role="player"),
    ])
    await db_session.commit()

    await room_service.set_member_group(db_session, session.id, sample_user.id, "alley", "后巷组", "酒馆后巷")
    await room_service.set_member_group(db_session, session.id, ally.id, "alley", "后巷组", "酒馆后巷")
    await room_service.set_member_group(db_session, session.id, tavern.id, "tavern", "酒馆组", "酒馆大厅")
    await room_service.submit_group_action(db_session, session.id, ally.id, "alley", "我检查仓库门锁。")
    await room_service.submit_group_action(db_session, session.id, tavern.id, "tavern", "我继续套老板的话。")
    await room_service.set_group_readiness(db_session, session.id, ally.id, "alley", "ready")
    await room_service.set_group_readiness(db_session, session.id, tavern.id, "tavern", "waiting")
    await db_session.refresh(session)

    seen = {}

    async def fake_table_decider(context, action_text):
        seen["action_text"] = action_text
        seen["other_pending_counts"] = dict(context["other_pending_counts"])
        seen["group_readiness"] = dict(context["group_readiness"])
        return {
            "decision": "process_actor_group",
            "focus_group_id": "alley",
            "knowledge_scope": "group",
            "visible_to_user_ids": [sample_user.id, ally.id],
            "clear_pending_group_ids": ["alley"],
            "table_message": None,
            "reason": "后巷组正在执行当前行动，酒馆组保留待处理。",
        }

    decision = await run_multiplayer_dm_agent(
        db=db_session,
        session=session,
        actor_user_id=sample_user.id,
        action_text="我撬开后门。",
        table_decider=fake_table_decider,
    )

    assert seen["action_text"] == "我撬开后门。"
    assert seen["other_pending_counts"] == {"tavern": 1}
    assert seen["group_readiness"]["alley"][ally.id] == "ready"
    assert seen["group_readiness"]["tavern"][tavern.id] == "waiting"
    assert decision.should_call_base_dm is True
    assert decision.focus_group_id == "alley"
    assert decision.clear_pending_group_ids == ["alley"]
    assert decision.visibility["scope"] == "group"
    assert decision.visibility["visible_to_user_ids"] == [sample_user.id, ally.id]
    assert "艾拉：我检查仓库门锁。" in decision.effective_action_text
    assert "艾拉: 已确认" in decision.effective_action_text
    assert "我继续套老板的话" not in decision.effective_action_text


@pytest.mark.asyncio
async def test_multiplayer_dm_agent_table_decision_can_switch_focus_without_base_dm(
    db_session,
    sample_module,
    sample_user,
):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="多人 DM v2 切镜头测试",
        max_players=4,
    )
    tavern = User(username="focus_target", password_hash="x", display_name="凯伦")
    db_session.add(tavern)
    await db_session.flush()
    db_session.add(SessionMember(session_id=session.id, user_id=tavern.id, role="player"))
    await db_session.commit()

    await room_service.set_member_group(db_session, session.id, sample_user.id, "alley", "后巷组", "酒馆后巷")
    await room_service.set_member_group(db_session, session.id, tavern.id, "tavern", "酒馆组", "酒馆大厅")
    await room_service.submit_group_action(db_session, session.id, tavern.id, "tavern", "我想先和老板对话。")
    await db_session.refresh(session)

    async def fake_table_decider(context, action_text):
        return {
            "decision": "switch_focus",
            "focus_group_id": "tavern",
            "knowledge_scope": "group",
            "visible_to_user_ids": [tavern.id],
            "clear_pending_group_ids": [],
            "table_message": "镜头转向酒馆组，请酒馆组玩家先行动。",
            "reason": "玩家明确要求切镜头。",
        }

    decision = await run_multiplayer_dm_agent(
        db=db_session,
        session=session,
        actor_user_id=sample_user.id,
        action_text="先切到酒馆看看他们。",
        table_decider=fake_table_decider,
    )

    assert decision.should_call_base_dm is False
    assert decision.table_message == "镜头转向酒馆组，请酒馆组玩家先行动。"
    assert decision.table_reason == "玩家明确要求切镜头。"
    assert decision.table_decision == {
        "decision": "switch_focus",
        "reason_code": "switch_focus",
        "target_group_id": "tavern",
        "waiting_group_id": None,
        "actor_group_id": "alley",
        "focus_group_id": "tavern",
        "knowledge_scope": "group",
    }
    assert decision.focus_group_id == "tavern"
    assert decision.room_updates == {"active_group_id": "tavern"}
    assert decision.clear_pending_group_ids == []
    assert decision.visibility["visible_to_user_ids"] == [tavern.id]


@pytest.mark.asyncio
async def test_multiplayer_dm_agent_does_not_give_host_focus_group_visibility(
    db_session,
    sample_module,
    sample_user,
):
    """房主只是玩家；不在焦点分队时，不能因为 host_user_id 被加入分队可见列表。"""
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="多人 DM 房主可见性测试",
        max_players=4,
    )
    alley_actor = User(username="alley_actor", password_hash="x", display_name="艾拉")
    tavern_member = User(username="host_visibility_other", password_hash="x", display_name="凯伦")
    db_session.add_all([alley_actor, tavern_member])
    await db_session.flush()
    db_session.add_all([
        SessionMember(session_id=session.id, user_id=alley_actor.id, role="player"),
        SessionMember(session_id=session.id, user_id=tavern_member.id, role="player"),
    ])
    await db_session.commit()

    await room_service.set_member_group(db_session, session.id, sample_user.id, "tavern", "酒馆组", "酒馆大厅")
    await room_service.set_member_group(db_session, session.id, tavern_member.id, "tavern", "酒馆组", "酒馆大厅")
    await room_service.set_member_group(db_session, session.id, alley_actor.id, "alley", "后巷组", "酒馆后巷")
    await room_service.submit_group_action(db_session, session.id, tavern_member.id, "tavern", "我继续套老板的话。")
    await db_session.refresh(session)

    async def fake_table_decider(context, action_text):
        return {
            "decision": "switch_focus",
            "focus_group_id": "alley",
            "knowledge_scope": "group",
            "visible_to_user_ids": [],
            "clear_pending_group_ids": [],
            "table_message": "镜头转向后巷组。",
            "reason": "后巷组需要先处理私下行动。",
        }

    decision = await run_multiplayer_dm_agent(
        db=db_session,
        session=session,
        actor_user_id=alley_actor.id,
        action_text="先切镜头到后巷。",
        table_decider=fake_table_decider,
    )

    assert session.host_user_id == sample_user.id
    assert decision.visibility["scope"] == "group"
    assert decision.visibility["visible_to_user_ids"] == [alley_actor.id]
    assert sample_user.id not in decision.visibility["visible_to_user_ids"]


@pytest.mark.asyncio
async def test_multiplayer_dm_agent_party_scope_keeps_visible_users_empty(
    db_session,
    sample_module,
    sample_user,
):
    """party scope 表示全队可见，不应枚举房间成员，更不能制造 host 特权列表。"""
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="多人 DM 全队可见性测试",
        max_players=4,
    )
    ally = User(username="party_scope_ally", password_hash="x", display_name="艾拉")
    other = User(username="party_scope_other", password_hash="x", display_name="凯伦")
    db_session.add_all([ally, other])
    await db_session.flush()
    db_session.add_all([
        SessionMember(session_id=session.id, user_id=ally.id, role="player"),
        SessionMember(session_id=session.id, user_id=other.id, role="player"),
    ])
    await db_session.commit()

    await room_service.set_member_group(db_session, session.id, sample_user.id, "alley", "后巷组", "酒馆后巷")
    await room_service.set_member_group(db_session, session.id, ally.id, "alley", "后巷组", "酒馆后巷")
    await room_service.set_member_group(db_session, session.id, other.id, "tavern", "酒馆组", "酒馆大厅")
    await room_service.submit_group_action(db_session, session.id, ally.id, "alley", "我检查仓库门锁。")
    await room_service.submit_group_action(db_session, session.id, other.id, "tavern", "我继续套老板的话。")
    await db_session.refresh(session)

    async def fake_table_decider(context, action_text):
        return {
            "decision": "process_actor_group",
            "focus_group_id": "alley",
            "knowledge_scope": "party",
            "visible_to_user_ids": [],
            "clear_pending_group_ids": ["alley"],
            "table_message": None,
            "reason": "公开桌面节奏，全队都可知道当前处理顺序。",
        }

    decision = await run_multiplayer_dm_agent(
        db=db_session,
        session=session,
        actor_user_id=sample_user.id,
        action_text="我撬开后门。",
        table_decider=fake_table_decider,
    )

    assert decision.should_call_base_dm is True
    assert decision.visibility == {
        "scope": "party",
        "group_id": "alley",
        "visible_to_user_ids": [],
    }


@pytest.mark.asyncio
async def test_multiplayer_dm_agent_falls_back_to_v1_when_table_decision_is_invalid(
    db_session,
    sample_module,
    sample_user,
):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="多人 DM v2 回退测试",
        max_players=4,
    )
    ally = User(username="bad_json_ally", password_hash="x", display_name="艾拉")
    other = User(username="bad_json_other", password_hash="x", display_name="凯伦")
    db_session.add_all([ally, other])
    await db_session.flush()
    db_session.add_all([
        SessionMember(session_id=session.id, user_id=ally.id, role="player"),
        SessionMember(session_id=session.id, user_id=other.id, role="player"),
    ])
    await db_session.commit()

    await room_service.set_member_group(db_session, session.id, sample_user.id, "alley", "后巷组", "酒馆后巷")
    await room_service.set_member_group(db_session, session.id, ally.id, "alley", "后巷组", "酒馆后巷")
    await room_service.set_member_group(db_session, session.id, other.id, "tavern", "酒馆组", "酒馆大厅")
    await room_service.submit_group_action(db_session, session.id, ally.id, "alley", "我检查仓库门锁。")
    await room_service.submit_group_action(db_session, session.id, other.id, "tavern", "我继续套老板的话。")
    await db_session.refresh(session)

    async def bad_table_decider(context, action_text):
        return "not json"

    decision = await run_multiplayer_dm_agent(
        db=db_session,
        session=session,
        actor_user_id=sample_user.id,
        action_text="我撬开后门。",
        table_decider=bad_table_decider,
    )

    assert decision.should_call_base_dm is True
    assert decision.focus_group_id == "alley"
    assert decision.clear_pending_group_ids == ["alley"]
    assert "我撬开后门。" in decision.effective_action_text
    assert "艾拉：我检查仓库门锁。" in decision.effective_action_text
    assert "其他分队待处理：酒馆组 1 条" in decision.effective_action_text
