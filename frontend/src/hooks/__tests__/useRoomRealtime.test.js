import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'

const { roomsGetMock } = vi.hoisted(() => ({
  roomsGetMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  roomsApi: {
    get: roomsGetMock,
  },
}))

import { mergeRealtimeRoomEvent, normalizeRealtimeRoom, useRoomRealtime } from '../useRoomRealtime'

describe('normalizeRealtimeRoom', () => {
  it('normalizes multiplayer current speaker for shared UI usage', () => {
    expect(normalizeRealtimeRoom({
      is_multiplayer: true,
      current_speaker_user_id: 'u2',
      dm_thinking: {
        active: true,
        by_user_id: 'u1',
        action_text: 'Open the door',
      },
    })).toMatchObject({
      is_multiplayer: true,
      _currentSpeaker: 'u2',
      _dmThinking: {
        active: true,
        by_user_id: 'u1',
        action_text: 'Open the door',
      },
    })
  })

  it('drops inactive DM thinking snapshots', () => {
    expect(normalizeRealtimeRoom({
      is_multiplayer: true,
      current_speaker_user_id: 'u2',
      dm_thinking: { active: false, by_user_id: 'u1' },
    })).toMatchObject({
      _dmThinking: null,
    })
  })

  it('returns null for single-player or missing room payloads', () => {
    expect(normalizeRealtimeRoom(null)).toBeNull()
    expect(normalizeRealtimeRoom({ is_multiplayer: false })).toBeNull()
  })
})

describe('mergeRealtimeRoomEvent', () => {
  it('replaces room state from room_state_updated payload and normalizes speaker', () => {
    const merged = mergeRealtimeRoomEvent(
      { is_multiplayer: true, room_code: '234567', _currentSpeaker: 'old' },
      {
        type: 'room_state_updated',
        room: {
          is_multiplayer: true,
          room_code: '765432',
          current_speaker_user_id: 'new',
          party_groups: [{ id: 'main', member_user_ids: ['u1'] }],
          group_readiness: { main: { u1: 'ready' } },
        },
      },
    )

    expect(merged).toMatchObject({
      room_code: '765432',
      _currentSpeaker: 'new',
      party_groups: [{ id: 'main', member_user_ids: ['u1'] }],
      group_readiness: { main: { u1: 'ready' } },
    })
  })

  it('merges member snapshots without losing current speaker', () => {
    const merged = mergeRealtimeRoomEvent(
      { is_multiplayer: true, room_code: '234567', _currentSpeaker: 'u1', members: [] },
      {
        type: 'member_online',
        user_id: 'u2',
        members: [{ user_id: 'u2', is_online: true }],
      },
    )

    expect(merged).toMatchObject({
      room_code: '234567',
      _currentSpeaker: 'u1',
      members: [{ user_id: 'u2', is_online: true }],
    })
  })
})

describe('useRoomRealtime', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads room, exposes my member and controlled character id', async () => {
    roomsGetMock.mockResolvedValue({
      is_multiplayer: true,
      current_speaker_user_id: 'u1',
      members: [
        { user_id: 'u1', character_id: 'c1' },
        { user_id: 'u2', character_id: 'c2' },
      ],
    })

    const { result } = renderHook(() => useRoomRealtime('sess-1', 'u2'))

    await waitFor(() => expect(result.current.room?.is_multiplayer).toBe(true))
    expect(result.current.room._currentSpeaker).toBe('u1')
    expect(result.current.myMember).toMatchObject({ user_id: 'u2', character_id: 'c2' })
    expect(result.current.myCharacterId).toBe('c2')
  })

  it('keeps room null and records error when room lookup fails', async () => {
    roomsGetMock.mockRejectedValue(new Error('not found'))

    const { result } = renderHook(() => useRoomRealtime('solo-1', 'u1'))

    await waitFor(() => expect(roomsGetMock).toHaveBeenCalledWith('solo-1'))
    expect(result.current.room).toBeNull()
    await waitFor(() => expect(result.current.error).toBe('not found'))
  })

  it('can preserve the previous room snapshot on transient refresh errors', async () => {
    roomsGetMock.mockResolvedValueOnce({
      is_multiplayer: true,
      current_speaker_user_id: 'u1',
      members: [{ user_id: 'u1', character_id: 'c1' }],
    })

    const { result } = renderHook(() => useRoomRealtime('sess-1', 'u1'))

    await waitFor(() => expect(result.current.room?._currentSpeaker).toBe('u1'))
    roomsGetMock.mockRejectedValueOnce(new Error('network blip'))
    await act(async () => {
      await result.current.refreshRoom({ preserveOnError: true })
    })

    expect(result.current.room?._currentSpeaker).toBe('u1')
    await waitFor(() => expect(result.current.error).toBe('network blip'))
  })
})
