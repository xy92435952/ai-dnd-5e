"""
导出后端 OpenAPI schema 到 backend/openapi.json。

用途：前端 `npm run types:api` 读这份文件生成 TypeScript 类型声明，
无需启动后端服务，CI 也能跑。

约定：
  - 本脚本不跑 app.lifespan（不初始化 LangGraph / ChromaDB / SQLite 表）
  - 只做纯 schema 导出，秒级完成
  - 产物入库（便于 PR 审查 schema 变化）

在项目根运行：
    cd backend && python scripts/export_openapi.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 允许 `python scripts/export_openapi.py` 从 backend 根目录运行
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from main import app

    schema = app.openapi()
    out = ROOT / "openapi.json"
    out.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths = len(schema.get("paths", {}))
    size_kb = out.stat().st_size / 1024
    print(f"[ok] 写入 {out.relative_to(ROOT.parent)} — {paths} 个路径，{size_kb:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
