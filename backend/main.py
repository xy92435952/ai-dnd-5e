from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_db
from api.auth import router as auth_router
from api.modules import router as modules_router
from api.characters import router as characters_router
from api.game import router as game_router
from api.combat import router as combat_router


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(modules_router)
app.include_router(characters_router)
app.include_router(game_router)
app.include_router(combat_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
