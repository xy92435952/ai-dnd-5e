from services.rate_limit_service import InMemoryRateLimiter, RateLimitExceeded


def test_rate_limiter_allows_within_limit_and_blocks_over_limit():
    limiter = InMemoryRateLimiter(now=lambda: 100.0)

    limiter.check("user:1", limit=2, window_seconds=60)
    limiter.check("user:1", limit=2, window_seconds=60)

    try:
        limiter.check("user:1", limit=2, window_seconds=60)
    except RateLimitExceeded as exc:
        assert exc.retry_after == 60
    else:
        raise AssertionError("expected rate limit to be exceeded")


def test_rate_limiter_resets_after_window():
    now = {"value": 100.0}
    limiter = InMemoryRateLimiter(now=lambda: now["value"])

    limiter.check("ip:127.0.0.1", limit=1, window_seconds=10)
    now["value"] = 111.0
    limiter.check("ip:127.0.0.1", limit=1, window_seconds=10)


def test_rate_limiter_can_be_cleared_for_tests_and_redeploys():
    limiter = InMemoryRateLimiter(now=lambda: 100.0)
    limiter.check("user:1", limit=1, window_seconds=60)
    limiter.clear()

    limiter.check("user:1", limit=1, window_seconds=60)
