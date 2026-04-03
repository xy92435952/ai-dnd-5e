"""
本地 RAG 上传器（ChromaDB）
===========================
替换 DifyRagUploader，将 WF1 生成的 rag_chunks 存入本地 ChromaDB。
"""

import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


def _get_chroma_collection():
    """获取或创建 ChromaDB collection。"""
    import chromadb
    client = chromadb.PersistentClient(path=settings.chromadb_path)
    return client.get_or_create_collection(
        name="module_chunks",
        metadata={"hnsw:space": "cosine"},
    )


def _format_chunk_content(chunk: dict, module_id: str) -> str:
    """将 chunk 格式化为存储文本（复用自 dify_rag_uploader.py）。"""
    lines = [
        f"模组ID: {module_id}",
        f"类型: {chunk.get('source_type', 'unknown')}",
    ]

    chunk_id = chunk.get("chunk_id", "")
    if chunk_id:
        lines.append(f"标识: {chunk_id}")

    content = chunk.get("content", "")
    if content:
        lines.append(f"\n内容:\n{content}")

    summary = chunk.get("summary", "")
    if summary:
        lines.append(f"\n摘要: {summary}")

    tags = chunk.get("tags", [])
    if tags:
        lines.append(f"标签: {', '.join(tags)}")

    entities = chunk.get("entities", [])
    if entities:
        lines.append(f"相关实体: {', '.join(entities)}")

    questions = chunk.get("searchable_questions", [])
    if questions:
        lines.append("\n常见问题:")
        for q in questions:
            lines.append(f"- {q}")

    return "\n".join(lines)


class LocalRagUploader:
    """将模组 RAG chunks 存入本地 ChromaDB。"""

    async def upload_module_chunks(
        self,
        module_id: str,
        chunks: list[dict],
    ) -> int:
        if not chunks:
            logger.info(f"模组 {module_id}: rag_chunks 为空，跳过上传")
            return 0

        try:
            import asyncio
            collection = await asyncio.to_thread(_get_chroma_collection)

            ids = []
            documents = []
            metadatas = []

            for chunk in chunks:
                chunk_id = chunk.get("chunk_id", f"chunk_{len(ids)}")
                doc_id = f"{module_id}_{chunk_id}"
                content = _format_chunk_content(chunk, module_id)

                ids.append(doc_id)
                documents.append(content)
                metadatas.append({
                    "module_id": module_id,
                    "chunk_id": chunk_id,
                    "source_type": chunk.get("source_type", "unknown"),
                })

            await asyncio.to_thread(
                collection.upsert,
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )

            logger.info(f"模组 {module_id}: 已存入 {len(ids)} 个 RAG chunks 到 ChromaDB")
            return len(ids)
        except Exception as e:
            logger.warning(f"RAG chunk 上传失败 [{module_id}]: {e}")
            return 0

    async def delete_module_chunks(self, module_id: str) -> None:
        try:
            import asyncio
            collection = await asyncio.to_thread(_get_chroma_collection)
            await asyncio.to_thread(
                collection.delete,
                where={"module_id": module_id},
            )
            logger.info(f"模组 {module_id}: 已从 ChromaDB 删除相关 chunks")
        except Exception as e:
            logger.warning(f"清理模组 RAG chunks 失败 [{module_id}]: {e}")


# 单例
rag_uploader = LocalRagUploader()
