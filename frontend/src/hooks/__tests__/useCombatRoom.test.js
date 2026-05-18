import { describe, expect, it, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

const { roomsGetMock } = vi.hoisted(() => ({
  roomsGetMock: vi.fn(),
}))

vi.mock('../../api/rooms', () => ({
  roomsApi: {
    get: roomsGetMock,
  },
}))

import { useCombatRoom } from '../useCombatRoom'

describe('useCombatRoom', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads multiplayer room and resolves the controlled character id', async () => {
    roomsGetMock.mockResolvedValue({
      is_multiplayer: true,
      members: [
        { user_id: 'other', character_id: 'char-2' },
        { user_id: 'me', character_id: 'char-1' },
      ],
    })

    const { result } = renderHook(() => useCombatRoom('sess-1', 'me'))

    await waitFor(() => expect(result.current.room?.is_multiplayer).toBe(true))
    expect(result.current.myCharacterId).toBe('char-1')
    expect(roomsGetMock).toHaveBeenCalledWith('sess-1')
  })

  it('keeps null room for single-player sessions when room lookup fails', async () => {
    roomsGetMock.mockRejectedValue(new Error('not found'))

    const { result } = renderHook(() => useCombatRoom('sess-1', 'me'))

    await waitFor(() => expect(roomsGetMock).toHaveBeenCalledWith('sess-1'))
    expect(result.current.room).toBe(null)
    expect(result.current.myCharacterId).toBe(null)
  })
})
