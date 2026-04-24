/**
 * useUser — 统一读取 localStorage 中的登录用户信息
 *
 * 原先散落在 Home.jsx / Room.jsx / Adventure.jsx / Combat.jsx 的这段重复代码：
 *   const u = JSON.parse(localStorage.getItem('user') || 'null')
 *   const myUserId = u?.user_id || u?.id || null
 *
 * 统一收敛到这里；同时解决两个问题：
 *   1) 各处字段取法不一致（有的用 user_id，有的用 id；有的取 display_name，有的取 username）
 *   2) localStorage 读取散落，将来要接 OAuth / 单点登出时要改 N 处
 *
 * 约定：localStorage.setItem('user', JSON.stringify({ user_id, username, display_name }))
 * 仅该 hook 负责读取；写入仍在登录流程里按需 setItem。
 *
 * 返回值 user 在未登录时为 null；userId 在未登录时为 null。
 */
import { useSyncExternalStore } from 'react'

const STORAGE_KEY = 'user'

// 读取并规范化——无论存的是 user_id 还是 id，统一暴露为 user_id / id 两个键都可用。
function readUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    // 规范化 id 字段
    const uid = parsed.user_id || parsed.id || null
    return {
      ...parsed,
      user_id:  uid,
      id:       uid,
      display_name: parsed.display_name || parsed.displayName || parsed.username || '冒险者',
    }
  } catch {
    return null
  }
}

// 监听 localStorage 的 storage 事件（跨 tab 登录同步时用得到）
// 以及自定义 'user-changed' 事件（同 tab 登录 / 登出后手动派发）
function subscribe(callback) {
  const onStorage = (e) => {
    if (!e || e.key === STORAGE_KEY || e.key === null) callback()
  }
  const onCustom = () => callback()
  window.addEventListener('storage', onStorage)
  window.addEventListener('user-changed', onCustom)
  return () => {
    window.removeEventListener('storage', onStorage)
    window.removeEventListener('user-changed', onCustom)
  }
}

// snapshot 返回的值必须是稳定的（相同内容返回相同引用），否则会触发无限重渲染。
// 这里用 JSON 字符串做指纹，内容变了才生成新对象。
let _cachedSnapshot = null
let _cachedFingerprint = null

function getSnapshot() {
  const user = readUser()
  const fp = user ? JSON.stringify(user) : null
  if (fp !== _cachedFingerprint) {
    _cachedFingerprint = fp
    _cachedSnapshot = user
  }
  return _cachedSnapshot
}

/**
 * 读取当前登录用户。
 * @returns {{user: object|null, userId: string|null, displayName: string}}
 */
export function useUser() {
  const user = useSyncExternalStore(subscribe, getSnapshot, () => null)
  return {
    user,
    userId:      user?.user_id || null,
    displayName: user?.display_name || '冒险者',
  }
}

/**
 * 登录 / 登出后调用，通知同 tab 的所有 useUser 订阅者刷新。
 * 跨 tab 会由原生 storage 事件自动触发，不需要手动派发。
 */
export function setUser(userObj) {
  if (userObj) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(userObj))
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
  // 同 tab 通知
  window.dispatchEvent(new Event('user-changed'))
}
