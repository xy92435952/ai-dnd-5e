/**
 * useUser 单元测试 — 验证 localStorage 解析、setUser 派事件、跨订阅同步。
 */
import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useUser, setUser } from '../useUser'


describe('useUser', () => {
  it('未登录时返回 userId=null + 默认 displayName', () => {
    const { result } = renderHook(() => useUser())
    expect(result.current.user).toBeNull()
    expect(result.current.userId).toBeNull()
    expect(result.current.displayName).toBe('冒险者')
  })

  it('从 localStorage 解析 user_id', () => {
    localStorage.setItem('user', JSON.stringify({ user_id: 'u1', display_name: 'Alice' }))
    const { result } = renderHook(() => useUser())
    expect(result.current.userId).toBe('u1')
    expect(result.current.displayName).toBe('Alice')
  })

  it('兼容 id 字段（旧版 schema）', () => {
    localStorage.setItem('user', JSON.stringify({ id: 'u2', username: 'bob' }))
    const { result } = renderHook(() => useUser())
    expect(result.current.userId).toBe('u2')
    expect(result.current.displayName).toBe('bob')
  })

  it('setUser 派 user-changed 事件，订阅者刷新', () => {
    const { result } = renderHook(() => useUser())
    expect(result.current.userId).toBeNull()

    act(() => {
      setUser({ user_id: 'u3', display_name: 'Carol' })
    })

    expect(result.current.userId).toBe('u3')
    expect(result.current.displayName).toBe('Carol')
  })

  it('setUser(null) 清登录状态', () => {
    setUser({ user_id: 'u4', display_name: 'Dan' })
    const { result } = renderHook(() => useUser())
    expect(result.current.userId).toBe('u4')

    act(() => {
      setUser(null)
    })
    expect(result.current.user).toBeNull()
    expect(result.current.userId).toBeNull()
  })

  it('localStorage 损坏的 JSON 不会让 hook 抛异常', () => {
    localStorage.setItem('user', 'not-valid-json')
    const { result } = renderHook(() => useUser())
    expect(result.current.user).toBeNull()
  })
})
