# 生产部署清单（v0.10）

> 最后更新：2026-04-19

## 🔒 一、强制硬化（上线前必做）

### 1. 生成独立 JWT secret

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
# 把输出填入 backend/.env 的 JWT_SECRET
```

不设 `JWT_SECRET` + `ENV=production` 会直接 RuntimeError，上线不会忘。

### 2. 配置 CORS 白名单

编辑 `backend/.env`：

```env
ENV=production
JWT_SECRET=<上一步生成的强随机值>
CORS_ALLOW_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

**禁止使用 `*`** — FastAPI 与 `allow_credentials=True` 不兼容。

### 3. 清理测试数据

```bash
cd backend
python cleanup_test_data.py --dry-run   # 预览
python cleanup_test_data.py --apply     # 实际删除
```

清理规则：
- `users` 中 username 以 `mp_` / `test_` 开头的账号（含关联 sessions / characters / logs / combat / members）
- `modules` 中 name 以 `__test_module` 开头的
- 保留 `username='test'` 等手动创建的账号

## 📦 二、数据库迁移

### 生产 PostgreSQL 初始化

```bash
# 在生产环境
cd backend
pip install -r requirements.txt

# 已有 v0.8 及以前数据库（数据已存在）
alembic stamp 20260417_0001_baseline_v08
alembic upgrade head

# 全新数据库
alembic upgrade head
```

## 🐳 三、Docker 部署

### 重新构建镜像（v0.10 变更）

```bash
cd <项目根>
docker compose build --no-cache backend frontend
docker compose up -d
```

### 验证

```bash
# Backend 健康
curl https://yourdomain.com/api/health
# 期望: {"status":"ok","version":"0.1.0"}

# Sprite 资源（39 个 PNG + _INDEX.json）
curl -I https://yourdomain.com/sprites/_INDEX.json
curl -I https://yourdomain.com/sprites/paladin.png

# 新 API 端点
curl -I https://yourdomain.com/api/game/combat/xxx/skill-bar  # 应 401（未登录）或 404
```

## 🌐 四、Nginx 配置（WebSocket 要点）

多人联机用 WebSocket，Nginx 需要升级头：

```nginx
location /api/ws/ {
    proxy_pass http://backend:8002/ws/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_set_header Host $host;
}

location /api/ {
    proxy_pass http://backend:8002/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /sprites/ {
    # 像素 PNG 缓存一年（文件内容不变）
    alias /var/www/frontend/dist/sprites/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## 🎨 五、像素 Sprite 系统

### 当前资源（v0.10.3）

- 39 个 PNG（`frontend/public/sprites/*.png`，共 ~39KB）
- 7 个"原型"精灵 + 32 个通过色相偏移派生的变体
- `_INDEX.json` 定义 kind → fallback + size 映射
- 体型缩放：S(0.75x) / M(1x) / L(1.5x) / H(2x) / G(3x)

### 如需后期换成手绘高清版

1. 替换 `frontend/public/sprites/{kind}.png` 为同名新文件
2. 无需改代码；保持 16×24 或 16:24 比例即可

### 重新生成

```bash
cd <项目根>
python scripts/generate_sprite_pngs.py
```

## 🧪 六、部署后冒烟测试（最低覆盖）

在生产环境用真实账号手动跑一遍：

1. **注册 + 登录** → 获得 token（localStorage 检查）
2. **上传模组** → 等待 parse_status 变 done
3. **创建角色**（Step 1-4 或 1-5 或 1-6）→ 生成队伍 → 开始冒险
4. **对话冒险** → 说一句话，验证 DM 响应 + stage 打字机
5. **翻开对话历史** → 验证章节 + 筛选器
6. **触发战斗** → 攻击/施法/移动/结束回合/AI 回合循环 → 胜利/失败结算
7. **开多人房间** → 房间码分享（另一账号加入）→ WebSocket 事件实时同步
8. **刷新页面** → localStorage 保留 + 会话恢复

## 📊 七、监控与日志

- **后端日志**：`docker compose logs -f backend --tail=200`
- **前端错误**：浏览器 Console + Network 面板
- **LLM 调用失败率**：关注 AiHubMix dashboard 的 4xx/5xx 比例
- **数据库大小**：`ai_trpg.db` 或 PG `pg_database_size()`
- **ChromaDB**：`chromadb_data/` 目录大小（向量持久化）

## 🚨 八、已知限制（不阻止上线，记录给用户说明）

- **反应窗口弹窗**：Shield / Uncanny Dodge / Hellish Rebuke 做了骨架，多数子职业特性未接入技能栏
- **像素 sprite 风格化**：当前是"算法变体"，不同敌人在同一变体组（如 skeleton/zombie/ghoul/vampire/lich）外观差异有限
- **多人 DM 发言轮转**：探索阶段按 `speak_done` 推进，如果玩家不点会一直等（已有 30s 心跳超时检测，但没有自动跳过发言）
- **战斗资源回收**：退出战斗时清理不完全，长期可能有僵尸 CombatState（建议定期 cron 清理 `combat_states` 表）

## 🔄 九、回滚方案

```bash
# 保留 v0.9 tag
git tag v0.10-pre-deploy
git push origin v0.10-pre-deploy

# 出问题
git checkout v0.9-multiplayer-stable
docker compose build --no-cache && docker compose up -d
alembic downgrade 20260417_0002_multiplayer  # 回滚 schema 到多人联机
```

---

## ✅ 上线 checklist（勾选完成）

- [ ] `.env` 设置 `JWT_SECRET`（≥32 字节）
- [ ] `.env` 设置 `ENV=production`
- [ ] `.env` 设置 `CORS_ALLOW_ORIGINS` 为实际域名
- [ ] 运行 `cleanup_test_data.py --apply`
- [ ] 运行 `alembic upgrade head`
- [ ] `docker compose build --no-cache`
- [ ] `docker compose up -d`
- [ ] Nginx 配置含 WebSocket upgrade header
- [ ] Nginx 配置含 `/sprites/` 长缓存
- [ ] 冒烟测试 8 步全部通过
- [ ] 开放 1-5 个内测用户（不要直接开放注册）
- [ ] 观察 24 小时日志
- [ ] 开放公测
