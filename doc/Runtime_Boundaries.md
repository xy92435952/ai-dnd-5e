# 运行时边界与扩容前置条件

> 最后更新：2026-05-24
> 适用阶段：50 人封闭内测。目标是稳定试玩，不是多实例平台化。

## 结论

当前技术栈可以支撑 50 人内测，但运行方式必须保持“单后端进程 + PostgreSQL + nginx + 前端静态构建”。不要在接入外部实时消息层之前开启多 worker 或多实例。

## 单实例边界

| 能力 | 当前实现 | 50 人内测口径 | 扩容前必须做的事 |
|------|----------|---------------|------------------|
| 多人 WebSocket | `services.ws_manager` 进程内连接表 | 单 worker 可用 | Redis pub/sub 或独立 realtime service |
| 房间在线状态 | 连接生命周期写入内存并同步 DB 状态 | 可承受刷新和短线重连 | 在线状态外部化，避免进程间分裂 |
| HTTP 限流 | `services.rate_limit_service` 进程内固定窗口 | 单实例有效 | Redis-backed rate limit |
| 模组解析并发 | `services.background_job_limits` 进程内计数 | 控制并发和 backlog | Worker 队列，例如 Redis/RQ/Celery/Arq |
| AI 调用延迟观测 | `services.ai_latency` 日志分段 | 可定位主要慢点 | 聚合指标、成本统计、模型分层策略 |
| 数据库 | PostgreSQL 生产，SQLite 本地 | 生产必须 PostgreSQL | 连接池、慢查询、索引审计 |
| 文件上传 | 本机目录 | 低频上传可用 | 对象存储和异步杀毒/解析 |
| ChromaDB | 本地持久化目录 | 单机可用 | 外部向量库或可迁移 RAG worker |

## 必须保持的部署约束

- `uvicorn` / `gunicorn` 后端 worker 数保持 `1`。
- 生产 `DATABASE_URL` 使用 `postgresql+asyncpg://...`。
- `LANGGRAPH_DB_URL` 使用 PostgreSQL，避免 LangGraph 记忆仍落到本地 SQLite。
- nginx WebSocket 反代必须保留 `Upgrade` / `Connection`。
- `/ready` 返回 503 时不要开放玩家入口。
- `/ready.runtime.single_worker_required` 当前固定为 `true`；只要 `coordination=in_process`，就不要开启多 worker。

推荐启动形态：

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

## 风险信号

出现下面任一信号，就说明已经接近当前架构边界：

- `/ready` 中 `ws.connections` 接近 `BETA_MAX_WS_CONNECTIONS`。
- 多人房间刷新后在线状态、发言权或广播不同步。
- 后端日志中 `429` 明显增多。
- `background_jobs.module_parse.queued` 长时间贴近 backlog 上限。
- `ai_latency` 日志显示 `dm_agent_ms`、`parse_ms` 或 `narrate_ms` 经常超过玩家可接受区间。
- 部署时需要不中断玩家会话。

## 下一阶段升级顺序

1. Redis pub/sub：先解决 WebSocket 广播和多人房间状态分裂问题。
2. Redis rate limit：让限流跨实例一致。
3. Worker 队列：外部化模组解析、RAG 入库、长期记忆总结等慢任务。
4. AI 观测：把 `ai_latency` 日志接入指标平台，按 route/session/model 统计 P50/P95/P99。
5. 文件和 RAG 外部化：对象存储 + 可迁移向量库。
6. 多实例后端：完成以上外部化后再增加 worker 或实例。

## 与玩家体验相关的边界

AI 回复质量优先于极端低延迟。当前可以优化的是链路观测、局部并发、前端等待反馈和失败恢复；不应为了快而裁剪 `module_context`、`campaign_memory` 或规则上下文，除非有回归测试证明不会损害 DM 回答质量。
