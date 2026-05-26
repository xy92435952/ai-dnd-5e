import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { getCombatMock, getSessionMock } = vi.hoisted(() => ({
  getCombatMock: vi.fn(),
  getSessionMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    getCombat: getCombatMock,
    getSession: getSessionMock,
  },
}))

import { useCombatLoader } from '../useCombatLoader'

describe('useCombatLoader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  function renderLoader(overrides = {}) {
    const aiTimer = { current: null }
    const deps = {
      sessionId: 'sess-1',
      initiativeShown: false,
      aiTimer,
      setCombat: vi.fn(),
      setSession: vi.fn(),
      setPlayerId: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      setPlayerKnownSpells: vi.fn(),
      setPlayerCantrips: vi.fn(),
      setPlayerClass: vi.fn(),
      setPlayerLevel: vi.fn(),
      setClassResources: vi.fn(),
      setPlayerSubclass: vi.fn(),
      setPlayerSubclassEffects: vi.fn(),
      setTurnState: vi.fn(),
      setLogs: vi.fn(),
      setInitiativeShown: vi.fn(),
      setError: vi.fn(),
      showDice: vi.fn(),
      triggerAiTurn: vi.fn(),
      isPlayerTurn: vi.fn(c => c?.turn_order?.[c.current_turn_index]?.is_player === true),
      ...overrides,
    }
    return { deps, aiTimer, ...renderHook(() => useCombatLoader(deps)) }
  }

  it('loads combat/session data and shows the settled first-round initiative result', async () => {
    getCombatMock.mockResolvedValue({
      round_number: 1,
      current_turn_index: 0,
      turn_order: [{ character_id: 'char-1', is_player: true, initiative: 14, d20: 12 }],
      turn_states: { 'char-1': { action_used: false } },
    })
    getSessionMock.mockResolvedValue({
      player: {
        id: 'char-1',
        char_class: 'Wizard',
        level: 3,
      },
      logs: [],
    })

    const { result, deps } = renderLoader()

    await act(async () => {
      await result.current.loadCombat()
    })

    expect(getCombatMock).toHaveBeenCalledWith('sess-1')
    expect(getSessionMock).toHaveBeenCalledWith('sess-1')
    expect(deps.setPlayerId).toHaveBeenCalledWith('char-1')
    expect(deps.setInitiativeShown).toHaveBeenCalledWith(true)
    expect(deps.showDice).toHaveBeenCalledWith({ faces: 20, result: 12, label: '先攻检定' })
  })

  it('shows the controlled player initiative when reloading a multiplayer combat', async () => {
    getCombatMock.mockResolvedValue({
      round_number: 1,
      current_turn_index: 0,
      turn_order: [
        { character_id: 'host-char', is_player: true, initiative: 18, d20: 17 },
        { character_id: 'guest-char', is_player: true, initiative: 12, d20: 11 },
      ],
      turn_states: {
        'guest-char': { action_used: false },
      },
    })
    getSessionMock.mockResolvedValue({
      player: {
        id: 'guest-char',
        char_class: 'Wizard',
        level: 3,
      },
      logs: [],
    })

    const { result, deps } = renderLoader()

    await act(async () => {
      await result.current.loadCombat()
    })

    expect(deps.setPlayerId).toHaveBeenCalledWith('guest-char')
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: false })
    expect(deps.setInitiativeShown).toHaveBeenCalledWith(true)
    expect(deps.showDice).toHaveBeenCalledWith({ faces: 20, result: 11, label: '先攻检定' })
    expect(deps.showDice).not.toHaveBeenCalledWith({ faces: 20, result: 17, label: '先攻检定' })
  })

  it('schedules ai turns when fresh combat is not on a player turn', async () => {
    getCombatMock.mockResolvedValue({
      round_number: 2,
      current_turn_index: 0,
      turn_order: [{ character_id: 'enemy-1', is_player: false }],
    })
    getSessionMock.mockResolvedValue({ player: { id: 'char-1' }, logs: [] })

    const { result, deps, aiTimer } = renderLoader()

    await act(async () => {
      await result.current.loadCombat()
    })

    expect(aiTimer.current).not.toBeNull()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(deps.triggerAiTurn).toHaveBeenCalled()
  })

  it('replaces a pending ai timer when combat reloads on the same ai turn', async () => {
    getCombatMock.mockResolvedValue({
      round_number: 2,
      current_turn_index: 0,
      turn_order: [{ character_id: 'enemy-1', is_player: false }],
    })
    getSessionMock.mockResolvedValue({ player: { id: 'char-1' }, logs: [] })

    const { result, deps, aiTimer } = renderLoader()

    await act(async () => {
      await result.current.loadCombat()
    })
    const firstTimer = aiTimer.current
    expect(firstTimer).not.toBeNull()

    await act(async () => {
      await result.current.loadCombat()
    })
    expect(aiTimer.current).not.toBeNull()
    expect(aiTimer.current).not.toBe(firstTimer)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(deps.triggerAiTurn).toHaveBeenCalledTimes(1)
  })

  it('clears a pending ai timer when reload restores a player turn', async () => {
    getCombatMock.mockResolvedValue({
      round_number: 2,
      current_turn_index: 0,
      turn_order: [{ character_id: 'enemy-1', is_player: false }],
    })
    getSessionMock.mockResolvedValue({ player: { id: 'char-1' }, logs: [] })

    const { result, deps, aiTimer } = renderLoader()

    await act(async () => {
      await result.current.loadCombat()
    })
    expect(aiTimer.current).not.toBeNull()

    getCombatMock.mockResolvedValue({
      round_number: 2,
      current_turn_index: 1,
      turn_order: [
        { character_id: 'enemy-1', is_player: false },
        { character_id: 'char-1', is_player: true },
      ],
      turn_states: { 'char-1': { action_used: false } },
    })

    await act(async () => {
      await result.current.loadCombat()
    })
    expect(aiTimer.current).toBeNull()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(deps.triggerAiTurn).not.toHaveBeenCalled()
  })

  it('does not schedule multiplayer ai turns on non-driver clients', async () => {
    getCombatMock.mockResolvedValue({
      round_number: 2,
      current_turn_index: 0,
      turn_order: [{ character_id: 'enemy-1', is_player: false }],
    })
    getSessionMock.mockResolvedValue({ player: { id: 'char-1' }, logs: [] })

    const { result, deps, aiTimer } = renderLoader({ canDriveAiTurns: false })

    await act(async () => {
      await result.current.loadCombat()
    })

    expect(aiTimer.current).toBeNull()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(deps.triggerAiTurn).not.toHaveBeenCalled()
  })
})
