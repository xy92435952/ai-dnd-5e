# -*- coding: utf-8 -*-
"""
Dify Workflow 连接测试脚本
使用 /info 端点做轻量鉴权检查，不触发 LLM
运行方式: python test_dify.py
"""
import asyncio
import httpx
import os
import sys

# 强制 UTF-8 输出
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

BASE_URL = os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1").rstrip("/")

WORKFLOWS = {
    "WF1 模组解析器":          os.getenv("DIFY_MODULE_PARSER_KEY", ""),
    "WF2 队伍生成器":          os.getenv("DIFY_PARTY_GENERATOR_KEY", ""),
    "WF3 DM Agent (Chatflow)": os.getenv("DIFY_DM_AGENT_KEY", ""),
}


async def check_workflow(name: str, api_key: str) -> bool:
    """
    调用 GET /info 验证 API Key 有效性
    - 200: Key 有效，应用存在
    - 401: Key 无效
    - 404: 应用不存在
    """
    url = f"{BASE_URL}/info"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code == 200:
            data = resp.json()
            app_name = data.get("name", "未知")
            app_mode = data.get("mode", "未知")
            print(f"  [OK]  {name}  ->  应用名: {app_name}  模式: {app_mode}")
            return True
        elif resp.status_code == 401:
            print(f"  [ERR] {name}  ->  401 认证失败，Key 无效")
            return False
        elif resp.status_code == 404:
            print(f"  [ERR] {name}  ->  404 应用不存在，请检查 Key 是否对应正确的应用")
            return False
        else:
            print(f"  [ERR] {name}  ->  HTTP {resp.status_code}: {resp.text[:100]}")
            return False

    except httpx.ConnectError:
        print(f"  [ERR] {name}  ->  无法连接到 {BASE_URL}，请检查网络或 DIFY_BASE_URL")
        return False
    except httpx.TimeoutException:
        print(f"  [WARN]{name}  ->  连接超时(15s)")
        return False
    except Exception as e:
        print(f"  [ERR] {name}  ->  {type(e).__name__}: {e}")
        return False


async def main():
    print("=" * 55)
    print("  Dify Workflow 连接测试 (/info 鉴权检查)")
    print(f"  Base URL: {BASE_URL}")
    print("=" * 55)

    results = {}
    for name, key in WORKFLOWS.items():
        if not key:
            print(f"  [SKIP]{name}  ->  Key 未配置")
            results[name] = None
            continue
        results[name] = await check_workflow(name, key)

    # 汇总
    print("-" * 55)
    ok_count = sum(1 for v in results.values() if v is True)
    fail_count = sum(1 for v in results.values() if v is False)
    total = len([v for v in results.values() if v is not None])

    print(f"结果: {ok_count}/{total} 通过")
    if fail_count == 0:
        print("所有 Workflow 连接正常！")
    else:
        print(f"有 {fail_count} 个异常，请根据上方提示排查。")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
