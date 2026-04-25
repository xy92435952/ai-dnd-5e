// vitest 的 defineConfig 是 vite defineConfig 的超集，能识别 `test` 字段
import { defineConfig } from 'vitest/config'
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
