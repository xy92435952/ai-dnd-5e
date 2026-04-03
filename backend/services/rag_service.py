"""
RAG 服务接口与实现
==================
支持两种检索场景：
  - 模组内容检索（module_retrieval）：玩家询问场景细节/NPC信息/物品描述时
  - 历史事件检索（history_retrieval）：玩家引用很久以前发生的事件时

激活方式：
  RagService      → 存根，返回空字符串（默认）
  DifyRagService  → 接入 Dify Cloud Knowledge Base，自动激活（当 config 中 KB 配置非空时）

模组 chunks 由 WF1 生成，通过 dify_rag_uploader.py 上传到 KB。
每个 chunk 的 content 第一行格式为「模组ID: {module_id}」，
retrieve 时按此前缀进行 Python 侧过滤，实现 per-module 隔离。
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 抽象接口
# ─────────────────────────────────────────────

class BaseRagService(ABC):

    @abstractmethod
    async def retrieve_module_context(
        self,
        query: str,
        module_id: str,
        top_k: int = 3,
        score_threshold: float = 0.4,
    ) -> str:
        """从模组知识库中检索与当前行动相关的片段。"""
        ...

    @abstractmethod
    async def retrieve_history_context(
        self,
        query: str,
        session_id: str,
        top_k: int = 3,
        score_threshold: float = 0.4,
    ) -> str:
        """从历史 GameLog 知识库中检索与当前行动相关的历史事件。"""
        ...

    async def retrieve(
        self,
        query: str,
        module_id: str,
        session_id: str,
        top_k: int = 3,
    ) -> str:
        """
        统一检索入口：合并模组内容检索 + 历史事件检索。
        ContextBuilder 调用此方法。
        """
        parts = []

        module_result = await self.retrieve_module_context(query, module_id, top_k)
        if module_result:
            parts.append(f"【模组相关内容】\n{module_result}")

        history_result = await self.retrieve_history_context(query, session_id, top_k)
        if history_result:
            parts.append(f"【历史关键事件】\n{history_result}")

        return "\n\n".join(parts)


# ─────────────────────────────────────────────
# 存根实现（未配置 KB 时使用）
# ─────────────────────────────────────────────

class RagService(BaseRagService):
    """存根 RAG 服务，所有方法返回空字符串。"""

    async def retrieve_module_context(self, query, module_id, top_k=3, score_threshold=0.4) -> str:
        return ""

    async def retrieve_history_context(self, query, session_id, top_k=3, score_threshold=0.4) -> str:
        return ""


# ─────────────────────────────────────────────
# Dify Knowledge Base 实现
# ─────────────────────────────────────────────

class DifyRagService(BaseRagService):
    """
    基于 Dify Knowledge Base API 的 RAG 实现。

    模组 chunks 格式（由 dify_rag_uploader.py 上传）：
      第一行: 模组ID: {module_id}
      第二行: 类型: {source_type}
      ...其余内容...

    检索时通过 Python 侧前缀匹配实现 per-module 隔离。
    """

    def __init__(self):
        try:
            from config import settings
            import httpx
            self.kb_base_url = settings.dify_kb_base_url.rstrip("/")
            self.knowledge_api_key = settings.dify_knowledge_api_key
            self.module_dataset_id = settings.dify_module_dataset_id
            self.history_dataset_id = settings.dify_history_dataset_id
            self._client = httpx.AsyncClient(timeout=15.0)
        except Exception as e:
            logger.warning(f"DifyRagService 初始化失败，退化为空返回: {e}")
            self._client = None

    async def retrieve_module_context(
        self,
        query: str,
        module_id: str,
        top_k: int = 3,
        score_threshold: float = 0.4,
    ) -> str:
        if not self._client or not self.module_dataset_id:
            return ""
        try:
            resp = await self._client.post(
                f"{self.kb_base_url}/datasets/{self.module_dataset_id}/retrieve",
                headers={"Authorization": f"Bearer {self.knowledge_api_key}"},
                json={
                    "query": query,
                    "retrieval_model": {
                        "search_method": "hybrid_search",
                        "top_k": top_k * 3,        # 多取以便过滤后仍有足够结果
                        "score_threshold_enabled": True,
                        "score_threshold": score_threshold,
                        "reranking_enable": False,
                    },
                },
            )
            resp.raise_for_status()
            records = resp.json().get("records", [])

            # Python 侧按 module_id 过滤：只保留本模组的 chunks
            module_marker = f"模组ID: {module_id}"
            chunks = []
            for r in records:
                content = (r.get("segment") or {}).get("content", "")
                if content and module_marker in content:
                    chunks.append(content)
                    if len(chunks) >= top_k:
                        break

            return "\n---\n".join(chunks)
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
        if not self._client or not self.history_dataset_id:
            return ""
        try:
            resp = await self._client.post(
                f"{self.kb_base_url}/datasets/{self.history_dataset_id}/retrieve",
                headers={"Authorization": f"Bearer {self.knowledge_api_key}"},
                json={
                    "query": query,
                    "retrieval_model": {
                        "search_method": "hybrid_search",
                        "top_k": top_k * 3,
                        "score_threshold_enabled": True,
                        "score_threshold": score_threshold,
                        "reranking_enable": False,
                    },
                },
            )
            resp.raise_for_status()
            records = resp.json().get("records", [])

            session_marker = f"会话ID: {session_id}"
            chunks = []
            for r in records:
                content = (r.get("segment") or {}).get("content", "")
                if content and session_marker in content:
                    chunks.append(content)
                    if len(chunks) >= top_k:
                        break

            return "\n---\n".join(chunks)
        except Exception as e:
            logger.warning(f"历史 RAG 检索失败: {e}")
            return ""


# ─────────────────────────────────────────────
# 工厂函数：根据配置自动选择实现
# ─────────────────────────────────────────────

def get_rag_service() -> BaseRagService:
    """
    自动选择 RAG 服务实现：
    - 配置了 chromadb_path → LocalRagService（本地 ChromaDB）
    - 否则 → RagService（存根，返回空串）
    """
    try:
        from config import settings
        if settings.chromadb_path:
            from services.local_rag_service import LocalRagService
            logger.info("RAG: 使用 LocalRagService（ChromaDB 已配置）")
            return LocalRagService()
    except Exception:
        pass
    return RagService()
