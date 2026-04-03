#!/bin/bash
# ═══════════════════════════════════════════════════
# AI跑团平台 — 腾讯云一键部署脚本
# 适配 OpenCloudOS / CentOS 系统（Node.js 镜像）
#
# 使用方式：
#   1. scp 上传项目到 /opt/ai-trpg/app/
#   2. ssh 登录服务器
#   3. bash /opt/ai-trpg/app/deploy.sh
# ═══════════════════════════════════════════════════

set -e
echo "══════════════════════════════════════"
echo "  AI跑团平台 一键部署"
echo "  系统: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
echo "══════════════════════════════════════"

APP_DIR="/opt/ai-trpg"

# ── 检测包管理器 ──
if command -v dnf &> /dev/null; then
    PKG="dnf"
elif command -v yum &> /dev/null; then
    PKG="yum"
elif command -v apt &> /dev/null; then
    PKG="apt"
else
    echo "未识别的包管理器，请手动安装依赖"; exit 1
fi
echo "  包管理器: $PKG"

# ── 1. 安装 Python 3.11 ──
echo ""
echo "[1/8] 安装 Python..."
if command -v python3.11 &> /dev/null; then
    echo "  Python 3.11 已存在"
elif command -v python3 &> /dev/null; then
    PY_VER=$(python3 --version 2>&1 | awk '{print $2}')
    echo "  已有 Python $PY_VER，将使用 python3"
else
    if [ "$PKG" = "dnf" ] || [ "$PKG" = "yum" ]; then
        sudo $PKG install -y python3 python3-pip python3-devel
    else
        sudo apt update -qq && sudo apt install -y python3 python3-venv python3-pip
    fi
fi

# 确定 python 命令
PYTHON=$(command -v python3.11 || command -v python3)
echo "  使用: $PYTHON ($($PYTHON --version))"

# ── 2. 安装 Nginx ──
echo ""
echo "[2/8] 安装 Nginx..."
if command -v nginx &> /dev/null; then
    echo "  Nginx 已存在"
else
    if [ "$PKG" = "dnf" ] || [ "$PKG" = "yum" ]; then
        sudo $PKG install -y nginx
    else
        sudo apt install -y nginx
    fi
fi
sudo systemctl enable nginx

# ── 3. 检查 Node.js ──
echo ""
echo "[3/8] 检查 Node.js..."
if command -v node &> /dev/null; then
    echo "  Node.js $(node --version) 已存在"
else
    echo "  安装 Node.js 18..."
    if [ "$PKG" = "dnf" ] || [ "$PKG" = "yum" ]; then
        curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
        sudo $PKG install -y nodejs
    else
        curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
        sudo apt install -y nodejs
    fi
fi

# ── 4. 检查项目代码 ──
echo ""
echo "[4/8] 检查项目代码..."
if [ ! -f "$APP_DIR/app/backend/main.py" ]; then
    echo ""
    echo "  ⚠ 项目代码未找到！"
    echo ""
    echo "  请先上传代码到 $APP_DIR/app/"
    echo "  在本地执行："
    echo "    scp -r D:/program/game/ root@$(curl -s ifconfig.me 2>/dev/null || echo '你的IP'):$APP_DIR/app/"
    echo ""
    echo "  上传完成后重新运行: bash $APP_DIR/app/deploy.sh"
    exit 0
fi
echo "  项目代码: $APP_DIR/app/"

# ── 5. Python 虚拟环境 + 依赖 ──
echo ""
echo "[5/8] 配置 Python 环境..."
$PYTHON -m venv $APP_DIR/venv 2>/dev/null || $PYTHON -m ensurepip && $PYTHON -m venv $APP_DIR/venv
source $APP_DIR/venv/bin/activate
pip install --upgrade pip -q
pip install -r $APP_DIR/app/backend/requirements.txt -q
echo "  虚拟环境: $APP_DIR/venv/"

# 数据库迁移
cd $APP_DIR/app/backend
python migrate_phase12.py 2>/dev/null || echo "  migrate_phase12: skipped/done"
python migrate_p0_features.py 2>/dev/null || echo "  migrate_p0: skipped/done"

