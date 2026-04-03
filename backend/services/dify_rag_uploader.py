"""
Dify RAG 上传器
==============
将 WF1 生成的 rag_chunks 上传到 Dify Cloud Knowledge Base。

调用时机：
  - 模组上传解析完成后（api/modules.py 的后台任务中）
  - 模组删除时清理对应 chunks

chunk 上传格式：
  每个 chunk 作为一个独立文档上传，文档名为 [{module_id}] {chunk_id}。
  content 的第一行写入 module_id 标记，供检索时 Python 侧过滤使用。

  格式示例：
    模组ID: abc123
    类型: scene
    标题: 银谷村入口
    内容: 银谷村坐落于两座山峰之间...
    摘要: 玩家进入银谷村的第一个场景...
    标签: 村庄, 入口, 起始场景
    相关实体: 银谷村, 村长, 老井
    常见问题:
    - 银谷村里有什么？
    - 如何进入银谷村？
"""

import httpx
import json
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


class DifyRagUploader:
    """将模组 RAG chunks 上传到 Dify Knowledge Base。"""

    def __init__(self):
        self.kb_base_url = settings.dify_kb_base_url.rstrip("/")
        self.api_key = settings.dify_knowledge_api_key
        self.dataset_id = settings.dify_module_dataset_id

    @property
    def _is_configured(self) -> bool:
        return bool(self.api_key and self.dataset_id)

    async def upload_module_chunks(
        self,
        module_id: str,
        chunks: list[dict],
    ) -> int:
        """
        将 RAG chunks 上传到 Dify Knowledge Base。

        Args:
            module_id: 模组 ID（用于前缀过滤标记）
            chunks:    WF1 生成的 rag_chunks 列表

        Returns:
            成功上传的 chunk 数量
        """
        if not self._is_configured:
            logger.info("RAG uploader: 未配置 Knowledge Base，跳过上传")
            return 0

        if not chunks:
            logger.info(f"模组 {module_id}: rag_chunks 为空，跳过上传")
            return 0

        success_count = 0
        async with httpx.AsyncClient(timeout=30.0) as client:
            for chunk in chunks:
                try:
                    content = _format_chunk_content(chunk, module_id)
                    doc_name = f"[{module_id}] {chunk.get('chunk_id', 'unknown')}"

                    resp = await client.post(
                        f"{self.kb_base_url}/datasets/{self.dataset_id}/document/create_by_text",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "name": doc_name,
                            "text": content,
                            "indexing_technique": "high_quality",
                            "process_rule": {
                                "mode": "custom",
                                "rules": {
                                    "segmentation": {
                                        "separator": "\n\n",
                                        "max_tokens": 800,
                                    },
                                    "pre_processing_rules": [
                                        {"id": "remove_extra_spaces", "enabled": True},
                                        {"id": "remove_urls_emails", "enabled": False},
                                    ],
                                },
                            },
                        },
                    )
                    resp.raise_for_status()
                    success_count += 1
                except Exception as e:
                    logger.warning(
                        f"RAG chunk 上传失败 [{module_id}]"
                        f" {chunk.get('chunk_id', '?')}: {e}"
                    )

        logger.info(
            f"模组 {module_id}: 上传 {success_count}/{len(chunks)} 个 RAG chunks 到 KB"
        )
        return success_count

    async def delete_module_chunks(self, module_id: str) -> None:
        """
        删除指定模组的所有 chunks（模组删除时调用）。
        通过文档名前缀 [{module_id}] 定位所有相关文档。
        """
        if not self._is_configured:
            return

        deleted = 0
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                page = 1
                while True:
                    resp = await client.get(
                        f"{self.kb_base_url}/datasets/{self.dataset_id}/documents",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        params={"page": page, "limit": 100},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    docs = data.get("data", [])

                    if not docs:
                        break

                    prefix = f"[{module_id}]"
                    for doc in docs:
                        if doc.get("name", "").startswith(prefix):
                            try:
                                await client.delete(
                                    f"{self.kb_base_url}/datasets/{self.dataset_id}"
                                    f"/documents/{doc['id']}",
                                    headers={"Authorization": f"Bearer {self.api_key}"},
                                )
                                deleted += 1
                            except Exception as e:
                                logger.warning(f"删除 RAG 文档失败 {doc.get('id')}: {e}")

                    if not data.get("has_more"):
                        break
                    page += 1

            logger.info(f"模组 {module_id}: 已从 KB 删除 {deleted} 个文档")
        except Exception as e:
            logger.warning(f"清理模组 RAG chunks 失败 [{module_id}]: {e}")


def _format_chunk_content(chunk: dict, module_id: str) -> str:
    """
    将 chunk 格式化为上传到 KB 的文本。
    第一行固定为「模组ID: {module_id}」，供检索时 Python 侧过滤。
    """
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


# 单例
rag_uploader = DifyRagUploader()
