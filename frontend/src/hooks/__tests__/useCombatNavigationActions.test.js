import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

vi.mock('../../api/game', () => ({
  gameApi: {
    endCombat: vi.fn(),
  },
}))

import { gameApi } from '../../api/game'
import { useCombatNavigationActions } from '../useCombatNavigationActions'

beforeEach(() => {
  vi.clearAllMocks()
  globalThis.confirm = vi.fn()
})

describe('useCombatNavigationActions', () => {
  it('returns to the adventure route without ending combat', () => {
    const navigate = vi.fn()
    const { result } = renderHook(() => useCombatNavigationActions({ sessionId: 's1', navigate }))

    act(() => result.current.returnToAdventure())

    expect(navigate).toHaveBeenCalledWith('/adventure/s1')
    expect(gameApi.endCombat).not.toHaveBeenCalled()
  })

  it('ends combat before returning from the stage', async () => {
    const navigate = vi.fn()
    gameApi.endCombat.mockResolvedValue({})
    const { result } = renderHook(() => useCombatNavigationActions({ sessionId: 's1', navigate }))

    await act(async () => result.current.endCombatAndReturn())

    expect(gameApi.endCombat).toHaveBeenCalledWith('s1')
    expect(navigate).toHaveBeenCalledWith('/adventure/s1')
  })

  it('requires confirmation for force ending combat', async () => {
    const navigate = vi.fn()
    globalThis.confirm.mockReturnValue(true)
    gameApi.endCombat.mockResolvedValue({})
    const { result } = renderHook(() => useCombatNavigationActions({ sessionId: 's1', navigate }))

    await act(async () => result.current.forceEndCombat())

    expect(globalThis.confirm).toHaveBeenCalledWith('强制结束战斗？')
    expect(gameApi.endCombat).toHaveBeenCalledWith('s1')
    expect(navigate).toHaveBeenCalledWith('/adventure/s1')
  })

  it('does not end combat when force confirmation is rejected', async () => {
    const navigate = vi.fn()
    globalThis.confirm.mockReturnValue(false)
    const { result } = renderHook(() => useCombatNavigationActions({ sessionId: 's1', navigate }))

    await act(async () => result.current.forceEndCombat())

    expect(gameApi.endCombat).not.toHaveBeenCalled()
    expect(navigate).not.toHaveBeenCalled()
  })
})
