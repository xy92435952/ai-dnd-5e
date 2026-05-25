"""Cross-user access boundary regressions for sessions, modules, combat, and characters."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from models import Character, CombatState, Module, Session, SessionMember

pytestmark = pytest.mark.integration


async def _register(client, username, password="password"):
    response = await client.post("/auth/register", json={
        "username": username,
        "password": password,
        "display_name": username,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _module(owner_id: str | None, name: str = "Private Module") -> Module:
    return Module(
        id=str(uuid.uuid4()),
        user_id=owner_id,
        name=name,
        file_path="",
        file_type="md",
        parsed_content={
            "setting": "private",
            "tone": "standard",
            "plot_summary": "private test module",
            "scenes": [{"title": "start", "description": "private opening"}],
            "npcs": [],
            "monsters": [],
            "magic_items": [],
        },
        parse_status="done",
        level_min=1,
        level_max=3,
        recommended_party_size=4,
    )


def _boundary_character(
    *,
    user_id: str,
    session_id: str,
    name: str,
    battle_master: bool = False,
) -> Character:
    subclass_effects = {}
    class_resources = {}
    if battle_master:
        subclass_effects = {
            "battle_master": True,
            "maneuvers": ["trip"],
            "superiority_die": "d8",
        }
        class_resources = {"superiority_dice_remaining": 1}

    return Character(
        id=str(uuid.uuid4()),
        user_id=user_id,
        session_id=session_id,
        name=name,
        race="Human",
        char_class="Fighter",
        level=3 if battle_master else 1,
        ability_scores={"str": 16, "dex": 14, "con": 14, "int": 14, "wis": 12, "cha": 10},
        derived={
            "hp_max": 18,
            "ac": 16,
            "initiative": 2,
            "proficiency_bonus": 2,
            "attack_bonus": 5,
            "hit_die": 8,
            "spell_save_dc": 13,
            "spell_ability": "int",
            "ability_modifiers": {"str": 3, "dex": 2, "con": 2, "int": 2, "wis": 1, "cha": 0},
            "saving_throws": {"str": 5, "con": 4},
            "subclass_effects": subclass_effects,
        },
        hp_current=18,
        proficient_skills=["Athletics"],
        proficient_saves=["str", "con"],
        spell_slots={"1st": 1},
        class_resources=class_resources,
        is_player=True,
    )


async def _seed_two_owned_combats(db_session, *, user_id: str, module_id: str):
    session_a_id = str(uuid.uuid4())
    session_b_id = str(uuid.uuid4())
    char_a = _boundary_character(
        user_id=user_id,
        session_id=session_a_id,
        name="boundary hero A",
        battle_master=True,
    )
    char_b = _boundary_character(
        user_id=user_id,
        session_id=session_b_id,
        name="boundary hero B",
    )
    session_a = Session(
        id=session_a_id,
        user_id=user_id,
        module_id=module_id,
        player_character_id=char_a.id,
        current_scene="boundary A",
        session_history="",
        game_state={
            "companion_ids": [],
            "enemies": [{
                "id": "goblin-a",
                "name": "goblin A",
                "hp_current": 9,
                "max_hp": 9,
                "derived": {"hp_max": 9, "ac": 13, "ability_modifiers": {"str": 1, "dex": 1}},
                "conditions": [],
            }],
        },
        save_name="boundary A",
        combat_active=True,
    )
    session_b = Session(
        id=session_b_id,
        user_id=user_id,
        module_id=module_id,
        player_character_id=char_b.id,
        current_scene="boundary B",
        session_history="",
        game_state={"companion_ids": [], "enemies": []},
        save_name="boundary B",
        combat_active=True,
    )
    combat_a = CombatState(
        id=str(uuid.uuid4()),
        session_id=session_a_id,
        grid_data={},
        entity_positions={
            char_a.id: {"x": 5, "y": 5},
            "goblin-a": {"x": 6, "y": 5},
        },
        turn_order=[
            {"character_id": char_a.id, "name": char_a.name, "initiative": 15, "is_player": True, "is_enemy": False},
            {"character_id": "goblin-a", "name": "goblin A", "initiative": 10, "is_player": False, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        combat_log=[],
        turn_states={},
    )
    db_session.add_all([session_a, session_b, char_a, char_b, combat_a])
    await db_session.commit()
    return session_a, char_a, combat_a, session_b, char_b


async def test_private_module_cannot_be_read_deleted_or_started_by_other_user(
    client, db_session,
):
    owner = await _register(client, "module_owner")
    other = await _register(client, "module_other")

    module = _module(owner["user_id"])
    db_session.add(module)
    await db_session.commit()

    read = await client.get(f"/modules/{module.id}", headers=_h(other["token"]))
    assert read.status_code == 403

    delete = await client.delete(f"/modules/{module.id}", headers=_h(other["token"]))
    assert delete.status_code == 403

    create_room = await client.post(
        "/game/rooms/create",
        headers=_h(other["token"]),
        json={"module_id": module.id, "save_name": "steal room", "max_players": 4},
    )
    assert create_room.status_code == 403

    create_session = await client.post(
        "/game/sessions",
        headers=_h(other["token"]),
        json={
            "module_id": module.id,
            "player_character_id": str(uuid.uuid4()),
            "companion_ids": [],
        },
    )
    assert create_session.status_code == 403

    owner_read = await client.get(f"/modules/{module.id}", headers=_h(owner["token"]))
    assert owner_read.status_code == 200, owner_read.text


async def test_private_module_cannot_be_used_for_character_or_party_generation(
    client, db_session,
):
    owner = await _register(client, "character_module_owner")
    other = await _register(client, "character_module_other")

    module = _module(owner["user_id"])
    other_character = Character(
        id=str(uuid.uuid4()),
        user_id=other["user_id"],
        name="other fighter",
        race="Human",
        char_class="Fighter",
        level=1,
        ability_scores={"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        derived={"hp_max": 12, "ac": 16},
        hp_current=12,
        is_player=True,
    )
    db_session.add_all([module, other_character])
    await db_session.commit()

    create_character = await client.post(
        "/characters/create",
        headers=_h(other["token"]),
        json={
            "module_id": module.id,
            "name": "stolen module hero",
            "race": "Human",
            "char_class": "Fighter",
            "level": 1,
            "ability_scores": {"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
            "proficient_skills": ["Athletics", "Perception"],
        },
    )
    assert create_character.status_code == 403

    generate_party = await client.post(
        "/characters/generate-party",
        headers=_h(other["token"]),
        json={
            "module_id": module.id,
            "player_character_id": other_character.id,
            "party_size": 1,
        },
    )
    assert generate_party.status_code == 403


async def test_non_member_cannot_read_or_advance_multiplayer_combat(
    client, db_session, sample_module,
):
    host = await _register(client, "combat_boundary_host")
    stranger = await _register(client, "combat_boundary_stranger")

    created = (await client.post(
        "/game/rooms/create",
        headers=_h(host["token"]),
        json={"module_id": sample_module.id, "save_name": "combat boundary", "max_players": 4},
    )).json()
    session_id = created["session_id"]

    host_character = Character(
        id=str(uuid.uuid4()),
        user_id=host["user_id"],
        name="host fighter",
        race="Human",
        char_class="Fighter",
        level=1,
        ability_scores={"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        derived={"hp_max": 12, "ac": 16},
        hp_current=12,
        is_player=True,
        session_id=session_id,
    )
    db_session.add(host_character)
    await db_session.commit()
    claim = await client.post(
        f"/game/rooms/{session_id}/claim-character",
        headers=_h(host["token"]),
        json={"character_id": host_character.id},
    )
    assert claim.status_code == 200, claim.text

    session = await db_session.get(Session, session_id)
    session.combat_active = True
    state = dict(session.game_state or {})
    state["enemies"] = [{
        "id": "orc-1",
        "name": "orc",
        "hp_current": 9,
        "max_hp": 9,
        "derived": {"hp_max": 9, "ac": 13, "ability_modifiers": {"str": 3, "dex": 1}},
        "actions": [{"name": "axe", "type": "melee_attack", "damage_dice": "1d8", "attack_bonus": 5}],
    }]
    session.game_state = state
    flag_modified(session, "game_state")
    combat = CombatState(
        id=str(uuid.uuid4()),
        session_id=session_id,
        entity_positions={host_character.id: {"x": 5, "y": 5}, "orc-1": {"x": 6, "y": 5}},
        turn_order=[
            {"character_id": "orc-1", "name": "orc", "initiative": 16, "is_player": False, "is_enemy": True},
            {"character_id": host_character.id, "name": host_character.name, "initiative": 12, "is_player": True, "is_enemy": False},
        ],
        current_turn_index=0,
        round_number=1,
        turn_states={},
    )
    db_session.add(combat)
    await db_session.commit()

    read = await client.get(f"/game/combat/{session_id}", headers=_h(stranger["token"]))
    assert read.status_code == 403

    skill_bar = await client.get(
        f"/game/combat/{session_id}/skill-bar",
        headers=_h(stranger["token"]),
        params={"entity_id": host_character.id},
    )
    assert skill_bar.status_code == 403

    ai_turn = await client.post(f"/game/combat/{session_id}/ai-turn", headers=_h(stranger["token"]))
    assert ai_turn.status_code == 403

    no_token = await client.post(f"/game/combat/{session_id}/ai-turn")
    assert no_token.status_code == 401


async def test_room_member_can_only_control_ai_character_on_that_ai_turn(
    client, db_session, sample_module,
):
    host = await _register(client, "ai_turn_guard_host")
    session_id = str(uuid.uuid4())
    host_character = _boundary_character(
        user_id=host["user_id"],
        session_id=session_id,
        name="host guard fighter",
    )
    ai_character = Character(
        id=str(uuid.uuid4()),
        user_id=None,
        session_id=session_id,
        name="AI guard companion",
        race="Human",
        char_class="Fighter",
        level=1,
        ability_scores={"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        derived={"hp_max": 12, "ac": 15, "initiative": 1},
        hp_current=12,
        is_player=False,
    )
    session = Session(
        id=session_id,
        user_id=host["user_id"],
        module_id=sample_module.id,
        player_character_id=host_character.id,
        current_scene="AI turn guard",
        session_history="",
        game_state={"multiplayer": {"current_speaker_user_id": host["user_id"]}},
        save_name="AI turn guard",
        is_multiplayer=True,
        room_code="246824",
        host_user_id=host["user_id"],
        max_players=4,
        combat_active=True,
    )
    member = SessionMember(
        session_id=session_id,
        user_id=host["user_id"],
        role="host",
        character_id=host_character.id,
    )
    combat = CombatState(
        id=str(uuid.uuid4()),
        session_id=session_id,
        entity_positions={
            host_character.id: {"x": 1, "y": 1},
            ai_character.id: {"x": 5, "y": 5},
        },
        turn_order=[
            {
                "character_id": host_character.id,
                "name": host_character.name,
                "initiative": 16,
                "is_player": True,
                "is_enemy": False,
            },
            {
                "character_id": ai_character.id,
                "name": ai_character.name,
                "initiative": 12,
                "is_player": False,
                "is_enemy": False,
            },
        ],
        current_turn_index=0,
        round_number=1,
        turn_states={},
    )
    db_session.add_all([session, member, host_character, ai_character, combat])
    await db_session.commit()

    out_of_turn = await client.post(
        f"/game/combat/{session_id}/move",
        headers=_h(host["token"]),
        json={"entity_id": ai_character.id, "to_x": 6, "to_y": 5},
    )
    assert out_of_turn.status_code == 403
    assert "不是你的回合" in out_of_turn.text
    await db_session.refresh(combat)
    assert combat.entity_positions[ai_character.id] == {"x": 5, "y": 5}

    combat.current_turn_index = 1
    await db_session.commit()
    on_turn = await client.post(
        f"/game/combat/{session_id}/move",
        headers=_h(host["token"]),
        json={"entity_id": ai_character.id, "to_x": 6, "to_y": 5},
    )
    assert on_turn.status_code == 200, on_turn.text
    await db_session.refresh(combat)
    assert combat.entity_positions[ai_character.id] == {"x": 6, "y": 5}


async def test_user_cannot_mutate_another_users_character_inventory(
    client, db_session, sample_user, sample_character,
):
    intruder = await _register(client, "inventory_intruder")
    sample_character.equipment = {"gold": 51, "gear": []}
    await db_session.commit()

    response = await client.post(
        f"/characters/{sample_character.id}/shop/buy",
        headers=_h(intruder["token"]),
        json={
            "item_name": "Healing Potion",
            "item_category": "gear",
            "quantity": 1,
        },
    )
    assert response.status_code == 403
    await db_session.refresh(sample_character)
    assert sample_character.equipment["gold"] == 51
    assert sample_character.equipment["gear"] == []


async def test_user_cannot_start_singleplayer_session_with_another_users_character(
    client, db_session, sample_user, sample_module, sample_character,
):
    intruder = await _register(client, "session_character_intruder")

    response = await client.post(
        "/game/sessions",
        headers=_h(intruder["token"]),
        json={
            "module_id": sample_module.id,
            "player_character_id": sample_character.id,
            "companion_ids": [],
        },
    )
    assert response.status_code == 403


async def test_user_cannot_submit_action_to_another_users_singleplayer_session(
    client, sample_session,
):
    intruder = await _register(client, "action_intruder")

    response = await client.post(
        "/game/action",
        headers=_h(intruder["token"]),
        json={
            "session_id": sample_session.id,
            "action_text": "open the locked door",
        },
    )
    assert response.status_code == 403


async def test_user_cannot_attack_or_smite_in_another_users_singleplayer_combat(
    client, db_session, sample_session, sample_character,
):
    intruder = await _register(client, "combat_action_intruder")

    sample_character.char_class = "Paladin"
    sample_character.spell_slots = {"1st": 1}
    sample_session.combat_active = True
    sample_session.game_state = {
        **(sample_session.game_state or {}),
        "enemies": [{
            "id": "skeleton-1",
            "name": "skeleton",
            "hp_current": 9,
            "max_hp": 9,
            "derived": {"hp_max": 9, "ac": 13, "ability_modifiers": {"dex": 1}},
        }],
    }
    flag_modified(sample_session, "game_state")
    combat = CombatState(
        id=str(uuid.uuid4()),
        session_id=sample_session.id,
        entity_positions={
            sample_character.id: {"x": 5, "y": 5},
            "skeleton-1": {"x": 6, "y": 5},
        },
        turn_order=[
            {"character_id": sample_character.id, "name": sample_character.name, "initiative": 16, "is_player": True, "is_enemy": False},
            {"character_id": "skeleton-1", "name": "skeleton", "initiative": 10, "is_player": False, "is_enemy": True},
        ],
        current_turn_index=0,
        round_number=1,
        turn_states={},
    )
    db_session.add(combat)
    await db_session.commit()

    attack = await client.post(
        f"/game/combat/{sample_session.id}/action",
        headers=_h(intruder["token"]),
        json={"action_text": "attack", "target_id": "skeleton-1"},
    )
    assert attack.status_code == 403

    smite = await client.post(
        f"/game/combat/{sample_session.id}/smite",
        headers=_h(intruder["token"]),
        json={"slot_level": 1, "target_id": "skeleton-1", "damage_values": [4]},
    )
    assert smite.status_code == 403

    await db_session.refresh(sample_character)
    assert sample_character.spell_slots["1st"] == 1


async def test_same_owner_cannot_mix_combat_actor_or_target_ids_between_sessions(
    client, db_session, sample_module,
):
    owner = await _register(client, "same_owner_combat_boundary")
    session_a, char_a, _combat_a, _session_b, char_b = await _seed_two_owned_combats(
        db_session,
        user_id=owner["user_id"],
        module_id=sample_module.id,
    )
    headers = _h(owner["token"])

    skill_bar = await client.get(
        f"/game/combat/{session_a.id}/skill-bar",
        headers=headers,
        params={"entity_id": char_b.id},
    )
    assert skill_bar.status_code == 403

    condition = await client.post(
        f"/game/combat/{session_a.id}/condition/add",
        headers=headers,
        json={"entity_id": char_b.id, "condition": "poisoned", "is_enemy": False},
    )
    assert condition.status_code == 403

    attack_target = await client.post(
        f"/game/combat/{session_a.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": char_a.id,
            "target_id": char_b.id,
            "action_type": "melee",
            "d20_value": 15,
        },
    )
    assert attack_target.status_code == 403

    attack_actor = await client.post(
        f"/game/combat/{session_a.id}/attack-roll",
        headers=headers,
        json={
            "entity_id": char_b.id,
            "target_id": "goblin-a",
            "action_type": "melee",
            "d20_value": 15,
        },
    )
    assert attack_actor.status_code == 403

    spell_target = await client.post(
        f"/game/combat/{session_a.id}/spell-roll",
        headers=headers,
        json={
            "caster_id": char_a.id,
            "spell_name": "魔法飞弹",
            "spell_level": 1,
            "target_id": char_b.id,
        },
    )
    assert spell_target.status_code == 403

    spell_actor = await client.post(
        f"/game/combat/{session_a.id}/spell-roll",
        headers=headers,
        json={
            "caster_id": char_b.id,
            "spell_name": "魔法飞弹",
            "spell_level": 1,
            "target_id": "goblin-a",
        },
    )
    assert spell_actor.status_code == 403

    direct_spell = await client.post(
        f"/game/combat/{session_a.id}/spell",
        headers=headers,
        json={
            "caster_id": char_a.id,
            "spell_name": "魔法飞弹",
            "spell_level": 1,
            "target_id": char_b.id,
        },
    )
    assert direct_spell.status_code == 403

    predict_target = await client.post(
        f"/game/combat/{session_a.id}/predict",
        headers=headers,
        json={"attacker_id": char_a.id, "target_id": char_b.id, "action_key": "atk"},
    )
    assert predict_target.status_code == 403

    predict_actor = await client.post(
        f"/game/combat/{session_a.id}/predict",
        headers=headers,
        json={"attacker_id": char_b.id, "target_id": "goblin-a", "action_key": "atk"},
    )
    assert predict_actor.status_code == 403

    grapple = await client.post(
        f"/game/combat/{session_a.id}/grapple-shove",
        headers=headers,
        json={"action_type": "grapple", "target_id": char_b.id},
    )
    assert grapple.status_code == 403

    maneuver = await client.post(
        f"/game/combat/{session_a.id}/maneuver",
        headers=headers,
        json={"maneuver_name": "trip", "target_id": char_b.id},
    )
    assert maneuver.status_code == 403

    await db_session.refresh(char_a)
    await db_session.refresh(char_b)
    assert char_a.spell_slots["1st"] == 1
    assert char_a.class_resources["superiority_dice_remaining"] == 1
    assert char_b.conditions in (None, [])


async def test_pending_combat_confirm_steps_reject_cross_session_targets(
    client, db_session, sample_module,
):
    owner = await _register(client, "same_owner_pending_boundary")
    session_a, char_a, combat_a, _session_b, char_b = await _seed_two_owned_combats(
        db_session,
        user_id=owner["user_id"],
        module_id=sample_module.id,
    )
    pending_attack_id = str(uuid.uuid4())
    pending_spell_id = str(uuid.uuid4())
    combat_a.turn_states = {
        char_a.id: {
            "attacks_made": 1,
            "pending_attack": {
                "pending_attack_id": pending_attack_id,
                "attacker_id": char_a.id,
                "target_id": char_b.id,
                "target_name": char_b.name,
                "target_is_enemy": False,
                "hit": True,
                "is_crit": False,
                "is_ranged": False,
                "hit_die": 8,
                "dmg_mod": 3,
                "attack_roll": {
                    "d20": 15,
                    "attack_bonus": 5,
                    "attack_total": 20,
                    "target_ac": 16,
                    "hit": True,
                    "is_crit": False,
                    "is_fumble": False,
                },
            },
            "pending_spell": {
                "pending_spell_id": pending_spell_id,
                "caster_id": char_a.id,
                "spell_name": "魔法飞弹",
                "spell_level": 1,
                "target_ids": [char_b.id],
                "is_cantrip": False,
                "is_aoe": False,
                "spell_type": "damage",
            },
        }
    }
    await db_session.commit()

    headers = _h(owner["token"])
    damage = await client.post(
        f"/game/combat/{session_a.id}/damage-roll",
        headers=headers,
        json={"pending_attack_id": pending_attack_id, "damage_values": [4]},
    )
    assert damage.status_code == 403

    confirm = await client.post(
        f"/game/combat/{session_a.id}/spell-confirm",
        headers=headers,
        json={"pending_spell_id": pending_spell_id, "damage_values": [1, 1, 1]},
    )
    assert confirm.status_code == 403

    await db_session.refresh(char_a)
    await db_session.refresh(char_b)
    assert char_a.spell_slots["1st"] == 1
    assert char_b.hp_current == 18


async def test_multiplayer_session_delete_endpoint_does_not_bypass_room_lifecycle(
    client, db_session, sample_module,
):
    host = await _register(client, "delete_boundary_host")
    guest = await _register(client, "delete_boundary_guest")

    created = (await client.post(
        "/game/rooms/create",
        headers=_h(host["token"]),
        json={"module_id": sample_module.id, "save_name": "delete boundary", "max_players": 4},
    )).json()
    session_id = created["session_id"]
    join = await client.post(
        "/game/rooms/join",
        headers=_h(guest["token"]),
        json={"room_code": created["room_code"]},
    )
    assert join.status_code == 200, join.text

    response = await client.delete(
        f"/game/sessions/{session_id}",
        headers=_h(host["token"]),
    )
    assert response.status_code == 400

    session = await db_session.get(Session, session_id)
    assert session is not None
    assert session.is_multiplayer is True
    assert session.room_code == created["room_code"]

    members = await db_session.execute(
        select(SessionMember).where(SessionMember.session_id == session_id)
    )
    assert len(list(members.scalars().all())) == 2
