import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { endTurnMock, getCombatMock } = vi.hoisted(() => ({
  endTurnMock: vi.fn(),
  getCombatMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    endTurn: endTurnMock,
    getCombat: getCombatMock,
  },
}))

import { useCombatTurnControls } from '../useCombatTurnControls'

describe('useCombatTurnControls', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  function renderControls(overrides = {}) {
    const processingRef = { current: false }
    const aiTimer = { current: null }
    const deps = {
      sessionId: 'sess-1',
      combat: { current_turn_index: 0, turn_order: [{ is_player: true, character_id: 'char-1' }] },
      isProcessing: false,
      isPlayerTurn: vi.fn(() => true),
      processingRef,
      aiTimer,
      setIsProcessing: vi.fn(),
      setMoveMode: vi.fn(),
      setHelpMode: vi.fn(),
      setError: vi.fn(),
      setCombat: vi.fn(),
      setTurnState: vi.fn(),
      setCombatOver: vi.fn(),
      addLog: vi.fn(),
      triggerAiTurn: vi.fn(),
      ...overrides,
    }
    return { deps, processingRef, aiTimer, ...renderHook(() => useCombatTurnControls(deps)) }
  }

  it('ends the turn, loads fresh combat, and schedules ai when the next turn is not a player', async () => {
    endTurnMock.mockResolvedValue({
      next_turn_index: 1,
      round_number: 2,
      expired_conditions: ['迟缓结束'],
    })
    getCombatMock.mockResolvedValue({
      current_turn_index: 1,
      turn_order: [
        { character_id: 'char-1', is_player: true },
        { character_id: 'enemy-1', is_player: false },
      ],
    })

    const { result, deps, aiTimer } = renderControls()

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(endTurnMock).toHaveBeenCalledWith('sess-1', '1:0:char-1')
    expect(deps.addLog).toHaveBeenCalledWith({
      role: 'system',
      content: '迟缓结束',
      log_type: 'system',
    })
    expect(deps.setMoveMode).toHaveBeenCalledWith(false)
    expect(deps.setHelpMode).toHaveBeenCalledWith(false)
    expect(getCombatMock).toHaveBeenCalledWith('sess-1')
    expect(aiTimer.current).not.toBeNull()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(600)
    })
    expect(deps.triggerAiTurn).toHaveBeenCalled()
  })

  it('sets player turn state when the fresh next turn is a player', async () => {
    endTurnMock.mockResolvedValue({ next_turn_index: 0, round_number: 1 })
    getCombatMock.mockResolvedValue({
      current_turn_index: 0,
      turn_order: [{ character_id: 'char-1', is_player: true }],
      turn_states: {
        'char-1': { action_used: false },
      },
    })

    const { result, deps } = renderControls()

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: false })
  })

  it('does not end turn when a multiplayer observer is watching another player turn', async () => {
    const { result, deps } = renderControls({ canActThisTurn: false })

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(endTurnMock).not.toHaveBeenCalled()
    expect(deps.setIsProcessing).not.toHaveBeenCalled()
  })

  it('does not auto-drive ai after ending turn on non-driver clients', async () => {
    endTurnMock.mockResolvedValue({ next_turn_index: 1, round_number: 2 })
    getCombatMock.mockResolvedValue({
      current_turn_index: 1,
      turn_order: [
        { character_id: 'char-1', is_player: true },
        { character_id: 'enemy-1', is_player: false },
      ],
    })

    const { result, deps, aiTimer } = renderControls({ canDriveAiTurns: false })

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(endTurnMock).toHaveBeenCalledWith('sess-1', '1:0:char-1')
    expect(aiTimer.current).toBeNull()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(600)
    })
    expect(deps.triggerAiTurn).not.toHaveBeenCalled()
  })

  it('refreshes combat and stops quietly when ending turn with a stale token', async () => {
    const freshCombat = {
      current_turn_index: 1,
      turn_order: [
        { character_id: 'char-1', is_player: true },
        { character_id: 'enemy-1', is_player: false },
      ],
    }
    endTurnMock.mockRejectedValue(new Error('End turn token is stale; refresh combat state'))
    getCombatMock.mockResolvedValue(freshCombat)

    const { result, deps, processingRef } = renderControls()

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(endTurnMock).toHaveBeenCalledWith('sess-1', '1:0:char-1')
    expect(getCombatMock).toHaveBeenCalledWith('sess-1')
    expect(deps.setCombat).toHaveBeenCalledWith(freshCombat)
    expect(deps.setError).toHaveBeenCalledWith('')
    expect(deps.setError).not.toHaveBeenCalledWith(expect.stringContaining('stale'))
    expect(processingRef.current).toBe(false)
    expect(deps.setIsProcessing).toHaveBeenLastCalledWith(false)
  })
})
