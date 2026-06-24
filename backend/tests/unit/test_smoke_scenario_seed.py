from sqlalchemy import event, func, select

from models import Character, CombatState, GameLog, Module, Session, User
from services.smoke_scenario_seed import (
    STAGE7_5_COMBAT_CHOICE_TEXT,
    STAGE7_5_GOLD_LOOT_ID,
    STAGE7_5_TOKEN_LOOT_ID,
    seed_smoke_scenario,
)


async def _count(db_session, model) -> int:
    result = await db_session.execute(select(func.count()).select_from(model))
    return int(result.scalar_one())


async def test_seed_smoke_scenario_creates_repeatable_playable_state(db_session):
    result = await seed_smoke_scenario(db_session, slug="Codex Smoke")

    user = await db_session.get(User, result.user_id)
    module = await db_session.get(Module, result.module_id)
    hero = await db_session.get(Character, result.character_id)
    companion = await db_session.get(Character, result.companion_ids[0])
    session = await db_session.get(Session, result.session_id)
    combat = await db_session.get(CombatState, result.combat_state_id)
    logs = (
        await db_session.execute(
            select(GameLog).where(GameLog.session_id == result.session_id)
        )
    ).scalars().all()

    assert result.slug == "codex_smoke"
    assert result.variant == "standard"
    assert result.username == "test_codex_smoke"
    assert user.username == result.username
    assert module.name == "__test_module_smoke_codex_smoke"
    assert module.parse_status == "done"
    assert module.parsed_content["monsters"][0]["name"] == "Clockwork Training Construct"
    assert hero.user_id == user.id
    assert hero.session_id == session.id
    assert hero.derived["ac"] >= 18
    assert hero.equipment["weapons"]
    assert companion.is_player is False
    assert companion.personality
    assert session.combat_active is True
    assert session.game_state["scenario_seed"] == {"slug": "codex_smoke", "version": 1}
    assert session.game_state["trap_states"]["gatehouse_tripwire"]["armed"] is True
    assert session.campaign_state["quest_log"][0]["quest"] == "Stabilize the Clockwork Crossing"
    assert len(session.game_state["enemies"]) == 2
    assert combat.entity_positions[result.character_id] == {"x": 3, "y": 5}
    assert "enemy_smoke_construct" in combat.turn_states
    assert len(combat.turn_order) == 4
    assert len(logs) == 2


async def test_seed_smoke_scenario_can_prepare_death_save_variant(db_session):
    result = await seed_smoke_scenario(db_session, slug="death save qa", variant="death-save")

    hero = await db_session.get(Character, result.character_id)
    session = await db_session.get(Session, result.session_id)
    combat = await db_session.get(CombatState, result.combat_state_id)

    current = combat.turn_order[combat.current_turn_index]
    assert result.variant == "death_save"
    assert hero.hp_current == 0
    assert hero.death_saves == {"successes": 1, "failures": 1, "stable": False}
    assert current["character_id"] == result.character_id
    assert session.game_state["scenario_seed_variant"] == "death_save"
    assert "death-save UI checks" in combat.combat_log[-1]


async def test_seed_smoke_scenario_can_prepare_reaction_variant(db_session):
    result = await seed_smoke_scenario(db_session, slug="reaction qa", variant="reaction")

    hero = await db_session.get(Character, result.character_id)
    session = await db_session.get(Session, result.session_id)
    combat = await db_session.get(CombatState, result.combat_state_id)
    turn_state = combat.turn_states[result.character_id]
    pending = turn_state["pending_attack_reaction"]
    current = combat.turn_order[combat.current_turn_index]

    assert result.variant == "reaction"
    assert "Shield" in hero.known_spells
    assert hero.spell_slots["1st"] == 1
    assert hero.hp_current == hero.derived["hp_max"] - 9
    assert current["character_id"] == result.character_id
    assert session.game_state["scenario_seed_variant"] == "reaction"
    assert pending["trigger"] == "incoming_attack"
    assert pending["reactor_character_id"] == result.character_id
    assert pending["available_reactions"][0]["type"] == "shield"
    assert pending["options"][0]["character_id"] == result.character_id


