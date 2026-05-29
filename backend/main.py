import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from database import AsyncSessionLocal


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # 初始化 LangGraph 对话记忆
    from services.graphs.dm_agent import initialize_memory
    await initialize_memory()
    cleanup_task = None
    if settings.enable_ws_stale_cleanup:
        cleanup_task = asyncio.create_task(_ws_stale_cleanup_loop())
    yield
    if cleanup_task is not None:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


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


async def _ws_stale_cleanup_loop():
    from services.ws_cleanup_service import cleanup_stale_ws_connections

    interval = max(5, int(settings.ws_stale_cleanup_interval_seconds))
    stale_after = max(1, int(settings.ws_stale_disconnect_after_seconds))

    while True:
        await asyncio.sleep(interval)
        try:
            async with AsyncSessionLocal() as db:
                await cleanup_stale_ws_connections(
                    db,
                    stale_after_seconds=stale_after,
                )
        except Exception as exc:
            logger.warning("WS stale cleanup loop failed: %s", exc)
