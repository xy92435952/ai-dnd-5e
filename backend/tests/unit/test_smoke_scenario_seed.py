from sqlalchemy import func, select

from models import Character, CombatState, GameLog, Module, Session, User
from services.smoke_scenario_seed import seed_smoke_scenario


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
