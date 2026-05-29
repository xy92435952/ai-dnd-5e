import pytest

from models import SessionMember, User
from services import room_service


@pytest.mark.asyncio
async def test_create_room_initializes_default_party_group(db_session, sample_module, sample_user):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="分队测试房",
        max_players=4,
    )

    info = await room_service.get_room_info(db_session, session.id)

    assert info["active_group_id"] == "main"
    assert info["pending_actions_by_group"] == {"main": []}
    assert info["group_readiness"] == {"main": {}}
    assert info["party_groups"] == [
        {
            "id": "main",
            "name": "主队",
            "location": "当前场景",
            "member_user_ids": [sample_user.id],
        }
    ]


@pytest.mark.asyncio
async def test_joining_custom_group_moves_member_out_of_other_groups(db_session, sample_module, sample_user):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="分队测试房",
        max_players=4,
    )
    guest = User(username="guest_group", password_hash="x", display_name="后巷玩家")
    db_session.add(guest)
    await db_session.flush()
    db_session.add(SessionMember(session_id=session.id, user_id=guest.id, role="player"))
    await db_session.commit()
    await room_service.ensure_multiplayer_state(db_session, session.id)

    info = await room_service.set_member_group(
        db_session,
        session_id=session.id,
        user_id=guest.id,
        group_id="alley",
        group_name="后巷组",
        location="酒馆后巷",
    )

    groups = {group["id"]: group for group in info["party_groups"]}
    assert groups["main"]["member_user_ids"] == [sample_user.id]
    assert groups["alley"]["member_user_ids"] == [guest.id]
    assert groups["alley"]["name"] == "后巷组"
    assert groups["alley"]["location"] == "酒馆后巷"
    assert info["active_group_id"] == "alley"
    assert info["group_readiness"]["alley"] == {guest.id: "drafting"}


@pytest.mark.asyncio
async def test_group_actions_are_scoped_and_clearable(db_session, sample_module, sample_user):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="分队测试房",
        max_players=4,
    )
    await room_service.set_member_group(
        db_session,
        session_id=session.id,
        user_id=sample_user.id,
        group_id="main",
        group_name="主队",
        location="酒馆大厅",
    )

    info = await room_service.submit_group_action(
        db_session,
        session_id=session.id,
        user_id=sample_user.id,
        group_id="main",
        action_text="我观察老板是否在说谎。",
    )

    actions = info["pending_actions_by_group"]["main"]
    assert info["group_readiness"]["main"][sample_user.id] == "drafting"
    assert len(actions) == 1
    assert actions[0]["user_id"] == sample_user.id
    assert actions[0]["text"] == "我观察老板是否在说谎。"
    assert actions[0]["display_name"] == "测试玩家"
    assert "created_at" in actions[0]

    cleared = await room_service.clear_group_actions(db_session, session.id, "main")
    assert cleared["pending_actions_by_group"]["main"] == []
    assert cleared["group_readiness"]["main"] == {}


@pytest.mark.asyncio
async def test_new_group_action_clears_stale_readiness_for_all_group_members(db_session, sample_module, sample_user):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="Stale readiness room",
        max_players=4,
    )
    ally = User(username="stale_ready_ally", password_hash="x", display_name="Ally")
    db_session.add(ally)
    await db_session.flush()
    db_session.add(SessionMember(session_id=session.id, user_id=ally.id, role="player"))
    await db_session.commit()

    await room_service.set_member_group(
        db_session,
        session_id=session.id,
        user_id=ally.id,
        group_id="main",
        group_name="Main",
        location="Tavern hall",
    )
    await room_service.submit_group_action(
        db_session,
        session_id=session.id,
        user_id=sample_user.id,
        group_id="main",
        action_text="I inspect the door seam.",
    )
    await room_service.set_group_readiness(
        db_session,
        session_id=session.id,
        user_id=sample_user.id,
        group_id="main",
        status="ready",
    )
    await room_service.set_group_readiness(
        db_session,
        session_id=session.id,
        user_id=ally.id,
        group_id="main",
        status="ready",
    )

    updated = await room_service.submit_group_action(
        db_session,
        session_id=session.id,
        user_id=ally.id,
        group_id="main",
        action_text="I switch to helping break the door.",
    )

    assert [item["text"] for item in updated["pending_actions_by_group"]["main"]] == [
        "I inspect the door seam.",
        "I switch to helping break the door.",
    ]
    assert updated["group_readiness"]["main"] == {
        sample_user.id: "drafting",
        ally.id: "drafting",
    }


