#!/bin/bash
# ═══════════════════════════════════════════════════════════
# AI 跑团平台 — v0.9 → v0.10 升级脚本（OpenCloudOS Server 9）
#
# 自动完成：
#   1. 备份数据库
#   2. git pull + 装依赖 + 构建前端
#   3. 首次 alembic baseline + upgrade head
#   4. .env 追加 JWT_SECRET / ENV / CORS_ALLOW_ORIGINS（如缺失）
#   5. 补 Nginx WebSocket + sprites 长缓存配置（如缺失）
#   6. 重启后端
#
# 使用（服务器上直接跑）：
#   bash <(curl -fsSL https://raw.githubusercontent.com/xy92435952/ai-dnd-5e/main/upgrade_v10.sh) 你的域名.com
#
# 或先下载再跑（方便看内容）：
#   curl -O https://raw.githubusercontent.com/xy92435952/ai-dnd-5e/main/upgrade_v10.sh
#   chmod +x upgrade_v10.sh
#   sudo ./upgrade_v10.sh 你的域名.com
# ═══════════════════════════════════════════════════════════

set -e   # 任何步骤出错立刻停

# ───── 参数 ─────
DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
    echo "⚠ 未提供域名，CORS 将用通配占位。用法: bash upgrade_v10.sh yourdomain.com"
    DOMAIN="localhost"
fi

APP_DIR="/opt/ai-trpg"
REPO_DIR="$APP_DIR/app"
VENV_DIR="$APP_DIR/venv"

# ───── 小工具 ─────
log() { echo ""; echo "━━━ $1 ━━━"; }
die() { echo "✗ 错误: $1" >&2; exit 1; }

# ───── 0. 前置检查 ─────
log "0. 前置检查"
[ -d "$REPO_DIR/.git" ] || die "未找到 $REPO_DIR（请先用 deploy.sh 做过初始部署）"
command -v python3 >/dev/null || die "python3 未安装"
command -v npm >/dev/null || die "npm 未安装（需要 Node 20+）"

# ───── 1. 备份数据库 ─────
log "1. 备份数据库"
TS=$(date +%Y%m%d_%H%M%S)
if [ -f "$REPO_DIR/backend/ai_trpg.db" ]; then
    cp "$REPO_DIR/backend/ai_trpg.db" "$REPO_DIR/backend/ai_trpg.db.v09.${TS}.bak"
    echo "  ✓ SQLite 已备份 → ai_trpg.db.v09.${TS}.bak"
elif command -v docker >/dev/null && docker compose -f "$REPO_DIR/docker-compose.yml" ps postgres 2>/dev/null | grep -q Up; then
    docker compose -f "$REPO_DIR/docker-compose.yml" exec -T postgres \
        pg_dump -U ai_trpg ai_trpg > "$APP_DIR/backup_v09_${TS}.sql"
    echo "  ✓ PostgreSQL 已备份 → $APP_DIR/backup_v09_${TS}.sql"
else
    echo "  ⚠ 未检测到数据库，跳过备份（如果是全新部署可忽略）"
fi

# ───── 2. 拉最新代码 ─────
log "2. 拉取 v0.10 代码"
cd "$REPO_DIR"
git fetch origin
git reset --hard origin/main
NEW_COMMIT=$(git log --oneline -1)
echo "  ✓ 当前: $NEW_COMMIT"

# ───── 3. 后端依赖 ─────
log "3. 更新后端依赖"
cd "$REPO_DIR/backend"
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
elif [ -d ".venv" ]; then
    source ".venv/bin/activate"
else
    echo "  创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
fi
pip install -r requirements.txt -q
echo "  ✓ 后端依赖完成"

