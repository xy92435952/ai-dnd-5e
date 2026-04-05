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
    sudo nginx -s reload 2>/dev/null && echo "  Nginx 已重载" || true
fi

echo ""
echo "══════════════════════════════════════"
echo "  更新完成！"
echo "  版本: $(cd $REPO_DIR && git log --oneline -1)"
echo "══════════════════════════════════════"
