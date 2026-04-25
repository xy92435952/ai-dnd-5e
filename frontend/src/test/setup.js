/**
 * vitest 全局 setup —— 每个测试文件运行前执行一次。
 *
 * 1. 启用 @testing-library/jest-dom 自定义 matcher（toBeInTheDocument / toHaveTextContent / ...）
 * 2. 每个 test 后清理 localStorage / sessionStorage（避免 useUser 等 hook 跨测试污染）
 */
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'

afterEach(() => {
  try {
    localStorage.clear()
    sessionStorage.clear()
  } catch (_) {}
})