# ───── 4. 前端构建 ─────
log "4. 前端依赖 + 构建"
cd "$REPO_DIR/frontend"
npm install --silent 2>&1 | tail -3
npm run build 2>&1 | tail -5
# 复制 dice-box 资源
if [ -d "node_modules/@3d-dice/dice-box/dist/assets" ]; then
    mkdir -p public/assets dist/assets
    cp -r node_modules/@3d-dice/dice-box/dist/assets/* dist/assets/ 2>/dev/null || true
    cp -r node_modules/@3d-dice/dice-box/dist/assets/* public/assets/ 2>/dev/null || true
fi
echo "  ✓ 前端构建完成（dist 大小: $(du -sh dist | awk '{print $1}')）"

# ───── 5. Alembic 迁移 ─────
log "5. 数据库迁移（alembic）"
cd "$REPO_DIR/backend"
CUR=$(alembic current 2>&1 | tail -1 || echo "")
if echo "$CUR" | grep -q "20260417_0002_multiplayer"; then
    echo "  ✓ 已是最新版本，无需迁移"
elif echo "$CUR" | grep -q "20260417_0001_baseline_v08"; then
    echo "  从 baseline 升级..."
    alembic upgrade head
else
    echo "  首次使用 alembic — 标记基线 + 升级..."
    alembic stamp 20260417_0001_baseline_v08
    alembic upgrade head
fi
alembic current
echo "  ✓ 数据库迁移完成"

# ───── 6. 配置 .env（追加缺失项） ─────
log "6. 检查/追加生产环境变量"
ENV_FILE="$REPO_DIR/backend/.env"
touch "$ENV_FILE"

append_if_missing() {
    local key="$1"
    local value="$2"
    if ! grep -q "^${key}=" "$ENV_FILE"; then
        echo "${key}=${value}" >> "$ENV_FILE"
        echo "  ✓ 追加 $key"
    else
        echo "  · $key 已存在，跳过"
    fi
}

# 确保文件末尾有换行
[ -n "$(tail -c 1 "$ENV_FILE")" ] && echo "" >> "$ENV_FILE"

append_if_missing "ENV" "production"
append_if_missing "CORS_ALLOW_ORIGINS" "https://${DOMAIN},http://${DOMAIN}"
JWT=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
append_if_missing "JWT_SECRET" "$JWT"

# ───── 7. Nginx 配置（如需要） ─────
log "7. Nginx WebSocket + sprites 配置检查"
NGINX_CONF=""
for f in /etc/nginx/conf.d/*.conf /etc/nginx/sites-enabled/*; do
    [ -f "$f" ] && grep -l "proxy_pass.*:8000\|proxy_pass.*127\.0\.0\.1" "$f" 2>/dev/null && {
        NGINX_CONF="$f"
        break
    }
done

if [ -n "$NGINX_CONF" ]; then
    echo "  检测到配置: $NGINX_CONF"

    # 检查 WebSocket 块
    if grep -q "location /api/ws" "$NGINX_CONF"; then
        echo "  · WebSocket 块已存在"
    else
        echo "  ⚠ 未找到 /api/ws 配置（多人联机会连不上）"
        echo "    请手动在 /api/ 块之前加入："
        cat <<'NGXEOF'

    location /api/ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_set_header Host $host;
    }

NGXEOF
    fi

    # 检查 sprites 缓存
    if grep -q "location /sprites" "$NGINX_CONF"; then
        echo "  · sprites 缓存块已存在"
    else
        echo "  ⚠ 未找到 /sprites 配置（可选优化，不影响功能）"
    fi

    # reload
    sudo nginx -t 2>&1 | tail -3
    if sudo nginx -t 2>&1 | grep -q "successful"; then
        sudo nginx -s reload && echo "  ✓ Nginx 已 reload"
    fi
else
    echo "  ⚠ 未检测到 Nginx 配置，跳过"
fi

# ───── 8. 重启后端 ─────
log "8. 重启后端"
if systemctl list-units --all | grep -q "ai-trpg-backend"; then
    sudo systemctl restart ai-trpg-backend
    echo "  ✓ systemd 已重启 ai-trpg-backend"
elif systemctl list-units --all | grep -q "ai-trpg"; then
    sudo systemctl restart ai-trpg
    echo "  ✓ systemd 已重启 ai-trpg"
else
    pkill -f 'uvicorn main:app' 2>/dev/null || true
    sleep 1
    cd "$REPO_DIR/backend"
    source "$VENV_DIR/bin/activate" 2>/dev/null || source ".venv/bin/activate" 2>/dev/null
    nohup python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 \
        > "$APP_DIR/uvicorn.log" 2>&1 &
    echo "  ✓ 手动启动 (PID: $!)"
fi

# 等服务起来
sleep 3

# ───── 9. 冒烟验证 ─────
log "9. 冒烟验证"
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health)
if [ "$HEALTH" = "200" ]; then
    echo "  ✓ 后端健康: $(curl -s http://127.0.0.1:8000/health)"
else
    echo "  ⚠ 后端返回 $HEALTH，查看日志:"
    echo "    tail -50 $APP_DIR/uvicorn.log"
    [ -f "$APP_DIR/uvicorn.log" ] && tail -10 "$APP_DIR/uvicorn.log"
fi

# 检查 sprite 资源是否就位
SPRITE_COUNT=$(ls "$REPO_DIR/frontend/dist/sprites/"*.png 2>/dev/null | wc -l)
echo "  ✓ 像素 PNG: $SPRITE_COUNT 个"

# ───── 完成 ─────
echo ""
echo "═══════════════════════════════════════"
echo "  ✓ v0.10 升级完成"
echo "═══════════════════════════════════════"
echo "  版本: $NEW_COMMIT"
echo "  数据库: $(cd "$REPO_DIR/backend" && alembic current 2>&1 | tail -1)"
echo "  备份: $REPO_DIR/backend/ai_trpg.db.v09.${TS}.bak"
echo ""
echo "下一步：浏览器打开 https://${DOMAIN} 跑一遍冒烟："
echo "  1. 登录/注册"
echo "  2. 上传模组 → 创建角色（新 7 步向导）"
echo "  3. 对话冒险（打字机效果）"
echo "  4. 开战斗（命中率预测 + 技能栏）"
echo "  5. 多人房间（右上角 ☰ 多人联机）"
echo ""
echo "如遇问题：tail -f $APP_DIR/uvicorn.log"
echo "═══════════════════════════════════════"
