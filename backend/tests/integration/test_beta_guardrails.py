import pytest

from config import settings
from services.background_job_limits import module_parse_limiter
from services.rate_limit_service import rate_limiter


async def _auth_headers(client, sample_user):
    resp = await client.post("/auth/login", json={
        "username": sample_user.username,
        "password": "password",
    })
    return {"Authorization": f"Bearer {resp.json()['token']}"}


@pytest.mark.asyncio
async def test_rate_limit_middleware_returns_429(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_default_per_minute", 1)
    monkeypatch.setattr(settings, "rate_limit_auth_per_minute", 1)
    monkeypatch.setattr(settings, "rate_limit_game_per_minute", 1)
    rate_limiter.clear()

    first = await client.get("/health")
    second = await client.get("/health")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"] == "请求过于频繁，请稍后再试"
    assert int(second.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_rate_limit_middleware_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_default_per_minute", 1)
    rate_limiter.clear()

    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/health")).status_code == 200


@pytest.mark.asyncio
async def test_ready_reports_beta_limits_and_ws_status(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "beta_max_users", 50)
    monkeypatch.setattr(settings, "beta_max_ws_connections", 80)
    module_parse_limiter.clear()

    resp = await client.get("/ready")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ready"
    assert payload["beta"]["max_users"] == 50
    assert payload["beta"]["max_ws_connections"] == 80
    assert "ws" in payload
    assert payload["background_jobs"]["module_parse"] == {"queued": 0, "running": 0}


@pytest.mark.asyncio
async def test_ready_fails_production_sqlite(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "database_url", "sqlite+aiosqlite:///./ai_trpg.db")
    monkeypatch.setattr(settings, "jwt_secret", "x" * 40)

    resp = await client.get("/ready")

    assert resp.status_code == 503
    payload = resp.json()
    assert payload["status"] == "not_ready"
    assert any("PostgreSQL" in item for item in payload["problems"])


@pytest.mark.asyncio
async def test_ready_fails_production_weak_jwt_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "database_url", "postgresql+asyncpg://u:p@db/app")
    monkeypatch.setattr(settings, "jwt_secret", "short")

    resp = await client.get("/ready")

    assert resp.status_code == 503
    payload = resp.json()
    assert payload["status"] == "not_ready"
    assert any("JWT_SECRET" in item for item in payload["problems"])


@pytest.mark.asyncio
async def test_module_upload_returns_429_when_parse_backlog_is_full(client, monkeypatch, sample_user):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "module_parse_max_backlog", 1)
    module_parse_limiter.clear()
    reservation = module_parse_limiter.reserve(max_backlog=1)
    headers = await _auth_headers(client, sample_user)

    try:
        resp = await client.post(
            "/modules/upload",
            files={"file": ("demo.txt", b"hello", "text/plain")},
            headers=headers,
        )
    finally:
        reservation.release()
        module_parse_limiter.clear()

    assert resp.status_code == 429
    assert resp.json()["detail"] == "后台解析队列已满，请稍后再上传"
