# 生产环境状态记录

> 更新时间：2026-05-24

## 当前结论

- 服务器数据库已完成 SQLite 到 PostgreSQL 的迁移。
- 后续生产发布以 PostgreSQL 为唯一生产数据库基线。
- 历史 SQLite 数据迁移脚本 `backend/migrate_to_pg.py` 仅用于老环境补救，不进入常规发布流程。
- 常规发布只执行 Alembic schema 增量迁移：

```bash
cd /opt/ai-trpg/app/backend
source /opt/ai-trpg/venv/bin/activate
alembic upgrade head
```

## 生产运行约束

- 后端保持单 worker 运行，直到 WebSocket 广播接入 Redis pub/sub。
- `/ready` 必须返回 `status=ready` 后再开放入口。
- `DATABASE_URL` 必须使用 `postgresql+asyncpg://...`。
- `LANGGRAPH_DB_URL` 必须使用 `postgresql://...`。
- `ENV=production` 时，如果仍配置 SQLite，`/ready` 会返回 503。
- `/ready.runtime` 会暴露当前协调层状态；在 `coordination=in_process` 且 `single_worker_required=true` 时，不要把后端扩成多 worker。

## 50 人封闭内测建议值

```env
BETA_MAX_USERS=50
BETA_MAX_WS_CONNECTIONS=80
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT_PER_MINUTE=120
RATE_LIMIT_AUTH_PER_MINUTE=20
RATE_LIMIT_GAME_PER_MINUTE=30
MODULE_PARSE_MAX_CONCURRENT=1
MODULE_PARSE_MAX_BACKLOG=5
```
