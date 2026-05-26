import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { roomsGetMock } = vi.hoisted(() => ({
  roomsGetMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    move: vi.fn(),
  },
  roomsApi: {
    get: roomsGetMock,
  },
}))

import { useCombatPageActions } from '../useCombatPageActions'

describe('useCombatPageActions websocket sync', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function renderActions(overrides = {}) {
    const deps = {
      sessionId: 'sess-1',
      setRoom: vi.fn(),
      myCharacterId: 'guest-char',
      playerId: 'guest-char',
      moveMode: false,
      isProcessing: false,
      canActThisTurn: true,
      selectedTarget: 'enemy-1',
      entityPositions: {},
      playerPos: null,
      setError: vi.fn(),
      setCombat: vi.fn(),
      setTurnState: vi.fn(),
      setSpellModalOpen: vi.fn(),
      setHelpMode: vi.fn(),
      handleAttack: vi.fn(),
      handleDash: vi.fn(),
      handleDisengage: vi.fn(),
      handleDodge: vi.fn(),
      handleClassFeature: vi.fn(),
      setMoveMode: vi.fn(),
      setAoePreview: vi.fn(),
      setAoeHover: vi.fn(),
      clearAoePreview: vi.fn(),
      onLoadCombat: vi.fn(),
      setCombatOver: vi.fn(),
      ...overrides,
    }
    return { deps, ...renderHook(() => useCombatPageActions(deps)) }
  }

  it('applies combat_update payloads and reloads the fresh combat snapshot', () => {
    const combat = {
      current_turn_index: 1,
      turn_order: [
        { character_id: 'host-char', is_player: true },
        { character_id: 'guest-char', is_player: true },
      ],
      turn_states: {
        'guest-char': { action_used: false, movement_used: 2 },
      },
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        combat,
        combat_over: true,
        outcome: { result: 'victory' },
      })
    })

    expect(deps.setCombat).toHaveBeenCalledWith(combat)
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: false, movement_used: 2 })
    expect(deps.setCombatOver).toHaveBeenCalledWith({ result: 'victory' })
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('reloads combat for turn, movement, and dm response realtime events', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({ type: 'turn_changed' })
      result.current.onWsEvent({ type: 'entity_moved' })
      result.current.onWsEvent({ type: 'dm_responded' })
    })

    expect(deps.onLoadCombat).toHaveBeenCalledTimes(3)
  })

  it('merges room_state_updated and online member snapshots without a room refetch', () => {
    const { result, deps } = renderActions()
    const prevRoom = {
      is_multiplayer: true,
      current_speaker_user_id: 'host',
      members: [{ user_id: 'host', character_id: 'host-char', is_online: true }],
    }
    const updatedRoom = {
      is_multiplayer: true,
      current_speaker_user_id: 'guest',
      members: [{ user_id: 'guest', character_id: 'guest-char', is_online: true }],
    }
    const onlineMembers = [
      { user_id: 'host', character_id: 'host-char', is_online: true },
      { user_id: 'guest', character_id: 'guest-char', is_online: true },
    ]

    act(() => {
      result.current.onWsEvent({ type: 'room_state_updated', room: updatedRoom })
    })
    expect(deps.setRoom).toHaveBeenCalledTimes(1)
    expect(deps.setRoom.mock.calls[0][0](prevRoom)).toMatchObject({
      current_speaker_user_id: 'guest',
      _currentSpeaker: 'guest',
      members: updatedRoom.members,
    })

    act(() => {
      result.current.onWsEvent({ type: 'member_online', members: onlineMembers })
    })
    expect(deps.setRoom).toHaveBeenCalledTimes(2)
    expect(deps.setRoom.mock.calls[1][0](prevRoom).members).toEqual(onlineMembers)
    expect(roomsGetMock).not.toHaveBeenCalled()
  })

  it('refetches the room when online events do not include members', async () => {
    roomsGetMock.mockResolvedValue({
      is_multiplayer: true,
      members: [{ user_id: 'guest', is_online: true }],
    })
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({ type: 'member_offline', user_id: 'guest' })
    })

    await waitFor(() => {
      expect(roomsGetMock).toHaveBeenCalledWith('sess-1')
      expect(deps.setRoom).toHaveBeenCalledWith({
        is_multiplayer: true,
        members: [{ user_id: 'guest', is_online: true }],
      })
    })
  })
})
