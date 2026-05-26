import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useCombatReconnectRefresh } from '../useCombatReconnectRefresh'

function renderReconnect(overrides = {}) {
  const props = {
    room: { is_multiplayer: true, session_id: 'sess-1' },
    combat: { session_id: 'sess-1', round_number: 1 },
    wsConnected: false,
    loadCombat: vi.fn().mockResolvedValue(),
    refreshRoom: vi.fn().mockResolvedValue(),
    ...overrides,
  }
  const hook = renderHook(
    nextProps => useCombatReconnectRefresh(nextProps),
    { initialProps: props },
  )
  return { props, ...hook }
}

describe('useCombatReconnectRefresh', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('reloads combat and room snapshots after websocket reconnects', async () => {
    const { props, rerender } = renderReconnect()

    rerender({ ...props, wsConnected: true })

    await waitFor(() => {
      expect(props.loadCombat).toHaveBeenCalledTimes(1)
      expect(props.refreshRoom).toHaveBeenCalledWith({ preserveOnError: true })
    })
  })

  it('waits until combat is loaded before filling a reconnect gap', async () => {
    const { props, rerender } = renderReconnect({ combat: null })

    rerender({ ...props, combat: null, wsConnected: true })
    expect(props.loadCombat).not.toHaveBeenCalled()
    expect(props.refreshRoom).not.toHaveBeenCalled()
  })
})
