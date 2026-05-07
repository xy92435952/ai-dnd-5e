/**
 * vitest 全局 setup —— 每个测试文件运行前执行一次。
 *
 * 1. 启用 @testing-library/jest-dom 自定义 matcher（toBeInTheDocument / toHaveTextContent / ...）
 * 2. 每个 test 后清理 localStorage / sessionStorage（避免 useUser 等 hook 跨测试污染）
 */
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'

function createMemoryStorage() {
  let store = new Map()
  return {
    get length() {
      return store.size
    },
    clear() {
      store.clear()
    },
    getItem(key) {
      key = String(key)
      return store.has(key) ? store.get(key) : null
    },
    key(index) {
      return Array.from(store.keys())[index] ?? null
    },
    removeItem(key) {
      store.delete(String(key))
    },
    setItem(key, value) {
      store.set(String(key), String(value))
    },
  }
}

function ensureStorage(name) {
  const current = globalThis[name]
  if (current && typeof current.setItem === 'function') return
  const storage = createMemoryStorage()
  Object.defineProperty(globalThis, name, {
    configurable: true,
    value: storage,
  })
  if (globalThis.window) {
    Object.defineProperty(globalThis.window, name, {
      configurable: true,
      value: storage,
    })
  }
}

ensureStorage('localStorage')
ensureStorage('sessionStorage')

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

afterEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})
