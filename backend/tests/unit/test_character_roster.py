"""
单元测试：P1 新增的 CharacterRoster service。

验证：
  - companion_ids() 正确从 session.game_state 读取
  - companions() 按顺序加载、跳过已删除
  - party() = [player] + companions
  - allies_alive() / companions_alive() 过滤 hp_current=0
  - bind_companions() 绑定 session_id
  - delete_ai_companions() 删 is_player=False 的，不碰玩家
"""
import pytest
import pytest_asyncio
from services.character_roster import CharacterRoster


@pytest_asyncio.fixture
async def roster(db_session, sample_session):
    return CharacterRoster(db_session, sample_session)


async def test_companion_ids_empty(roster):
    """新 session 没队友时返回空列表。"""
    assert roster.companion_ids() == []


async def test_player(roster, sample_character):
    p = await roster.player()
    assert p is not None
    assert p.id == sample_character.id


async def test_party_only_player(roster, sample_character):
    """没有 AI 队友时，party() 只返回玩家。"""
    party = await roster.party()
    assert len(party) == 1
    assert party[0].id == sample_character.id


async def test_companions_with_fixtures(db_session, sample_session):
    """手动往 session 里塞两个 AI 队友，companions() 应返回它们。"""
    from models import Character
    from sqlalchemy.orm.attributes import flag_modified
    import uuid as _uuid

    c1 = Character(
        id=str(_uuid.uuid4()), name="AI 法师",
        race="Elf", char_class="Wizard", level=1,
        ability_scores={"str": 8, "dex": 14, "con": 13, "int": 16, "wis": 12, "cha": 10},
        hp_current=6, is_player=False, session_id=sample_session.id,
    )
    c2 = Character(
        id=str(_uuid.uuid4()), name="AI 牧师",
        race="Dwarf", char_class="Cleric", level=1,
        ability_scores={"str": 14, "dex": 10, "con": 15, "int": 10, "wis": 16, "cha": 12},
        hp_current=10, is_player=False, session_id=sample_session.id,
    )
    db_session.add_all([c1, c2])
    sample_session.game_state = {
        **(sample_session.game_state or {}),
        "companion_ids": [c1.id, c2.id],
    }
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    roster = CharacterRoster(db_session, sample_session)
    comps = await roster.companions()
    assert [c.id for c in comps] == [c1.id, c2.id]

    party = await roster.party()
    assert len(party) == 3  # 玩家 + 2 AI


async def test_companions_alive_filters_dead(db_session, sample_session):
    """hp=0 的队友应该被过滤掉。"""
    from models import Character
    from sqlalchemy.orm.attributes import flag_modified
    import uuid as _uuid

    alive = Character(
        id=str(_uuid.uuid4()), name="活着的",
        race="Human", char_class="Fighter", level=1,
        ability_scores={}, hp_current=5, is_player=False, session_id=sample_session.id,
    )
    dead = Character(
        id=str(_uuid.uuid4()), name="倒下的",
        race="Human", char_class="Fighter", level=1,
        ability_scores={}, hp_current=0, is_player=False, session_id=sample_session.id,
    )
    db_session.add_all([alive, dead])
    sample_session.game_state = {**sample_session.game_state, "companion_ids": [alive.id, dead.id]}
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    roster = CharacterRoster(db_session, sample_session)
    assert [c.id for c in await roster.companions_alive()] == [alive.id]


async def test_companions_skip_deleted(db_session, sample_session):
    """companion_ids 里有不存在的 id 时，应该跳过而不是抛错。"""
    from sqlalchemy.orm.attributes import flag_modified
    sample_session.game_state = {
        **sample_session.game_state,
        "companion_ids": ["nonexistent-id-1", "nonexistent-id-2"],
    }
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    roster = CharacterRoster(db_session, sample_session)
    comps = await roster.companions()
    assert comps == []


async def test_bind_companions(db_session, sample_session):
    """bind_companions 把角色的 session_id 指向当前 session。"""
    from models import Character
    import uuid as _uuid

    orphan = Character(
        id=str(_uuid.uuid4()), name="流浪的",
        race="Elf", char_class="Rogue", level=1,
        ability_scores={}, hp_current=7, is_player=False, session_id=None,
    )
    db_session.add(orphan)
    await db_session.commit()

    roster = CharacterRoster(db_session, sample_session)
    await roster.bind_companions([orphan.id])
    await db_session.commit()
    await db_session.refresh(orphan)
    assert orphan.session_id == sample_session.id


async def test_delete_ai_companions_preserves_player(
    db_session, sample_session, sample_character,
):
    """delete_ai_companions 只删 is_player=False 的。"""
    from models import Character
    from sqlalchemy.orm.attributes import flag_modified
    import uuid as _uuid

    ai = Character(
        id=str(_uuid.uuid4()), name="AI 狂战",
        race="Half-Orc", char_class="Barbarian", level=1,
        ability_scores={}, hp_current=15, is_player=False, session_id=sample_session.id,
    )
    db_session.add(ai)
    sample_session.game_state = {
        **sample_session.game_state,
        # player 也放进来测试"玩家不被误删"
        "companion_ids": [sample_character.id, ai.id],
    }
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    roster = CharacterRoster(db_session, sample_session)
    deleted = await roster.delete_ai_companions()
    await db_session.commit()

    assert deleted == 1  # 只 AI 被删
    # 玩家角色应该仍然存在
    from sqlalchemy import select
    res = await db_session.execute(select(Character).where(Character.id == sample_character.id))
    assert res.scalar_one_or_none() is not None
    # AI 应该不在
    res = await db_session.execute(select(Character).where(Character.id == ai.id))
    assert res.scalar_one_or_none() is None


async def test_caching(roster):
    """第二次调用 companions() 应该走缓存，不重新查询。"""
    first  = await roster.companions()
    second = await roster.companions()
    # 不是等 "list equality"，是等 "同一个对象"（来自 _companions_cache）
    assert first is second
