# -*- coding: utf-8 -*-
"""
WF1 解析 + Dify KB 上传 全链路测试脚本
用法：.venv/Scripts/python test_wf1_and_upload.py [模组文本文件路径]
默认使用 ../test_module_sample.txt
"""
import asyncio
import httpx
import json
import os
import sys
import pathlib

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DIFY      = os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1").rstrip("/")
KB_BASE   = os.getenv("DIFY_KB_BASE_URL", "https://api.dify.ai/v1").rstrip("/")
WF1_KEY   = os.getenv("DIFY_MODULE_PARSER_KEY", "")
KB_KEY    = os.getenv("DIFY_KNOWLEDGE_API_KEY", "")
DATASET   = os.getenv("DIFY_MODULE_DATASET_ID", "")
MODULE_ID = "test-module-001"   # 虚拟 module_id，用于 KB 内容前缀过滤

PASS = "✅"; FAIL = "❌"


# ── Step 1: 调用 WF1 解析模组文本 ──────────────────────────────
async def run_wf1(client: httpx.AsyncClient, module_text: str) -> tuple[dict, list]:
    print("\n【Step 1】调用 WF1 解析模组文本...")
    r = await client.post(
        f"{DIFY}/workflows/run",
        headers={"Authorization": f"Bearer {WF1_KEY}", "Content-Type": "application/json"},
        json={"inputs": {"module_text": module_text}, "response_mode": "blocking", "user": "test-upload"},
        timeout=120.0,
    )
    r.raise_for_status()
    data = r.json()

    if data.get("data", {}).get("status") == "failed":
        print(f"  {FAIL}  WF1 执行失败: {data['data'].get('error')}")
        return {}, []

    outputs = data.get("data", {}).get("outputs", {})

    # module_data
    raw_md = outputs.get("module_data", "{}")
    try:
        module_data = json.loads(raw_md)
    except json.JSONDecodeError:
        module_data = {}

    name     = module_data.get("name", "?")
    scenes   = module_data.get("scenes", [])
    monsters = module_data.get("monsters", [])
    npcs     = module_data.get("npcs", [])
    ok_md    = bool(name and name != "?")
    print(f"  {PASS if ok_md else FAIL}  module_data — name={name}  scenes={len(scenes)}  monsters={len(monsters)}  npcs={len(npcs)}")

    if not ok_md:
        print("       ⚠️  module_data 为空 — 请检查 Dify WF1 LLM 节点的模型配置")
        print(f"       raw output: {raw_md[:200]}")

    # rag_chunks
    raw_chunks = outputs.get("rag_chunks", "[]")
    try:
        rag_chunks = json.loads(raw_chunks)
        if not isinstance(rag_chunks, list):
            rag_chunks = []
    except json.JSONDecodeError:
        rag_chunks = []

    chunks_count = outputs.get("chunks_count", len(rag_chunks))
    print(f"  {PASS if rag_chunks else FAIL}  rag_chunks — 数量={len(rag_chunks)}（WF1 报告={chunks_count}）")

    if not rag_chunks:
        print("       ⚠️  rag_chunks 为空 — WF1 v0.4 新增输出，请确认已部署最新版 WF1")

    return module_data, rag_chunks