@pytest.mark.asyncio
async def test_member_cannot_submit_action_to_other_group(db_session, sample_module, sample_user):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="分队权限测试房",
        max_players=4,
    )
    guest = User(username="guest_other_group", password_hash="x", display_name="酒馆玩家")
    db_session.add(guest)
    await db_session.flush()
    db_session.add(SessionMember(session_id=session.id, user_id=guest.id, role="player"))
    await db_session.commit()
    await room_service.ensure_multiplayer_state(db_session, session.id)
    await room_service.set_member_group(
        db_session,
        session_id=session.id,
        user_id=guest.id,
        group_id="tavern",
        group_name="酒馆组",
        location="酒馆大厅",
    )

    with pytest.raises(Exception) as exc:
        await room_service.submit_group_action(
            db_session,
            session_id=session.id,
            user_id=sample_user.id,
            group_id="tavern",
            action_text="我替酒馆组说一句。",
        )

    assert getattr(exc.value, "status_code", None) == 403


@pytest.mark.asyncio
async def test_group_readiness_tracks_member_confirmation(db_session, sample_module, sample_user):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="分队准备测试房",
        max_players=4,
    )
    await room_service.set_member_group(
        db_session,
        session_id=session.id,
        user_id=sample_user.id,
        group_id="main",
        group_name="主队",
        location="酒馆大厅",
    )

    ready = await room_service.set_group_readiness(
        db_session,
        session_id=session.id,
        user_id=sample_user.id,
        group_id="main",
        status="ready",
    )

    assert ready["group_readiness"]["main"][sample_user.id] == "ready"

    waiting = await room_service.set_group_readiness(
        db_session,
        session_id=session.id,
        user_id=sample_user.id,
        group_id="main",
        status="waiting",
    )

    assert waiting["group_readiness"]["main"][sample_user.id] == "waiting"


@pytest.mark.asyncio
async def test_active_group_can_be_changed_without_moving_members(db_session, sample_module, sample_user):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="分队测试房",
        max_players=4,
    )
    await room_service.set_member_group(
        db_session,
        session_id=session.id,
        user_id=sample_user.id,
        group_id="alley",
        group_name="后巷组",
        location="酒馆后巷",
    )

    focused = await room_service.set_active_group(
        db_session,
        session_id=session.id,
        group_id="main",
        actor_user_id=sample_user.id,
    )

    assert focused["active_group_id"] == "main"
    groups = {group["id"]: group for group in focused["party_groups"]}
    assert groups["alley"]["member_user_ids"] == [sample_user.id]


@pytest.mark.asyncio
async def test_context_builder_includes_multiplayer_party_context(db_session, sample_module, sample_user):
    from models import Character
    from services.context_builder import ContextBuilder
    import json

    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="分队测试房",
        max_players=4,
    )
    char = Character(
        session_id=session.id,
        user_id=sample_user.id,
        is_player=True,
        name="分队角色",
        race="Human",
        char_class="Rogue",
        level=1,
        ability_scores={"str": 10, "dex": 16, "con": 12, "int": 12, "wis": 10, "cha": 10},
        hp_current=8,
    )
    db_session.add(char)
    await db_session.commit()
    await room_service.set_member_group(
        db_session,
        session_id=session.id,
        user_id=sample_user.id,
        group_id="alley",
        group_name="后巷组",
        location="酒馆后巷",
    )
    await room_service.submit_group_action(
        db_session,
        session_id=session.id,
        user_id=sample_user.id,
        group_id="alley",
        action_text="我先检查仓库门锁。",
    )
    await db_session.refresh(session)

    builder = ContextBuilder(session=session, module=sample_module, characters=[char])
    game_state = json.loads(builder._build_game_state(current_actor_id=char.id))

    assert game_state["multiplayer_context"]["active_group_id"] == "alley"
    assert game_state["multiplayer_context"]["active_group"]["name"] == "后巷组"
    assert game_state["multiplayer_context"]["active_group"]["location"] == "酒馆后巷"
    assert game_state["multiplayer_context"]["active_group"]["member_character_names"] == ["分队角色"]
    assert game_state["multiplayer_context"]["pending_actions"][0]["text"] == "我先检查仓库门锁。"
