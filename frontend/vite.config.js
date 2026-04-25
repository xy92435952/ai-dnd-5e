/// <reference types="vitest" />
// 用 vite 的 defineConfig（不是 vitest/config）—— 生产部署 npm install --omit=dev
// 不会装 vitest，硬 import 'vitest/config' 会让 vite build 失败。
// vite.defineConfig 是 identity function，会原样保留 `test` 字段供 vitest 启动时读取；
// 三斜线 reference 让 IDE / TS 仍能识别 test 字段类型（dev 装了 vitest 时生效）。
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8002',
        changeOrigin: true,
        ws: true,                // 多人联机 WebSocket 代理
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    globals: true,                          // describe/it/expect 全局可用
    environment: 'jsdom',                   // hooks 测试需要 DOM API
    setupFiles: ['./src/test/setup.js'],
    css: false,                             // 测试不需要解析 css，加快速度
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}'],
  },
})
