"""
连通性测试脚本
测试所有 Dify API（WF1/WF2/WF3 Chatflow）和 Knowledge Base 的连通性
运行方式：.venv/Scripts/python test_connectivity.py
"""
import asyncio
import httpx
import json
import sys

# Windows GBK 终端兼容：强制 UTF-8 输出
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from config import settings

BASE  = "http://localhost:8002"
DIFY  = settings.dify_base_url.rstrip("/")
KB    = settings.dify_kb_base_url.rstrip("/")

PASS  = "✅"
FAIL  = "❌"
WARN  = "⚠️ "

results = []

def log(label: str, ok: bool, detail: str = ""):
    icon = PASS if ok else FAIL
    line = f"  {icon}  {label}"
    if detail:
        line += f"  →  {detail}"
    print(line)
    results.append(ok)

# ─────────────────────────────────────────────
# 1. 后端健康
# ─────────────────────────────────────────────
async def check_backend(client: httpx.AsyncClient):
    print("\n【1】后端健康检查")
    try:
        r = await client.get(f"{BASE}/health")
        data = r.json()
        log("FastAPI /health", r.status_code == 200, f"status={data.get('status')} version={data.get('version')}")
    except Exception as e:
        log("FastAPI /health", False, str(e))

# ─────────────────────────────────────────────
# 2. Dify Workflow API Keys
# ─────────────────────────────────────────────
async def check_workflow_key(client: httpx.AsyncClient, name: str, api_key: str):
    """用一个极简 inputs 调用 workflow，只看认证是否通过（不期待正确输出）"""
    if not api_key:
        log(name, False, "API Key 未配置")
        return
    try:
        r = await client.post(
            f"{DIFY}/workflows/run",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"inputs": {"_ping": "1"}, "response_mode": "blocking", "user": "connectivity-test"},
            timeout=15.0,
        )
        # 200/400 均说明 Key 有效（400 = 参数错误但认证通过）
        # 401 = Key 无效
        ok = r.status_code != 401
        detail = f"HTTP {r.status_code}"
        if not ok:
            detail += f"  ({r.text[:80]})"
        log(name, ok, detail)
    except httpx.TimeoutException:
        log(name, False, "请求超时（>15s）")
    except Exception as e:
        log(name, False, str(e))


async def check_chatflow_key(client: httpx.AsyncClient, name: str, api_key: str):
    """用空消息测试 Chatflow Key 认证"""
    if not api_key:
        log(name, False, "API Key 未配置")
        return
    try:
        r = await client.post(
            f"{DIFY}/chat-messages",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "query": "_ping",
                "inputs": {"game_state": "{}", "module_context": "{}", "campaign_memory": "", "retrieved_context": ""},
                "response_mode": "blocking",
                "user": "connectivity-test",
                "conversation_id": "",
            },
            timeout=30.0,
        )
        ok = r.status_code != 401
        detail = f"HTTP {r.status_code}"
        if r.status_code == 200:
            answer = r.json().get("answer", "")[:60]
            detail += f'  answer="{answer}..."'
        elif not ok:
            detail += f"  ({r.text[:80]})"
        log(name, ok, detail)
    except httpx.TimeoutException:
        log(name, False, "请求超时（>30s）")
    except Exception as e:
        log(name, False, str(e))


async def check_dify_keys(client: httpx.AsyncClient):
    print("\n【2】Dify Workflow API Keys")
    await check_workflow_key(client, "WF1 模组解析器",          settings.dify_module_parser_key)
    await check_workflow_key(client, "WF2 队伍生成器",          settings.dify_party_generator_key)
    await check_chatflow_key(client, "WF3 DM Agent (Chatflow)", settings.dify_dm_agent_key)


