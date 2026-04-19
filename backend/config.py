from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # LLM（OpenAI 兼容 API）
    llm_api_key: str = ""
    llm_base_url: str = "https://aihubmix.com/v1"
    llm_model: str = "claude-sonnet-4-6"

    # ChromaDB（本地 RAG 向量库）
    chromadb_path: str = "./chromadb_data"

    # LangGraph 对话记忆
    langgraph_db_path: str = "./langgraph_memory.db"       # SQLite（本地开发）
    langgraph_db_url: str = ""                              # PostgreSQL（生产环境，留空则用 SQLite）

    database_url: str = "sqlite+aiosqlite:///./ai_trpg.db"
    upload_dir: str = "./uploads"
    max_upload_mb: int = 50

    # 安全配置（v0.10 上线硬化）
    # JWT 签名密钥：务必在 .env 中设置为独立的强随机值（≥32 字节）
    # 留空时 auth.py 会降级使用 llm_api_key 派生（仅限开发）
    jwt_secret: str = ""
    # 允许的前端源（CORS 白名单）；逗号分隔；生产环境应只列实际域名
    # 开发默认：localhost:3000/5173；生产改成实际域名
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173"
    # 部署环境：development / production
    env: str = "development"

    class Config:
        env_file = ".env"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


settings = Settings()

# 确保上传目录存在
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
