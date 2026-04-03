"""
本地 RAG 检索服务（ChromaDB）
==============================
替换 DifyRagService，实现 BaseRagService 接口。
使用 ChromaDB metadata 过滤（where={"module_id": ...}）实现 per-module 隔离。
"""

import logging
import asyncio
from typing import Optional

from services.rag_service import BaseRagService
from config import settings

logger = logging.getLogger(__name__)


def _get_chroma_collection(name: str = "module_chunks"):
    import chromadb
    client = chromadb.PersistentClient(path=settings.chromadb_path)
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


class LocalRagService(BaseRagService):
    """基于 ChromaDB 的本地 RAG 服务。"""

    async def retrieve_module_context(
        self,
        query: str,
        module_id: str,
        top_k: int = 3,
        score_threshold: float = 0.4,
    ) -> str:
        try:
            collection = await asyncio.to_thread(_get_chroma_collection, "module_chunks")

            results = await asyncio.to_thread(
                collection.query,
                query_texts=[query],
                where={"module_id": module_id},
                n_results=top_k,
            )

            documents = results.get("documents", [[]])[0]
            if not documents:
                return ""

            return "\n---\n".join(documents)
        except Exception as e:
            logger.warning(f"模组 RAG 检索失败: {e}")
            return ""

    async def retrieve_history_context(
        self,
        query: str,
        session_id: str,
        top_k: int = 3,
        score_threshold: float = 0.4,
    ) -> str:
        # 历史事件知识库暂未实现，返回空串
        return ""
