# 50 人封闭内测运行手册

> 目标：先让约 50 名种子用户能稳定试玩，而不是提前建设大规模平台。

## 1. 内测容量假设

- 单个后端实例。
- 服务器已完成 PostgreSQL 迁移，生产数据库固定使用 PostgreSQL。
- nginx 反代 HTTP / WebSocket。
- 同时在线用户建议控制在 50 人以内。
- WebSocket 连接建议控制在 80 条以内，预留刷新、断线重连和多标签页余量。
- 多人房间以 2-4 人为主。
- 模组上传和解析是受控能力，不鼓励大量并发上传。

这个阶段不承诺多实例横向扩容。多人 WebSocket 仍是进程内房间管理，多实例前必须接 Redis pub/sub 或外部实时消息层。

## 2. 必需环境变量

```env
ENV=production
DATABASE_URL=postgresql+asyncpg://ai_trpg:<password>@127.0.0.1:5432/ai_trpg
LANGGRAPH_DB_URL=postgresql://ai_trpg:<password>@127.0.0.1:5432/ai_trpg
JWT_SECRET=<至少32字节强随机字符串>
CORS_ALLOW_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT_PER_MINUTE=120
RATE_LIMIT_AUTH_PER_MINUTE=20
RATE_LIMIT_GAME_PER_MINUTE=30

BETA_MAX_USERS=50
BETA_MAX_WS_CONNECTIONS=80
MODULE_PARSE_MAX_CONCURRENT=2
MODULE_PARSE_MAX_BACKLOG=10
MAX_UPLOAD_MB=50
```

当前生产服务器已经迁移到 PostgreSQL。后续发布只执行 `alembic upgrade head` 做 schema 增量迁移，不再重复执行 SQLite → PostgreSQL 数据搬迁脚本。

`JWT_SECRET` 生成方式：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 3. 启动前检查

每次部署后先查：

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/ready
```

`/ready` 在生产环境会检查：

- 是否仍在使用 SQLite。
- `JWT_SECRET` 是否为空或过短。
- 上传目录是否存在。
- 当前 WebSocket 房间数、连接数和每房间连接数。
- 当前模组解析队列和正在运行的解析任务数。
- 当前 50 人内测关键阈值。

如果 `/ready` 返回 `503`，不要开放入口。

## 4. 运行期观察

重点观察：

- `/ready` 里的 `ws.connections` 是否接近 `BETA_MAX_WS_CONNECTIONS`。
- `/ready` 里的 `background_jobs.module_parse.queued/running` 是否长期贴近阈值。
- 后端日志里的 `429` 是否过多。
- 模组上传是否频繁出现“后台解析队列已满，请稍后再上传”。
- LLM 调用是否出现超时、401、模型错误或明显延迟。
- 多人房间是否出现玩家刷新后状态不一致。

建议内测期间保留一个人工反馈群，让玩家上报：

- DM 响应超过 20 秒。
- 多人消息不同步。
- 模组一直 processing。
- 房间成员在线状态异常。
- 战斗行动后 HP / 回合资源异常。

## 5. 当前保护措施

- HTTP 内存限流：按 token 或 IP + path 做单实例固定窗口限流。
- `/game/action`、`/modules/upload` 使用更严格的游戏/AI相关限流。
- 模组解析 backlog guard：超过队列阈值时上传直接返回 429，避免后台 LLM/RAG 积压。
- 模组解析并发槽：同一进程内最多同时运行 `MODULE_PARSE_MAX_CONCURRENT` 个解析任务。
- `/ready` 暴露生产配置风险和 WS 占用。

这些保护只适用于单实例内测。多实例部署时，限流和后台任务队列也要外部化。

## 6. 什么时候必须升级

出现任意情况，就不应继续只靠单实例：

- 同时在线稳定超过 50 人。
- WebSocket 连接接近 80 且频繁重连。
- 多人房间超过 20 个并发活跃。
- 模组解析队列经常满。
- LLM 成本或超时不可控。
- 需要不中断部署或横向扩容。

下一步升级顺序：

1. Redis pub/sub 替换进程内 WS 广播。
2. Redis-backed rate limit 替换内存限流。
3. 模组解析 / RAG 入库 / 长期记忆总结迁到后台 worker 队列。
4. 上传文件迁到对象存储。
5. AI 调用增加成本统计、模型分层、超时和降级。
