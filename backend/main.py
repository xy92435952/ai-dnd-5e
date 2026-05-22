from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import hashlib
from pathlib import Path

from config import settings
from database import init_db
from api.auth import router as auth_router
from api.modules import router as modules_router
from api.character_inventory import router as character_inventory_router
from api.characters import router as characters_router
from api.game import router as game_router
from api.combat import router as combat_router
from api.rooms import router as rooms_router
from api.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # 初始化 LangGraph 对话记忆
    from services.graphs.dm_agent import initialize_memory
    await initialize_memory()
    yield


app = FastAPI(
    title="AI TRPG Backend",
    description="DnD 5e AI跑团平台后端",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS：从 .env 的 CORS_ALLOW_ORIGINS 读取白名单。
# 生产环境应明确列出实际前端域名；不要使用 "*"（与 allow_credentials=True 不兼容）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _rate_limit_policy(path: str) -> int:
    if path.startswith("/auth/"):
        return settings.rate_limit_auth_per_minute
    if path.startswith("/game/action") or path.startswith("/modules/upload"):
        return settings.rate_limit_game_per_minute
    return settings.rate_limit_default_per_minute


@app.middleware("http")
async def beta_rate_limit_middleware(request, call_next):
    if not settings.rate_limit_enabled:
        return await call_next(request)

    from services.rate_limit_service import RateLimitExceeded, rate_limiter

    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = (forwarded_for.split(",")[0].strip() if forwarded_for else "") or (
        request.client.host if request.client else "unknown"
    )
    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
    token_key = hashlib.sha256(token.encode("utf-8")).hexdigest()[:32] if token else ""
    key = f"token:{token_key}" if token_key else f"ip:{client_ip}"

    try:
        rate_limiter.check(
            f"{key}:{request.url.path}",
            limit=_rate_limit_policy(request.url.path),
            window_seconds=60,
        )
    except RateLimitExceeded as exc:
        return JSONResponse(
            status_code=429,
            content={"detail": "请求过于频繁，请稍后再试"},
            headers={"Retry-After": str(exc.retry_after)},
        )

    return await call_next(request)

app.include_router(auth_router)
app.include_router(modules_router)
app.include_router(character_inventory_router)
app.include_router(characters_router)
app.include_router(game_router)
app.include_router(combat_router)
app.include_router(rooms_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


def _readiness_problems() -> list[str]:
    problems: list[str] = []
    if settings.is_production:
        if settings.database_url.startswith("sqlite"):
            problems.append("生产环境必须使用 PostgreSQL DATABASE_URL")
        if not settings.jwt_secret or len(settings.jwt_secret) < 32:
            problems.append("生产环境必须设置至少 32 字节的 JWT_SECRET")

    upload_dir = Path(settings.upload_dir)
    if not upload_dir.exists():
        problems.append(f"上传目录不存在: {settings.upload_dir}")
    elif not upload_dir.is_dir():
        problems.append(f"上传路径不是目录: {settings.upload_dir}")

    return problems


@app.get("/ready")
async def ready():
    from services.background_job_limits import module_parse_limiter
    from services.session_action_lock import session_action_lock_stats
    from services.ws_manager import ws_manager

    problems = _readiness_problems()
    payload = {
        "status": "not_ready" if problems else "ready",
        "problems": problems,
        "env": settings.env,
        "database": {
            "kind": "sqlite" if settings.database_url.startswith("sqlite") else "postgresql",
        },
        "beta": {
            "max_users": settings.beta_max_users,
            "max_ws_connections": settings.beta_max_ws_connections,
            "rate_limit_enabled": settings.rate_limit_enabled,
            "module_parse_max_concurrent": settings.module_parse_max_concurrent,
            "module_parse_max_backlog": settings.module_parse_max_backlog,
        },
        "background_jobs": {
            "module_parse": module_parse_limiter.stats(),
        },
        "session_action_locks": session_action_lock_stats(),
        "ws": ws_manager.stats(),
    }
    if problems:
        return JSONResponse(status_code=503, content=payload)
    return payload
