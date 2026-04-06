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

    class Config:
        env_file = ".env"


settings = Settings()

# 确保上传目录存在
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
