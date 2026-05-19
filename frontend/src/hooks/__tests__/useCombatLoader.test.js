import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { getCombatMock, getSessionMock, rollDice3DMock } = vi.hoisted(() => ({
  getCombatMock: vi.fn(),
  getSessionMock: vi.fn(),
  rollDice3DMock: vi.fn(),
}))

vi.mock('../../api/game', () => ({
  gameApi: {
    getCombat: getCombatMock,
    getSession: getSessionMock,
  },
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  rollDice3D: rollDice3DMock,
}))

import { useCombatLoader } from '../useCombatLoader'

describe('useCombatLoader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    rollDice3DMock.mockResolvedValue({ total: 15, rolls: [15] })
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

  it('loads combat/session data and shows server initiative without blocking on a local roll', async () => {
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
    expect(rollDice3DMock).not.toHaveBeenCalled()
    expect(deps.showDice).toHaveBeenCalledWith({ faces: 20, result: 12, label: '先攻检定' })
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
})
