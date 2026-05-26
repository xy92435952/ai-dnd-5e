import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useRoomReconnectRefresh } from '../useRoomReconnectRefresh'

function renderReconnect(overrides = {}) {
  const props = {
    room: { is_multiplayer: true, session_id: 'sess-1' },
    wsConnected: false,
    refresh: vi.fn().mockResolvedValue(),
    ...overrides,
  }
  const hook = renderHook(
    nextProps => useRoomReconnectRefresh(nextProps),
    { initialProps: props },
  )
  return { props, ...hook }
}

describe('useRoomReconnectRefresh', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('refreshes room state after websocket reconnects', async () => {
    const { props, rerender } = renderReconnect()

    rerender({ ...props, wsConnected: true })

    await waitFor(() => {
      expect(props.refresh).toHaveBeenCalledTimes(1)
    })
  })

  it('does not refresh before the room snapshot is loaded', () => {
    const { props, rerender } = renderReconnect({ room: null })

    rerender({ ...props, room: null, wsConnected: true })

    expect(props.refresh).not.toHaveBeenCalled()
  })
})
