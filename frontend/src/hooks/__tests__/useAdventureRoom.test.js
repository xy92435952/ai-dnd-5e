import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('../../api/rooms', () => ({
  roomsApi: {
    get: vi.fn(),
  },
}))

import { roomsApi } from '../../api/rooms'
import { normalizeAdventureRoom, useAdventureRoom } from '../useAdventureRoom'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('normalizeAdventureRoom', () => {
  it('returns null for non-multiplayer rooms', () => {
    expect(normalizeAdventureRoom(null)).toBeNull()
    expect(normalizeAdventureRoom({ is_multiplayer: false })).toBeNull()
  })

  it('copies current speaker to local UI field', () => {
    expect(normalizeAdventureRoom({
      id: 'r1',
      is_multiplayer: true,
      current_speaker_user_id: 'u2',
    })).toMatchObject({
      id: 'r1',
      _currentSpeaker: 'u2',
    })
  })
})

describe('useAdventureRoom', () => {
  it('loads multiplayer room and normalizes current speaker', async () => {
    roomsApi.get.mockResolvedValue({
      id: 'r1',
      is_multiplayer: true,
      current_speaker_user_id: 'u1',
    })

    const { result } = renderHook(() => useAdventureRoom('s1'))

    await waitFor(() => expect(result.current.room).not.toBeNull())
    expect(result.current.room._currentSpeaker).toBe('u1')
  })

  it('keeps room null when lookup fails', async () => {
    roomsApi.get.mockRejectedValue(new Error('single-player session'))

    const { result } = renderHook(() => useAdventureRoom('s2'))

    await waitFor(() => expect(roomsApi.get).toHaveBeenCalledWith('s2'))
    expect(result.current.room).toBeNull()
  })
})