# .env 配置
if [ ! -f "$APP_DIR/app/backend/.env" ]; then
    cp $APP_DIR/app/backend/.env.example $APP_DIR/app/backend/.env
    echo ""
    echo "  ⚠ 请编辑 .env 填入 API Key："
    echo "  nano $APP_DIR/app/backend/.env"
    echo ""
fi

# ── 6. 前端构建 ──
echo ""
echo "[6/8] 构建前端..."
cd $APP_DIR/app/frontend

# 确保 vite proxy 指向 8000（生产环境通过 Nginx 代理，不需要 proxy）
npm install --silent 2>&1 | tail -1
npm run build
echo "  构建完成: $APP_DIR/app/frontend/dist/"

# 复制骰子纹理到 dist
if [ -d "$APP_DIR/app/frontend/public/textures" ]; then
    cp -r $APP_DIR/app/frontend/public/textures $APP_DIR/app/frontend/dist/
    echo "  骰子纹理已复制到 dist/"
fi

# ── 7. Systemd 服务 ──
echo ""
echo "[7/8] 配置后端服务..."
sudo tee /etc/systemd/system/ai-trpg.service > /dev/null <<EOF
[Unit]
Description=AI TRPG Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR/app/backend
ExecStart=$APP_DIR/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
Environment=PATH=$APP_DIR/venv/bin:/usr/bin:/usr/local/bin

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ai-trpg
sudo systemctl restart ai-trpg
sleep 3

if sudo systemctl is-active --quiet ai-trpg; then
    echo "  后端服务: 运行中 ✓"
else
    echo "  后端服务: 启动失败！查看日志: journalctl -u ai-trpg -n 20"
    sudo journalctl -u ai-trpg -n 10 --no-pager
fi

# ── 8. Nginx 配置 ──
echo ""
echo "[8/8] 配置 Nginx..."
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

sudo tee /etc/nginx/conf.d/ai-trpg.conf > /dev/null <<EOF
server {
    listen 80;
    server_name $SERVER_IP _;

    # 前端静态文件
    location / {
        root $APP_DIR/app/frontend/dist;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        client_max_body_size 50M;
    }

    # 骰子纹理
    location /textures/ {
        root $APP_DIR/app/frontend/dist;
    }

    # 骰子音效
    location /sounds/ {
        root $APP_DIR/app/frontend/dist;
    }
}
EOF

# 删除默认配置（如有）
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null
sudo rm -f /etc/nginx/conf.d/default.conf 2>/dev/null

if sudo nginx -t 2>/dev/null; then
    sudo systemctl reload nginx
    echo "  Nginx: 配置有效 ✓"
else
    echo "  Nginx 配置有误！"
    sudo nginx -t
fi

# ── 防火墙 ──
if command -v firewall-cmd &> /dev/null; then
    sudo firewall-cmd --permanent --add-service=http 2>/dev/null || true
    sudo firewall-cmd --permanent --add-service=https 2>/dev/null || true
    sudo firewall-cmd --reload 2>/dev/null || true
elif command -v ufw &> /dev/null; then
    sudo ufw allow 80/tcp 2>/dev/null || true
    sudo ufw allow 443/tcp 2>/dev/null || true
fi

# ── 验证 ──
echo ""
echo "══════════════════════════════════════"
echo "  部署完成！"
echo "══════════════════════════════════════"
echo ""

# Health check
if curl -s http://127.0.0.1:8000/health | grep -q "ok"; then
    echo "  ✓ 后端健康检查: 通过"
else
    echo "  ✗ 后端健康检查: 失败"
    echo "    查看日志: journalctl -u ai-trpg -f"
fi

echo ""
echo "  访问地址:   http://$SERVER_IP"
echo "  健康检查:   http://$SERVER_IP/api/health"
echo "  后端日志:   journalctl -u ai-trpg -f"
echo ""
echo "  ── 下一步 ──"
echo "  1. 编辑 API Key:  nano $APP_DIR/app/backend/.env"
echo "  2. 重启后端:      systemctl restart ai-trpg"
echo "  3. 配置域名后:    certbot --nginx -d your-domain.com"
echo ""
echo "  ── 常用命令 ──"
echo "  查看状态:  systemctl status ai-trpg"
echo "  查看日志:  journalctl -u ai-trpg -f"
echo "  重启后端:  systemctl restart ai-trpg"
echo "  重启前端:  cd $APP_DIR/app/frontend && npm run build"
echo ""
