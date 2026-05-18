import { describe, expect, it, vi, afterEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'

const { predictMock } = vi.hoisted(() => ({
  predictMock: vi.fn(),
}))

vi.mock('../../api/game', () => ({
  gameApi: {
    predict: predictMock,
  },
}))

import { useCombatPrediction } from '../useCombatPrediction'

describe('useCombatPrediction', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('debounces prediction requests and derives the action key from player class', async () => {
    vi.useFakeTimers()
    predictMock.mockResolvedValue({ hit_chance: 75 })

    const { result } = renderHook(() => useCombatPrediction({
      sessionId: 'sess-1',
      playerId: 'char-1',
      selectedTarget: 'enemy-1',
      playerClass: 'Wizard',
      isRanged: true,
    }))

    expect(result.current).toBe(null)
    expect(predictMock).not.toHaveBeenCalled()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(150)
    })

    expect(predictMock).toHaveBeenCalledWith('sess-1', 'char-1', 'enemy-1', 'firebolt', true)
    expect(result.current).toEqual({ hit_chance: 75 })
  })

  it('returns null and skips the request until target/session/player are ready', () => {
    const { result } = renderHook(() => useCombatPrediction({
      sessionId: 'sess-1',
      playerId: 'char-1',
      selectedTarget: null,
      playerClass: 'Fighter',
      isRanged: false,
    }))

    expect(result.current).toBe(null)
    expect(predictMock).not.toHaveBeenCalled()
  })
})
