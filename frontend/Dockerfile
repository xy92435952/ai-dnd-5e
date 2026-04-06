FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install --silent

COPY . .
RUN npm run build

# 复制骰子资源到 dist
RUN mkdir -p dist/assets && \
    cp -r node_modules/@3d-dice/dice-box/dist/assets/* dist/assets/ 2>/dev/null || true

# ── Nginx 生产镜像 ──
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