# ── Step 2: 上传 rag_chunks 到 Dify KB ──────────────────────────
async def upload_chunks(client: httpx.AsyncClient, chunks: list) -> int:
    if not KB_KEY or not DATASET:
        print(f"\n【Step 2】跳过 KB 上传（DIFY_KNOWLEDGE_API_KEY 或 DIFY_MODULE_DATASET_ID 未配置）")
        return 0

    if not chunks:
        print(f"\n【Step 2】跳过 KB 上传（rag_chunks 为空）")
        return 0

    print(f"\n【Step 2】上传 {len(chunks)} 个 chunks 到 Dify KB...")
    headers = {"Authorization": f"Bearer {KB_KEY}", "Content-Type": "application/json"}
    success = 0

    for i, chunk in enumerate(chunks):
        # 拼装 chunk 内容，首行固定为模组ID前缀供过滤
        lines = [
            f"模组ID: {MODULE_ID}",
            f"类型: {chunk.get('source_type', 'unknown')}",
            f"内容: {chunk.get('content', '')}",
        ]
        if chunk.get("summary"):
            lines.append(f"摘要: {chunk['summary']}")
        if chunk.get("tags"):
            tags_str = ", ".join(chunk["tags"]) if isinstance(chunk["tags"], list) else chunk["tags"]
            lines.append(f"标签: {tags_str}")
        if chunk.get("entities"):
            ent_str = ", ".join(chunk["entities"]) if isinstance(chunk["entities"], list) else chunk["entities"]
            lines.append(f"相关实体: {ent_str}")
        if chunk.get("searchable_questions"):
            lines.append("常见问题:")
            for q in (chunk["searchable_questions"] or [])[:3]:
                lines.append(f"- {q}")

        content = "\n".join(lines)

        try:
            r = await client.post(
                f"{KB_BASE}/datasets/{DATASET}/document/create_by_text",
                headers=headers,
                json={
                    "name": f"{MODULE_ID}_{chunk.get('chunk_id', i)}",
                    "text": content,
                    "indexing_technique": "high_quality",
                    "process_rule": {"mode": "automatic"},
                },
                timeout=30.0,
            )
            if r.status_code in (200, 201):
                success += 1
                doc_id = r.json().get("document", {}).get("id", "?")
                print(f"  {PASS}  chunk {i+1}/{len(chunks)}  [{chunk.get('source_type','?')}]  doc_id={doc_id}")
            else:
                print(f"  {FAIL}  chunk {i+1}/{len(chunks)}  HTTP {r.status_code}: {r.text[:100]}")
        except Exception as e:
            print(f"  {FAIL}  chunk {i+1}/{len(chunks)}  {e}")

    return success


# ── Step 3: 验证 KB 检索 ─────────────────────────────────────────
async def verify_kb(client: httpx.AsyncClient):
    if not KB_KEY or not DATASET:
        return
    print(f"\n【Step 3】验证 KB 检索...")
    try:
        r = await client.post(
            f"{KB_BASE}/datasets/{DATASET}/retrieve",
            headers={"Authorization": f"Bearer {KB_KEY}", "Content-Type": "application/json"},
            json={
                "query": "银谷村 场景 怪物",
                "retrieval_model": {
                    "search_method": "hybrid_search",
                    "top_k": 3,
                    "score_threshold_enabled": False,
                    "reranking_enable": False,
                },
            },
            timeout=15.0,
        )
        if r.status_code == 200:
            records = r.json().get("records", [])
            print(f"  {PASS}  检索成功，返回 {len(records)} 条结果")
            for rec in records[:2]:
                seg = rec.get("segment", {})
                preview = seg.get("content", "")[:80].replace("\n", " ")
                score = rec.get("score", "?")
                print(f"       score={score:.3f}  {preview}...")
        else:
            print(f"  {FAIL}  HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"  {FAIL}  {e}")


# ── 主流程 ────────────────────────────────────────────────────────
async def main():
    # 读取模组文本
    module_file = sys.argv[1] if len(sys.argv) > 1 else str(
        pathlib.Path(__file__).parent.parent / "test_module_sample.txt"
    )
    if not pathlib.Path(module_file).exists():
        print(f"找不到模组文件: {module_file}")
        sys.exit(1)
    module_text = pathlib.Path(module_file).read_text(encoding="utf-8")

    print("=" * 60)
    print("  WF1 解析 + Dify KB 上传 全链路测试")
    print(f"  模组文件: {module_file}（{len(module_text)} 字符）")
    print(f"  Dify: {DIFY}")
    print("=" * 60)

    if not WF1_KEY:
        print(f"{FAIL}  DIFY_MODULE_PARSER_KEY 未配置，退出")
        sys.exit(1)

    async with httpx.AsyncClient() as client:
        module_data, rag_chunks = await run_wf1(client, module_text)

        if not module_data.get("name"):
            print(f"\n{FAIL}  WF1 解析失败，中止上传。请先修复 Dify WF1 的 LLM 节点配置。")
            sys.exit(1)

        uploaded = await upload_chunks(client, rag_chunks)

        if uploaded > 0:
            print(f"\n  等待 KB 索引建立（3s）...")
            await asyncio.sleep(3)
            await verify_kb(client)

    print("\n" + "=" * 60)
    print(f"  module_data: {'OK' if module_data.get('name') else 'EMPTY'}")
    print(f"  rag_chunks:  {len(rag_chunks)} 个")
    print(f"  KB 上传:     {uploaded}/{len(rag_chunks)} 成功")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
