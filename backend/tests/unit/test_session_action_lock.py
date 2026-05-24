import asyncio

import pytest

from services.session_action_lock import session_action_lock


@pytest.mark.asyncio
async def test_session_action_lock_serializes_same_session():
    entered = asyncio.Event()
    release_first = asyncio.Event()
    order = []

    async def first():
        async with session_action_lock("lock-same-session"):
            order.append("first-enter")
            entered.set()
            await release_first.wait()
            order.append("first-exit")

    async def second():
        await entered.wait()
        async with session_action_lock("lock-same-session"):
            order.append("second-enter")

    first_task = asyncio.create_task(first())
    second_task = asyncio.create_task(second())

    await entered.wait()
    await asyncio.sleep(0.01)
    assert order == ["first-enter"]

    release_first.set()
    await asyncio.wait_for(asyncio.gather(first_task, second_task), timeout=1)
    assert order == ["first-enter", "first-exit", "second-enter"]


@pytest.mark.asyncio
async def test_session_action_lock_allows_different_sessions_in_parallel():
    release_first = asyncio.Event()
    second_entered = asyncio.Event()
    order = []

    async def first():
        async with session_action_lock("lock-room-a"):
            order.append("first-enter")
            await release_first.wait()

    async def second():
        async with session_action_lock("lock-room-b"):
            order.append("second-enter")
            second_entered.set()

    first_task = asyncio.create_task(first())
    await asyncio.sleep(0.01)
    second_task = asyncio.create_task(second())

    await asyncio.wait_for(second_entered.wait(), timeout=1)
    assert order == ["first-enter", "second-enter"]

    release_first.set()
    await asyncio.wait_for(asyncio.gather(first_task, second_task), timeout=1)
