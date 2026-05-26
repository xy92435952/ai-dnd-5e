import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('../../juice', () => ({
  JuiceAudio: {
    turn: vi.fn(),
  },
}))

import { useAdventureMultiplayer } from '../useAdventureMultiplayer'

function renderMultiplayer(room, myUserId = 'me', overrides = {}) {
  return renderHook((props) => useAdventureMultiplayer({
    room: props.room,
    myUserId,
    wsConnected: props.wsConnected,
    session: props.session,
    loadSession: props.loadSession,
    refreshRoom: props.refreshRoom,
    onReconnectSynced: props.onReconnectSynced,
  }), {
    initialProps: {
      room,
      wsConnected: false,
      session: null,
      loadSession: vi.fn(),
      refreshRoom: vi.fn(),
      ...overrides,
    },
  })
}

describe('useAdventureMultiplayer', () => {
  it('allows solo sessions without room state to act', () => {
    const { result } = renderMultiplayer(null)

    expect(result.current.isMySpeakTurn).toBe(true)
  })

  it('does not treat missing multiplayer speaker as my turn', () => {
    const { result } = renderMultiplayer({
      is_multiplayer: true,
      _currentSpeaker: null,
      members: [{ user_id: 'me', display_name: 'Me' }],
    })

    expect(result.current.currentSpeakerUid).toBeNull()
    expect(result.current.isMySpeakTurn).toBe(false)
  })

  it('allows only the current multiplayer speaker to act', () => {
    const room = {
      is_multiplayer: true,
      _currentSpeaker: 'other',
      members: [
        { user_id: 'me', display_name: 'Me' },
        { user_id: 'other', display_name: 'Other' },
      ],
    }

    expect(renderMultiplayer(room, 'me').result.current.isMySpeakTurn).toBe(false)
    expect(renderMultiplayer(room, 'other').result.current.isMySpeakTurn).toBe(true)
  })

  it('refreshes both session and room snapshot after reconnect', async () => {
    const loadSession = vi.fn().mockResolvedValue()
    const refreshRoom = vi.fn().mockResolvedValue()
    const onReconnectSynced = vi.fn()
    const room = {
      is_multiplayer: true,
      _currentSpeaker: 'me',
      members: [{ user_id: 'me', display_name: 'Me' }],
    }
    const { rerender } = renderMultiplayer(room, 'me', {
      session: { id: 'sess-1' },
      loadSession,
      refreshRoom,
      onReconnectSynced,
    })

    rerender({
      room,
      wsConnected: true,
      session: { id: 'sess-1' },
      loadSession,
      refreshRoom,
      onReconnectSynced,
    })

    await waitFor(() => expect(loadSession).toHaveBeenCalledTimes(1))
    expect(refreshRoom).toHaveBeenCalledTimes(1)
    expect(refreshRoom).toHaveBeenCalledWith({ preserveOnError: true })
    expect(onReconnectSynced).not.toHaveBeenCalled()
  })

  it('notifies after a real disconnect has been resynced', async () => {
    const loadSession = vi.fn().mockResolvedValue()
    const refreshRoom = vi.fn().mockResolvedValue()
    const onReconnectSynced = vi.fn()
    const room = {
      is_multiplayer: true,
      _currentSpeaker: 'me',
      members: [{ user_id: 'me', display_name: 'Me' }],
    }
    const { rerender } = renderMultiplayer(room, 'me', {
      wsConnected: true,
      session: { id: 'sess-1' },
      loadSession,
      refreshRoom,
      onReconnectSynced,
    })

    rerender({
      room,
      wsConnected: false,
      session: { id: 'sess-1' },
      loadSession,
      refreshRoom,
      onReconnectSynced,
    })

    rerender({
      room,
      wsConnected: true,
      session: { id: 'sess-1' },
      loadSession,
      refreshRoom,
      onReconnectSynced,
    })

    await waitFor(() => expect(onReconnectSynced).toHaveBeenCalledTimes(1))
  })
})
