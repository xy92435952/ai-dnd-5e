# AI跑团平台 — 腾讯云部署指南

> 最后更新：2026-04-03
> 适用版本：Phase 13（LangGraph + 完整 5e 战斗系统）

---

## 目录

1. [服务器选型建议](#1-服务器选型建议)
2. [环境准备](#2-环境准备)
3. [代码部署](#3-代码部署)
4. [环境变量配置](#4-环境变量配置)
5. [前端构建](#5-前端构建)
6. [后端启动（Systemd 服务）](#6-后端启动systemd-服务)
7. [Nginx 反向代理](#7-nginx-反向代理)
8. [HTTPS 证书（Let's Encrypt）](#8-https-证书lets-encrypt)
9. [安全注意事项](#9-安全注意事项)
10. [监控与维护](#10-监控与维护)
11. [成本估算](#11-成本估算)
12. [上线检查清单](#12-上线检查清单)
13. [常见问题排查](#13-常见问题排查)

---

## 1. 服务器选型建议

### 推荐配置

| 配置项 | 推荐值 | 说明 |
|--------|--------|------|
| 机型 | CVM 标准型 S5 | 通用计算实例，性价比高 |
| CPU | 2 核（推荐 4 核） | ChromaDB 向量检索 + Python 异步 IO |
| 内存 | 4 GB（推荐 8 GB） | ChromaDB 加载向量索引 + SQLite 缓存 + uvicorn 工作进程 |
| 系统盘 | 50 GB SSD 云硬盘 | 操作系统 + 代码 + Python 虚拟环境 |
| 数据盘 | 20 GB SSD（可选） | SQLite 数据库 + ChromaDB 向量数据 + LangGraph 记忆 |
| 带宽 | 5 Mbps（按量计费亦可） | 主要流量：LLM API 调用（HTTPS）+ 前端静态资源 |
| 地域 | 上海 / 广州 / 北京 | 选离用户最近的地域，降低访问延迟 |
| 操作系统 | Ubuntu 22.04 LTS | 长期支持版，Python 3.11+ 原生支持 |

### 轻量应用服务器方案（更便宜）

如果仅用于个人测试或小规模演示，可选择腾讯云轻量应用服务器（Lighthouse）：

| 配置 | 价格 | 说明 |
|------|------|------|
| 2 核 4G 60GB SSD 6Mbps | ~65 元/月 | 入门级，适合 1-3 人测试 |
| 4 核 8G 100GB SSD 8Mbps | ~130 元/月 | 推荐，可支撑 5-10 人同时使用 |

---

## 2. 环境准备

### 2.1 系统更新与基础工具

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y git curl wget unzip software-properties-common
```

### 2.2 安装 Python 3.11+

```bash
# Ubuntu 22.04 默认 Python 3.10，需要添加 deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# 验证
python3.11 --version
# Python 3.11.x
```

### 2.3 安装 Node.js 18+ (用于前端构建)

```bash
# 使用 NodeSource 官方源
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# 验证
node --version   # v18.x
npm --version    # 9.x+
```

### 2.4 安装 Nginx

```bash
sudo apt install -y nginx

# 验证
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 2.5 创建项目目录

```bash
# 创建项目根目录
sudo mkdir -p /opt/ai-trpg
sudo chown $USER:$USER /opt/ai-trpg

# 创建 Python 虚拟环境
python3.11 -m venv /opt/ai-trpg/venv
source /opt/ai-trpg/venv/bin/activate

# 验证虚拟环境
which python
# /opt/ai-trpg/venv/bin/python
python --version
# Python 3.11.x
```

---

## 3. 代码部署

### 方式一：Git Clone（推荐）

```bash
cd /opt/ai-trpg
git clone <your-repo-url> app
```

### 方式二：本地上传（无 Git 仓库时）

在本地 Windows 上打包：
```powershell
# 在项目根目录，排除不需要的文件
cd D:\program\game
tar -czf ai-trpg.tar.gz --exclude=node_modules --exclude=__pycache__ --exclude=.git --exclude=frontend/dist --exclude=backend/chromadb_data --exclude=backend/*.db .
```

上传到服务器：
```bash
# 使用 scp 上传
scp ai-trpg.tar.gz user@your-server-ip:/opt/ai-trpg/

# 在服务器上解压
cd /opt/ai-trpg
mkdir app && cd app
tar -xzf ../ai-trpg.tar.gz
```

### 安装后端依赖

```bash
source /opt/ai-trpg/venv/bin/activate
cd /opt/ai-trpg/app/backend

# 安装依赖
pip install -r requirements.txt

# 可能需要的系统依赖（用于 pymupdf / chromadb）
sudo apt install -y build-essential libffi-dev
```

### 运行数据库迁移

```bash
cd /opt/ai-trpg/app/backend

# 按顺序执行所有迁移脚本
python migrate_multiclass.py
python migrate_turn_states.py
python migrate_dify_conversation_id.py
python migrate_condition_durations.py

# 如有 Phase 12/13 的迁移脚本，也一并执行
# python migrate_phase12.py
# python migrate_p0_features.py
```

---

## 4. 环境变量配置

```bash
cd /opt/ai-trpg/app/backend

# 从模板创建配置文件
cp .env.example .env

# 编辑配置
nano .env
```

`.env` 文件内容：

```env
# ========================================
# LLM 配置（OpenAI 兼容 API）
# ========================================
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_BASE_URL=https://aihubmix.com/v1
LLM_MODEL=claude-sonnet-4-6

# ========================================
# ChromaDB 本地向量库（自动创建目录）
# ========================================
CHROMADB_PATH=./chromadb_data

# ========================================
# LangGraph 对话记忆（独立 SQLite 文件）
# ========================================
LANGGRAPH_DB_PATH=./langgraph_memory.db
```

**重要**：设置文件权限，防止 API Key 泄露：

```bash
chmod 600 /opt/ai-trpg/app/backend/.env
```

---

## 5. 前端构建

```bash
cd /opt/ai-trpg/app/frontend

# 安装依赖
npm install

# 构建生产版本
npm run build
```

构建完成后，静态文件输出到 `dist/` 目录。该目录将由 Nginx 直接提供服务。

**验证构建成功**：

```bash
ls -la dist/
# 应包含 index.html, assets/ 目录
```

---

## 6. 后端启动（Systemd 服务）

### 6.1 创建 Systemd 服务文件

```bash
sudo nano /etc/systemd/system/ai-trpg.service
```

写入以下内容：

```ini
[Unit]
Description=AI TRPG Backend (FastAPI + LangGraph)
After=network.target
Documentation=https://github.com/your-repo

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/ai-trpg/app/backend
ExecStart=/opt/ai-trpg/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5

# 环境变量文件
EnvironmentFile=/opt/ai-trpg/app/backend/.env

# 进程限制
LimitNOFILE=65536

# 日志
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ai-trpg

# 安全加固
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

> **注意**：`--workers 1` 是因为 SQLite 不适合多进程写入。如果未来迁移到 PostgreSQL，可增加 worker 数量。

### 6.2 设置文件权限

```bash
# 让 www-data 用户能访问项目文件
sudo chown -R www-data:www-data /opt/ai-trpg/app/backend/
sudo chown -R www-data:www-data /opt/ai-trpg/app/frontend/dist/

# 虚拟环境需要可读
sudo chmod -R o+rX /opt/ai-trpg/venv/
```

### 6.3 启动服务

```bash
# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start ai-trpg

# 设置开机自启
sudo systemctl enable ai-trpg

# 检查状态
sudo systemctl status ai-trpg
```

### 6.4 验证后端运行

```bash
# 检查健康端点
curl http://127.0.0.1:8000/health

# 预期返回
# {"status": "ok"}
```

---

## 7. Nginx 反向代理

### 7.1 创建 Nginx 配置

```bash
sudo nano /etc/nginx/sites-available/ai-trpg
```

写入以下内容：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名或服务器 IP

    # 客户端上传文件大小限制（模组文件可能较大）
    client_max_body_size 50M;

    # 前端静态文件
    location / {
        root /opt/ai-trpg/app/frontend/dist;
        try_files $uri $uri/ /index.html;

        # 静态资源缓存
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 7d;
            add_header Cache-Control "public, immutable";
        }
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # LLM 调用可能耗时较长（模组解析最长 2 分钟）
        proxy_read_timeout 300s;
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;

        # WebSocket 支持（如未来需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 后端 API 文档（可选，生产环境可注释掉）
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host $host;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8000/redoc;
        proxy_set_header Host $host;
    }

    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
    }

    # 禁止访问隐藏文件
    location ~ /\. {
        deny all;
        return 404;
    }
}
```

### 7.2 启用配置

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/ai-trpg /etc/nginx/sites-enabled/

# 删除默认站点（可选）
sudo rm -f /etc/nginx/sites-enabled/default

# 测试配置语法
sudo nginx -t

# 重新加载 Nginx
sudo systemctl reload nginx
```

### 7.3 验证

在浏览器访问 `http://your-server-ip`，应能看到前端页面。

---

## 8. HTTPS 证书（Let's Encrypt）

> 前提：需要已备案的域名指向服务器 IP（国内服务器需要 ICP 备案）。

### 8.1 安装 Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 8.2 申请证书

```bash
sudo certbot --nginx -d your-domain.com
```

按提示操作：
1. 输入邮箱地址
2. 同意服务条款
3. 选择是否将 HTTP 重定向到 HTTPS（建议选择 2 = 重定向）

### 8.3 自动续期

Certbot 会自动创建 cron job 或 systemd timer 来续期证书。验证：

```bash
sudo certbot renew --dry-run
```

### 8.4 国内替代方案

如果域名未备案或 Let's Encrypt 访问困难，可使用腾讯云提供的免费 SSL 证书：

1. 登录 [腾讯云 SSL 证书管理](https://console.cloud.tencent.com/ssl)
2. 申请免费 DV 证书（有效期 1 年）
3. 下载 Nginx 格式证书
4. 手动配置到 Nginx：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/your-domain.com_bundle.crt;
    ssl_certificate_key /etc/nginx/ssl/your-domain.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # ... 其他配置同上 ...
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}
```

---

## 9. 安全注意事项

### 9.1 文件权限

```bash
# .env 文件仅限 owner 读写
chmod 600 /opt/ai-trpg/app/backend/.env

# 数据库文件仅限 www-data 读写
chmod 600 /opt/ai-trpg/app/backend/ai_trpg.db
chmod 600 /opt/ai-trpg/app/backend/langgraph_memory.db
```

### 9.2 防火墙配置

```bash
# 安装 ufw（Ubuntu 防火墙）
sudo apt install -y ufw

# 默认拒绝入站
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 允许 SSH
sudo ufw allow 22/tcp

# 允许 HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 启用防火墙
sudo ufw enable

# 查看状态
sudo ufw status
```

> **重要**：不要开放 8000 端口到外网。uvicorn 监听 127.0.0.1，仅接受来自 Nginx 的本地转发。

### 9.3 API Key 安全

- `.env` 文件不要提交到 Git 仓库（已在 `.gitignore` 中）
- 前端代码中不包含任何 API Key（所有 LLM 调用在后端发起）
- Nginx 不代理 `/api/.env` 等敏感路径

### 9.4 腾讯云安全组

在腾讯云控制台配置安全组规则：

| 方向 | 协议 | 端口 | 来源 | 说明 |
|------|------|------|------|------|
| 入站 | TCP | 22 | 你的 IP/0.0.0.0 | SSH 远程管理 |
| 入站 | TCP | 80 | 0.0.0.0/0 | HTTP 访问 |
| 入站 | TCP | 443 | 0.0.0.0/0 | HTTPS 访问 |
| 出站 | ALL | ALL | 0.0.0.0/0 | 允许所有出站（LLM API 调用需要） |

---

## 10. 监控与维护

### 10.1 查看服务状态

```bash
# 服务状态
sudo systemctl status ai-trpg

# 实时日志
sudo journalctl -u ai-trpg -f

# 最近 100 行日志
sudo journalctl -u ai-trpg -n 100

# 过滤错误日志
sudo journalctl -u ai-trpg --since "1 hour ago" | grep -i error
```

### 10.2 Nginx 日志

```bash
# 访问日志
sudo tail -f /var/log/nginx/access.log

# 错误日志
sudo tail -f /var/log/nginx/error.log
```

### 10.3 数据库备份（Cron 定时任务）

```bash
# 创建备份目录
sudo mkdir -p /opt/ai-trpg/backups

# 编辑 cron 任务
sudo crontab -e
```

添加以下行（每天凌晨 3 点备份）：

```cron
# 每日备份 SQLite 数据库（保留最近 7 天）
0 3 * * * cp /opt/ai-trpg/app/backend/ai_trpg.db /opt/ai-trpg/backups/ai_trpg_$(date +\%Y\%m\%d).db && find /opt/ai-trpg/backups -name "ai_trpg_*.db" -mtime +7 -delete

# 每日备份 LangGraph 记忆数据库
0 3 * * * cp /opt/ai-trpg/app/backend/langgraph_memory.db /opt/ai-trpg/backups/langgraph_$(date +\%Y\%m\%d).db && find /opt/ai-trpg/backups -name "langgraph_*.db" -mtime +7 -delete

# 每周备份 ChromaDB 向量数据
0 4 * * 0 tar -czf /opt/ai-trpg/backups/chromadb_$(date +\%Y\%m\%d).tar.gz -C /opt/ai-trpg/app/backend chromadb_data && find /opt/ai-trpg/backups -name "chromadb_*.tar.gz" -mtime +30 -delete
```

### 10.4 磁盘空间监控

```bash
# 查看磁盘使用
df -h

# 查看项目目录大小
du -sh /opt/ai-trpg/app/backend/*.db
du -sh /opt/ai-trpg/app/backend/chromadb_data/
```

### 10.5 重启服务

```bash
# 代码更新后重启后端
sudo systemctl restart ai-trpg

# 前端更新后重新构建
cd /opt/ai-trpg/app/frontend && npm run build
# Nginx 不需要重启（静态文件直接更新）
```

---

## 11. 成本估算

### 月度费用（预估）

| 项目 | 规格 | 月费用（元） | 说明 |
|------|------|-------------|------|
| CVM 2核4G | 标准型 S5 | ~100 | 包年包月更便宜（~70元/月） |
| CVM 4核8G | 标准型 S5 | ~200 | 推荐配置，包年包月 ~140元/月 |
| 轻量 2核4G | Lighthouse | ~65 | 最经济方案 |
| 系统盘 50G SSD | 高性能云硬盘 | 含在 CVM 中 | — |
| 域名 | .com / .cn | ~5 | 首年可能有优惠 |
| SSL 证书 | DV 免费证书 | 0 | 腾讯云提供 |
| AI API | AiHubMix | ~50-200 | 按调用量，Claude Sonnet 较贵 |
| 带宽 5Mbps | 按带宽计费 | 含在 CVM 中 | 或按流量 0.8元/GB |

### 总计

| 方案 | 月费用 | 适用场景 |
|------|--------|----------|
| 经济方案（轻量 2核4G） | ~120-270 元 | 个人测试、1-3 人使用 |
| 标准方案（CVM 2核4G） | ~155-305 元 | 小团队演示 |
| 推荐方案（CVM 4核8G） | ~245-445 元 | 稳定运行、5-10 人使用 |

> AI API 费用与使用量直接相关。每次 DM 交互约消耗 2000-4000 tokens（输入+输出），按 Claude Sonnet 定价约 0.02-0.05 元/次。

---

## 12. 上线检查清单

### 部署前

- [ ] 服务器系统已更新（`apt update && apt upgrade`）
- [ ] Python 3.11+ 已安装
- [ ] Node.js 18+ 已安装
- [ ] Nginx 已安装并启动
- [ ] 防火墙仅开放 22/80/443 端口
- [ ] 腾讯云安全组已配置

### 后端

- [ ] `.env` 文件已配置，API Key 有效
- [ ] `.env` 文件权限为 600
- [ ] `pip install -r requirements.txt` 成功
- [ ] 数据库迁移脚本已全部执行
- [ ] `curl http://127.0.0.1:8000/health` 返回 `{"status": "ok"}`
- [ ] Systemd 服务已创建并设为开机自启

### 前端

- [ ] `npm install` 成功
- [ ] `npm run build` 成功，`dist/` 目录包含 `index.html`
- [ ] Nginx 配置中 `root` 路径指向正确的 `dist/` 目录

### Nginx

- [ ] `sudo nginx -t` 语法测试通过
- [ ] 反向代理 `/api/` 到 `127.0.0.1:8000` 正常
- [ ] `client_max_body_size` 设置足够大（50M+）
- [ ] `proxy_read_timeout` 设置为 300s+

### HTTPS

- [ ] SSL 证书已安装（Let's Encrypt 或腾讯云免费证书）
- [ ] HTTP 自动重定向到 HTTPS
- [ ] 证书自动续期已配置

### 功能验证

- [ ] 访问首页正常显示 Tavern Fantasy 主题 UI
- [ ] 模组上传成功（PDF/DOCX/MD/TXT）
- [ ] 模组解析完成（WF1 LangGraph 正常工作）
- [ ] 角色创建完整流程（含战斗风格/装备/法术/专长）
- [ ] AI 队友生成成功（WF2）
- [ ] 探索模式 DM 响应正常（WF3 explore）
- [ ] 战斗模式正常触发和运行（WF3 combat）
- [ ] 3D 骰子动画正常显示
- [ ] 长休/短休功能正常

---

## 13. 常见问题排查

### Q: 后端启动失败，提示 SQLite 相关错误

```bash
# 检查 SQLite 版本
python3.11 -c "import sqlite3; print(sqlite3.sqlite_version)"
# 需要 3.35+

# 如果版本太旧
sudo apt install -y libsqlite3-dev
# 然后重新编译 Python（或使用 deadsnakes PPA 的版本）
```

### Q: ChromaDB 初始化失败

```bash
# 确保目录存在且可写
sudo mkdir -p /opt/ai-trpg/app/backend/chromadb_data
sudo chown www-data:www-data /opt/ai-trpg/app/backend/chromadb_data

# 检查磁盘空间
df -h
```

### Q: LLM API 调用超时

```bash
# 检查网络连通性
curl -v https://aihubmix.com/v1/models

# 如果被墙，考虑使用国内 LLM 提供商或配置代理
# 在 .env 中可切换模型：
# LLM_BASE_URL=https://your-alternative-api.com/v1
# LLM_MODEL=gpt-4o
```

### Q: Nginx 502 Bad Gateway

```bash
# 检查后端是否在运行
sudo systemctl status ai-trpg

# 检查后端端口
ss -tlnp | grep 8000

# 查看后端日志
sudo journalctl -u ai-trpg -n 50
```

### Q: 前端页面空白

```bash
# 检查构建产物
ls -la /opt/ai-trpg/app/frontend/dist/

# 检查 Nginx 配置中的 root 路径
sudo nginx -t

# 查看 Nginx 错误日志
sudo tail -20 /var/log/nginx/error.log
```

### Q: 模组上传失败（413 Request Entity Too Large）

```bash
# 增加 Nginx 上传限制
# 在 nginx 配置中添加或修改：
client_max_body_size 100M;

sudo nginx -t && sudo systemctl reload nginx
```

### Q: SQLAlchemy JSON 列变更不持久化

这是一个已知问题（Phase 13 已修复）。如果遇到敌人 HP 不减少、回合状态不重置等现象，确认代码中所有 JSON 列的 in-place 变更后都调用了 `flag_modified()`。

### Q: 内存不足（OOM Killer）

```bash
# 查看内存使用
free -h

# 如果 ChromaDB 占用过多内存，可以限制服务内存
# 在 systemd 服务文件中添加：
# MemoryLimit=3G
```
