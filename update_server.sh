#!/bin/bash
# ═══════════════════════════════════════════════════
# AI跑团平台 — 服务器更新脚本
# 从 GitHub 拉取最新代码并重启服务
#
# 使用方式：SSH 到服务器后执行：
#   bash /opt/ai-trpg/app/update_server.sh
# ═══════════════════════════════════════════════════

set -e

APP_DIR="/opt/ai-trpg"
REPO_DIR="$APP_DIR/app"

ensure_nginx_websocket_proxy() {
    if ! command -v nginx &>/dev/null; then
        return 0
    fi

    local nginx_conf=""
    for f in /etc/nginx/conf.d/*.conf /etc/nginx/sites-enabled/*; do
        [ -f "$f" ] || continue
        if sudo grep -qE "location /api/|proxy_pass .*127\.0\.0\.1:8000|proxy_pass .*:8000" "$f"; then
            nginx_conf="$f"
            break
        fi
    done

    if [ -z "$nginx_conf" ]; then
        echo "  Nginx: 未找到应用代理配置，跳过 /api/ws 自动修复"
        return 0
    fi

    if sudo grep -q "location /api/ws" "$nginx_conf"; then
        echo "  Nginx: /api/ws WebSocket 代理已存在"
        return 0
    fi

    if ! command -v python3 &>/dev/null; then
        echo "  Nginx: 缺少 python3，无法自动插入 /api/ws 代理；请手动配置"
        return 0
    fi

    local backup="${nginx_conf}.stage8-ws.$(date +%Y%m%d%H%M%S).bak"
    sudo cp "$nginx_conf" "$backup"
    echo "  Nginx: 正在为 $nginx_conf 添加 /api/ws WebSocket 代理（备份: $backup）"

    if sudo python3 - "$nginx_conf" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
if "location /api/ws" in text:
    raise SystemExit(0)

match = re.search(r"(?m)^(?P<indent>\s*)location\s+/api/\s*\{", text)
if not match:
    raise SystemExit("Could not find location /api/ block.")

indent = match.group("indent")
block = f"""{indent}# Backend WebSocket proxy (frontend uses /api/ws/sessions/...)
{indent}location /api/ws/ {{
{indent}    proxy_pass http://127.0.0.1:8000/ws/;
{indent}    proxy_http_version 1.1;
{indent}    proxy_set_header Upgrade $http_upgrade;
{indent}    proxy_set_header Connection "upgrade";
{indent}    proxy_set_header Host $host;
{indent}    proxy_set_header X-Real-IP $remote_addr;
{indent}    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
{indent}    proxy_read_timeout 3600s;
{indent}    proxy_send_timeout 3600s;
{indent}}}

"""
path.write_text(text[:match.start()] + block + text[match.start():], encoding="utf-8")
PY
    then
        if sudo nginx -t >/dev/null 2>&1; then
            echo "  Nginx: /api/ws WebSocket 代理已添加"
        else
            echo "  Nginx: 新配置校验失败，已恢复备份"
            sudo cp "$backup" "$nginx_conf"
        fi
    else
        echo "  Nginx: 自动插入 /api/ws 代理失败，已恢复备份"
        sudo cp "$backup" "$nginx_conf"
    fi
}

echo "══════════════════════════════════════"
echo "  AI跑团平台 — 更新到最新版本"
echo "══════════════════════════════════════"

# ── 1. 拉取最新代码 ──
echo ""
echo "[1/5] 拉取最新代码..."
cd "$REPO_DIR"
git fetch origin
git reset --hard origin/main
echo "  当前版本: $(git log --oneline -1)"

# ── 2. 更新后端依赖 ──
echo ""
echo "[2/5] 更新后端依赖..."
cd "$REPO_DIR/backend"
if [ -d "$APP_DIR/venv" ]; then
    source "$APP_DIR/venv/bin/activate"
elif [ -d ".venv" ]; then
    source ".venv/bin/activate"
else
    echo "  创建虚拟环境..."
    python3 -m venv "$APP_DIR/venv"
    source "$APP_DIR/venv/bin/activate"
fi
pip install -r requirements.txt -q
echo "  后端依赖更新完成"

# ── 3. 更新前端依赖并构建 ──
echo ""
echo "[3/5] 更新前端并构建..."
cd "$REPO_DIR/frontend"
npm install --silent 2>/dev/null
npm run build
echo "  前端构建完成"

# ── 4. 复制 Fantastic Dice 资源 ──
echo ""
echo "[4/5] 复制骰子资源..."
if [ -d "node_modules/@3d-dice/dice-box/dist/assets" ]; then
    mkdir -p public/assets
    cp -r node_modules/@3d-dice/dice-box/dist/assets/* public/assets/ 2>/dev/null || true
    # 同时复制到 dist 目录（生产环境）
    if [ -d "dist" ]; then
        mkdir -p dist/assets
        cp -r node_modules/@3d-dice/dice-box/dist/assets/* dist/assets/ 2>/dev/null || true
    fi
    echo "  骰子资源已复制"
else
    echo "  跳过（dice-box 资源不存在）"
fi

# ── 5. 重启服务 ──
echo ""
echo "[5/5] 重启服务..."
# 尝试 systemd
if systemctl is-active ai-trpg-backend &>/dev/null; then
    sudo systemctl restart ai-trpg-backend
    echo "  后端服务已重启 (systemd)"
elif systemctl is-active ai-trpg &>/dev/null; then
    sudo systemctl restart ai-trpg
    echo "  服务已重启 (systemd)"
else
    # 手动重启
    echo "  未检测到 systemd 服务，手动重启..."
    pkill -f "uvicorn main:app" 2>/dev/null || true
    sleep 1
    cd "$REPO_DIR/backend"
    source "$APP_DIR/venv/bin/activate" 2>/dev/null || source ".venv/bin/activate" 2>/dev/null
    nohup python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 > "$APP_DIR/uvicorn.log" 2>&1 &
    echo "  后端已启动 (PID: $!)"
fi

# ── Nginx reload（如果有）──
if command -v nginx &>/dev/null; then
    ensure_nginx_websocket_proxy
    sudo nginx -s reload 2>/dev/null && echo "  Nginx 已重载" || true
fi

echo ""
echo "══════════════════════════════════════"
echo "  更新完成！"
echo "  版本: $(cd $REPO_DIR && git log --oneline -1)"
echo "══════════════════════════════════════"