# ─────────────────────────────────────────────
# 3. Knowledge Base API
# ─────────────────────────────────────────────
async def check_kb(client: httpx.AsyncClient):
    print("\n【3】Knowledge Base (RAG)")
    kb_key  = settings.dify_knowledge_api_key
    kb_id   = settings.dify_module_dataset_id

    if not kb_key:
        log("KB API Key",    False, "DIFY_KNOWLEDGE_API_KEY 未配置")
        log("KB Dataset ID", False, "跳过")
        log("KB 检索测试",   False, "跳过")
        return

    log("KB API Key",    True,  f"dataset-***{kb_key[-6:]}")
    log("KB Dataset ID", bool(kb_id), kb_id or "DIFY_MODULE_DATASET_ID 未配置")

    if not kb_id:
        log("KB 检索测试", False, "跳过（无 Dataset ID）")
        return

    # 列出 KB 文档（验证 KB 是否可访问）
    try:
        r = await client.get(
            f"{KB}/datasets/{kb_id}/documents",
            headers={"Authorization": f"Bearer {kb_key}"},
            params={"page": 1, "limit": 5},
            timeout=10.0,
        )
        ok = r.status_code == 200
        if ok:
            data  = r.json()
            total = data.get("total", "?")
            docs  = data.get("data", [])
            names = [d.get("name", "?")[:30] for d in docs[:3]]
            detail = f"总文档数={total}"
            if names:
                detail += "  示例: " + ", ".join(names)
            log("KB 文档列表", True, detail)
        else:
            log("KB 文档列表", False, f"HTTP {r.status_code}  {r.text[:100]}")
    except Exception as e:
        log("KB 文档列表", False, str(e))

    # 检索测试
    try:
        r = await client.post(
            f"{KB}/datasets/{kb_id}/retrieve",
            headers={"Authorization": f"Bearer {kb_key}", "Content-Type": "application/json"},
            json={
                "query": "场景 NPC 怪物",
                "retrieval_model": {
                    "search_method": "hybrid_search",
                    "top_k": 2,
                    "score_threshold_enabled": False,
                    "reranking_enable": False,
                },
            },
            timeout=10.0,
        )
        ok = r.status_code == 200
        if ok:
            records = r.json().get("records", [])
            log("KB 检索测试", True, f"返回 {len(records)} 条结果")
        else:
            log("KB 检索测试", False, f"HTTP {r.status_code}  {r.text[:100]}")
    except Exception as e:
        log("KB 检索测试", False, str(e))

# ─────────────────────────────────────────────
# 4. WF1 实际解析小样本
# ─────────────────────────────────────────────
async def check_wf1_parse(client: httpx.AsyncClient):
    print("\n【4】WF1 实际解析测试（小样本模组文本）")
    if not settings.dify_module_parser_key:
        log("WF1 解析", False, "API Key 未配置")
        return
    try:
        sample = (
            "模组名称：测试地下城\n"
            "背景：一个简单的测试场景。\n"
            "场景一：入口大厅，有一个哥布林守卫。\n"
            "NPC：村长阿尔文，友好，可提供任务。\n"
            "怪物：哥布林（CR1/4，HP7，AC15）"
        )
        r = await client.post(
            f"{DIFY}/workflows/run",
            headers={"Authorization": f"Bearer {settings.dify_module_parser_key}", "Content-Type": "application/json"},
            json={"inputs": {"module_text": sample}, "response_mode": "blocking", "user": "connectivity-test"},
            timeout=60.0,
        )
        if r.status_code == 200:
            outputs = r.json().get("data", {}).get("outputs", {})
            module_data  = outputs.get("module_data", "{}")
            rag_chunks   = outputs.get("rag_chunks", "[]")
            chunks_count = outputs.get("chunks_count", 0)

            # 验证 module_data
            try:
                md = json.loads(module_data)
                has_name    = bool(md.get("name"))
                has_scenes  = isinstance(md.get("scenes"), list)
                has_monsters= isinstance(md.get("monsters"), list)
                log("WF1 module_data 结构", has_name and has_scenes,
                    f"name={md.get('name','?')}  scenes={len(md.get('scenes',[]))}  monsters={len(md.get('monsters',[]))}")
            except Exception:
                log("WF1 module_data 解析", False, module_data[:80])

            # 验证 rag_chunks（WF1 v0.4 新增）
            try:
                chunks = json.loads(rag_chunks)
                log("WF1 rag_chunks 输出", isinstance(chunks, list),
                    f"chunks_count={chunks_count}  实际={len(chunks)}"
                    + (f"  类型={[c.get('source_type') for c in chunks[:3]]}" if chunks else "  (空)"))
            except Exception:
                log("WF1 rag_chunks 解析", False, rag_chunks[:80])
        else:
            log("WF1 解析", False, f"HTTP {r.status_code}  {r.text[:100]}")
    except httpx.TimeoutException:
        log("WF1 解析", False, "请求超时（>60s）")
    except Exception as e:
        log("WF1 解析", False, str(e))

# ─────────────────────────────────────────────
# 汇总
# ─────────────────────────────────────────────
async def main():
    print("=" * 55)
    print("  AI 跑团平台 — 连通性测试")
    print(f"  后端: {BASE}  Dify: {DIFY}")
    print("=" * 55)

    async with httpx.AsyncClient(timeout=30.0) as client:
        await check_backend(client)
        await check_dify_keys(client)
        await check_kb(client)
        await check_wf1_parse(client)

    passed = sum(results)
    total  = len(results)
    print("\n" + "=" * 55)
    print(f"  结果：{passed}/{total} 通过")
    if passed == total:
        print("  🎉 全部通过！")
    else:
        print(f"  ⚠️  {total - passed} 项失败，请检查上方日志")
    print("=" * 55)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