async def test_seed_smoke_scenario_can_prepare_feather_fall_variant(db_session):
    result = await seed_smoke_scenario(
        db_session,
        slug="feather fall qa",
        variant="feather-fall",
    )

    hero = await db_session.get(Character, result.character_id)
    companion = await db_session.get(Character, result.companion_ids[0])
    session = await db_session.get(Session, result.session_id)
    combat = await db_session.get(CombatState, result.combat_state_id)
    prompt = session.game_state["pending_exploration_reaction"]

    assert result.variant == "feather_fall"
    assert session.combat_active is False
    assert session.game_state["scenario_seed_variant"] == "feather_fall"
    assert companion.char_class == "Wizard"
    assert "Feather Fall" in companion.known_spells
    assert companion.spell_slots["1st"] == 1
    assert hero.hp_current == hero.derived["hp_max"]
    assert prompt["type"] == "feather_fall"
    assert prompt["reactor_character_id"] == companion.id
    assert prompt["reactor_user_id"] == result.user_id
    assert prompt["target_character_id"] == hero.id
    assert prompt["damage_before"] == 6
    assert prompt["damage_prevented"] == 6
    assert prompt["trap_resolution"]["final_damage"] == 6
    assert session.game_state["last_turn"]["pending_exploration_reaction_id"] == prompt["id"]
    assert "Feather Fall prompt" in combat.combat_log[-1]


async def test_seed_smoke_scenario_can_prepare_stage7_5_variant(db_session):
    result = await seed_smoke_scenario(
        db_session,
        slug="stage7_5_launch",
        variant="stage7-5",
    )

    session = await db_session.get(Session, result.session_id)
    combat = await db_session.get(CombatState, result.combat_state_id)
    loot_items = session.game_state["loot_pool"]["items"]

    assert result.variant == "stage7_5"
    assert result.stage7_5["exploration_session_id"] == result.session_id
    assert result.stage7_5["combat_session_id"] == result.session_id
    assert result.stage7_5["combat_choice_text"] == STAGE7_5_COMBAT_CHOICE_TEXT
    assert "--username test --password 123456" in result.stage7_5["reset_command"]
    assert session.combat_active is False
    assert session.game_state["scenario_seed_variant"] == "stage7_5"
    assert session.game_state["stage7_5_progress"] == "exploration_ready"
    assert session.game_state["last_turn"]["player_choices"][0]["text"] == STAGE7_5_COMBAT_CHOICE_TEXT
    assert {item["id"] for item in loot_items} >= {STAGE7_5_GOLD_LOOT_ID, STAGE7_5_TOKEN_LOOT_ID}
    assert all(item["status"] == "available" for item in loot_items if item["id"] in {STAGE7_5_GOLD_LOOT_ID, STAGE7_5_TOKEN_LOOT_ID})
    assert combat.turn_order == []
    assert combat.entity_positions == {}


async def test_seed_smoke_scenario_can_attach_stage7_5_to_existing_user(db_session):
    existing = User(
        id="existing-user",
        username="test",
        password_hash="old-hash",
        display_name="Existing Test User",
    )
    db_session.add(existing)
    await db_session.commit()

    result = await seed_smoke_scenario(
        db_session,
        slug="stage7_5_launch",
        variant="stage7-5",
        username="test",
        password="123456",
    )

    user = await db_session.get(User, "existing-user")
    session = await db_session.get(Session, result.session_id)
    module = await db_session.get(Module, result.module_id)
    hero = await db_session.get(Character, result.character_id)

    assert result.user_id == "existing-user"
    assert result.username == "test"
    assert user.password_hash != "old-hash"
    assert session.user_id == "existing-user"
    assert module.user_id == "existing-user"
    assert hero.user_id == "existing-user"


async def test_seed_smoke_scenario_flushes_fk_parents_before_dependents(db_session, engine):
    insert_tables = []

    def record_insert_order(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("insert into "):
            table_name = normalized.split()[2].strip('"')
            insert_tables.append(table_name)

    event.listen(engine.sync_engine, "before_cursor_execute", record_insert_order)
    try:
        await seed_smoke_scenario(db_session, slug="postgres fk order")
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record_insert_order)

    first_insert = {
        table_name: insert_tables.index(table_name)
        for table_name in set(insert_tables)
    }
    assert first_insert["modules"] < first_insert["sessions"]
    assert first_insert["users"] < first_insert["characters"]
    assert first_insert["sessions"] < first_insert["characters"]
    assert first_insert["sessions"] < first_insert["combat_states"]
    assert first_insert["sessions"] < first_insert["game_logs"]


async def test_seed_smoke_scenario_is_idempotent_for_same_slug(db_session):
    first = await seed_smoke_scenario(db_session, slug="repeatable")
    second = await seed_smoke_scenario(db_session, slug="repeatable")

    assert second.as_dict() == first.as_dict()
    assert await _count(db_session, User) == 1
    assert await _count(db_session, Module) == 1
    assert await _count(db_session, Character) == 2
    assert await _count(db_session, Session) == 1
    assert await _count(db_session, CombatState) == 1
    assert await _count(db_session, GameLog) == 2


async def test_seed_smoke_scenario_uses_cleanup_script_prefixes(db_session):
    result = await seed_smoke_scenario(db_session, slug="Manual QA")

    user = await db_session.get(User, result.user_id)
    module = await db_session.get(Module, result.module_id)

    assert user.username.startswith("test_")
    assert module.name.startswith("__test_module")
