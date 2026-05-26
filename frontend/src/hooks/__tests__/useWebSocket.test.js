import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useWebSocket } from '../useWebSocket'

const sockets = []

class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSED = 3

  constructor(url) {
    this.url = url
    this.readyState = MockWebSocket.CONNECTING
    this.send = vi.fn()
    this.close = vi.fn(() => {
      this.readyState = MockWebSocket.CLOSED
    })
    sockets.push(this)
  }
}

describe('useWebSocket reconnect behavior', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', MockWebSocket)
    localStorage.setItem('token', 'test token')
    sockets.length = 0
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    localStorage.clear()
    sockets.length = 0
  })

  it('reconnects after non-auth disconnects', () => {
    const { result } = renderHook(() => useWebSocket('session-1', vi.fn()))

    expect(result.current.connected).toBe(false)
    expect(result.current.send).toEqual(expect.any(Function))
    expect(sockets).toHaveLength(1)
    expect(sockets[0].url).toContain('/api/ws/sessions/session-1?token=test%20token')

    act(() => {
      sockets[0].onclose({ code: 1006 })
    })
    expect(sockets).toHaveLength(1)

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(sockets).toHaveLength(2)
  })

  it('does not reconnect after auth or permission closes', () => {
    renderHook(() => useWebSocket('session-1', vi.fn()))

    act(() => {
      sockets[0].onclose({ code: 4401 })
      vi.advanceTimersByTime(30000)
    })

    expect(sockets).toHaveLength(1)
  })
})
