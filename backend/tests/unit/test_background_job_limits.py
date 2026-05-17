import asyncio

import pytest

from services.background_job_limits import BackgroundJobLimiter, JobLimitExceeded


def test_background_job_limiter_reserves_and_releases_backlog():
    limiter = BackgroundJobLimiter()

    reservation = limiter.reserve(max_backlog=1)
    assert limiter.stats() == {"queued": 1, "running": 0}

    reservation.release()
    assert limiter.stats() == {"queued": 0, "running": 0}


def test_background_job_limiter_blocks_when_backlog_is_full():
    limiter = BackgroundJobLimiter()
    limiter.reserve(max_backlog=1)

    try:
        limiter.reserve(max_backlog=1)
    except JobLimitExceeded as exc:
        assert exc.detail == "后台解析队列已满，请稍后再上传"
    else:
        raise AssertionError("expected backlog limit")


def test_background_job_limiter_release_is_idempotent():
    limiter = BackgroundJobLimiter()
    reservation = limiter.reserve(max_backlog=1)

    reservation.release()
    reservation.release()

    assert limiter.stats() == {"queued": 0, "running": 0}


@pytest.mark.asyncio
async def test_background_job_limiter_limits_concurrent_runs():
    limiter = BackgroundJobLimiter(poll_seconds=0.001)
    first = limiter.reserve(max_backlog=2)
    second = limiter.reserve(max_backlog=2)

    first_slot = await first.acquire_run_slot(max_concurrent=1)
    second_task = asyncio.create_task(second.acquire_run_slot(max_concurrent=1))
    await asyncio.sleep(0.01)

    assert second_task.done() is False
    assert limiter.stats() == {"queued": 2, "running": 1}

    first_slot.release()
    second_slot = await asyncio.wait_for(second_task, timeout=0.1)
    assert limiter.stats() == {"queued": 2, "running": 1}

    second_slot.release()
    first.release()
    second.release()
    assert limiter.stats() == {"queued": 0, "running": 0}
