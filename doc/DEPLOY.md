# 生产部署清单

> 最后更新：2026-05-07
> 适用状态：当前 FastAPI + Vite + nginx 静态文件部署，以及可选 Docker Compose 部署。

## 1. 发布前本地确认

在推送或服务器拉取前，建议先跑：

```bash
cd frontend
npm test
npm run build

cd ..
backend/.venv-codex/bin/pytest \
  backend/tests/unit/test_action_parser.py \
  backend/tests/integration/test_combat_endpoints.py \
  backend/tests/smoke/test_imports.py -q
```

当前已知非阻塞 warning：

- Vite 构建可能提示部分 chunk 超过 500KB。
- CSS 可能提示 Google Fonts `@import` 顺序。
- Vitest 在 Node 25 下可能输出 `--localstorage-file` warning，但测试应通过。

## 2. 环境变量

服务器必须有 `backend/.env`，不要提交到 Git。

最小示例：

```env
ENV=production
JWT_SECRET=<用强随机生成的至少32字节字符串>
CORS_ALLOW_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash

DATABASE_URL=sqlite+aiosqlite:///./ai_trpg.db
CHROMADB_PATH=./chromadb_data
LANGGRAPH_DB_PATH=./langgraph_memory.db
UPLOAD_DIR=./uploads
```

生产 PostgreSQL 示例：

```env
DATABASE_URL=postgresql+asyncpg://ai_trpg:<password>@127.0.0.1:5432/ai_trpg
LANGGRAPH_DB_URL=postgresql://ai_trpg:<password>@127.0.0.1:5432/ai_trpg
```

生成 `JWT_SECRET`：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 3. 服务器更新流程（systemd + nginx）

适用于当前“nginx 直接读 `frontend/dist`，后端由 systemd/uvicorn 跑在本机端口”的部署方式。

```bash
cd /opt/ai-trpg/app
git pull

cd backend
source /opt/ai-trpg/venv/bin/activate
pip install -r requirements.txt

cd ../frontend
npm install
npm run build
```

纯前端改动：

- `npm run build` 成功后，nginx 会直接读取新的 `dist/` 静态文件。
- 通常不需要重启 nginx。
- 不需要重启后端。

包含后端改动：

```bash
sudo systemctl restart ai-trpg
# 或服务器实际使用的服务名：
sudo systemctl restart ai-trpg-backend
```

检查：

```bash
curl -s http://127.0.0.1:8000/health
curl -s https://yourdomain.com/api/health
sudo journalctl -u ai-trpg -n 100 --no-pager
```

如果服务器后端实际监听 8002，请把命令和 nginx `proxy_pass` 中的端口对应调整。

## 4. Nginx 参考配置

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        root /opt/ai-trpg/app/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        client_max_body_size 50M;
    }
}
```

注意：

- WebSocket 必须保留 `Upgrade` / `Connection` 头。
- `location /api/ws/` 应在 `location /api/` 之前。
- 如果使用 HTTPS，记得同步把域名写入 `CORS_ALLOW_ORIGINS`。

## 5. Docker Compose 部署

仓库内 [docker-compose.yml](/Users/qft/Desktop/ai-dnd-5e/docker-compose.yml) 提供 PostgreSQL + backend + frontend 三容器参考：

```bash
cd /opt/ai-trpg/app
docker compose build --no-cache
docker compose up -d
docker compose logs -f backend --tail=100
```

当前 compose 端口：

- backend 宿主机端口：`8002` → 容器 `8000`
- frontend 宿主机端口：`3080` → 容器 `80`
- postgres 宿主机端口：`5432`

## 6. 数据库迁移

项目当前仍在 `main.py` lifespan 中调用 `init_db()`，本地开发可自动建表。生产 PostgreSQL 推荐使用 Alembic 管理 schema。

全新 PostgreSQL：

```bash
cd backend
alembic upgrade head
```

已有旧库：

```bash
cd backend
alembic current
alembic upgrade head
```

更完整说明见 [backend/alembic/README.md](/Users/qft/Desktop/ai-dnd-5e/backend/alembic/README.md)。

## 7. 部署后冒烟测试

至少手动跑：

1. 注册 / 登录。
2. 上传一个小模组，等待解析完成。
3. 创建角色，确认技能/法术/装备步骤可交互。
4. 开始冒险，发送一句探索行动。
5. 点击 AI 生成选项，确认不会被规则拦截。
6. 输入明显无关内容，确认 DM 会拒绝。
7. 触发战斗，测试移动、攻击、施法、结束回合。
8. 测试远距离近战自然语言：`我向最近的敌人移动并用长剑攻击它`。如果移动后仍不可达，应只移动，不掷攻击骰。
9. 多人房间：创建、加入、认领角色、发言轮转、刷新恢复。

## 8. 日志与故障定位

```bash
# systemd 后端
sudo journalctl -u ai-trpg -f

# nginx
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Docker
docker compose logs -f backend --tail=200
docker compose logs -f frontend --tail=100
```

常见问题：

- **前端 404**：nginx `try_files $uri $uri/ /index.html` 缺失。
- **API 401**：token 过期或 `JWT_SECRET` 变更导致旧 token 失效。
- **WebSocket 不同步**：检查 `/api/ws/` upgrade header。
- **LLM 401/模型错误**：检查 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`。
- **ChromaDB import error**：服务器未重新 `pip install -r backend/requirements.txt`。

## 9. 不要推送的内容

已在 `.gitignore` 中忽略：

- `backend/.env`
- `frontend/dist/`
- `.venv*`
- `backend/.venv*`
- `*.db`
- `.pytest_cache/`

推送前可检查：

```bash
git status --short
git check-ignore -v backend/.env frontend/dist backend/.venv-codex
```
