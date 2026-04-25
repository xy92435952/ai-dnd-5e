/**
 * useAdventureSession 单元测试 — 加载 session、战斗激活时跳转、onLoaded 回调。
 *
 * mock：gameApi.getSession / react-router 的 useNavigate / Zustand store。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('../../api/client', () => ({
  gameApi: {
    getSession: vi.fn(),
  },
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}))

import { gameApi } from '../../api/client'
import { useAdventureSession } from '../useAdventureSession'


beforeEach(() => {
  vi.clearAllMocks()
})


describe('useAdventureSession', () => {
  it('mount 时自动加载，写入 session/player/companions', async () => {
    gameApi.getSession.mockResolvedValue({
      session_id: 's1',
      combat_active: false,
      player: { id: 'p1', name: '战士' },
      companions: [{ id: 'c1', name: '法师' }],
      logs: [],
    })

    const { result } = renderHook(() =>
      useAdventureSession({ sessionId: 's1' })
    )

    await waitFor(() => expect(result.current.session).not.toBeNull())
    expect(result.current.player).toEqual({ id: 'p1', name: '战士' })
    expect(result.current.companions).toHaveLength(1)
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('combat_active=true 时自动 navigate 到 /combat/{id}', async () => {
    gameApi.getSession.mockResolvedValue({
      session_id: 's2',
      combat_active: true,
      player: null,
      companions: [],
      logs: [],
    })

    renderHook(() => useAdventureSession({ sessionId: 's2' }))

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/combat/s2'))
  })

  it('调用 onLoaded 回调，传入 session 数据', async () => {
    const onLoaded = vi.fn()
    gameApi.getSession.mockResolvedValue({
      session_id: 's3',
      combat_active: false,
      player: null,
      companions: [],
      logs: [{ id: 'l1', role: 'dm', content: '...', log_type: 'narrative' }],
    })

    renderHook(() => useAdventureSession({ sessionId: 's3', onLoaded }))

    await waitFor(() => expect(onLoaded).toHaveBeenCalled())
    const data = onLoaded.mock.calls[0][0]
    expect(data.session_id).toBe('s3')
    expect(data.logs).toHaveLength(1)
  })

  it('combat_active=true 时不调 onLoaded（已经跳转走了）', async () => {
    const onLoaded = vi.fn()
    gameApi.getSession.mockResolvedValue({
      session_id: 's4',
      combat_active: true,
      player: null, companions: [], logs: [],
    })
    renderHook(() => useAdventureSession({ sessionId: 's4', onLoaded }))
    await waitFor(() => expect(mockNavigate).toHaveBeenCalled())
    expect(onLoaded).not.toHaveBeenCalled()
  })

  it('getSession 抛异常 → 调 onError 回调', async () => {
    const onError = vi.fn()
    gameApi.getSession.mockRejectedValue(new Error('boom'))

    renderHook(() => useAdventureSession({ sessionId: 's5', onError }))

    await waitFor(() => expect(onError).toHaveBeenCalled())
    expect(onError.mock.calls[0][0]).toBeInstanceOf(Error)
  })

  it('暴露的 loadSession 可以手动重新加载', async () => {
    gameApi.getSession.mockResolvedValue({
      session_id: 's6',
      combat_active: false,
      player: null, companions: [], logs: [],
    })

    const { result } = renderHook(() => useAdventureSession({ sessionId: 's6' }))
    await waitFor(() => expect(result.current.session).not.toBeNull())

    expect(gameApi.getSession).toHaveBeenCalledTimes(1)
    await result.current.loadSession()
    expect(gameApi.getSession).toHaveBeenCalledTimes(2)
  })
})
