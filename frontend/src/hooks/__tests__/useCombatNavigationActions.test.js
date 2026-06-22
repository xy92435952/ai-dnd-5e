import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

vi.mock('../../api/client', () => ({
  gameApi: {
    endCombat: vi.fn(),
  },
}))

import { gameApi } from '../../api/client'
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

  it('opens an in-app confirmation before force ending combat', () => {
    const navigate = vi.fn()
    const { result } = renderHook(() => useCombatNavigationActions({ sessionId: 's1', navigate }))

    act(() => result.current.forceEndCombat())

    expect(result.current.forceEndConfirmOpen).toBe(true)
    expect(globalThis.confirm).not.toHaveBeenCalled()
    expect(gameApi.endCombat).not.toHaveBeenCalled()
    expect(navigate).not.toHaveBeenCalled()
  })

  it('confirms force ending combat from the in-app confirmation', async () => {
    const navigate = vi.fn()
    gameApi.endCombat.mockResolvedValue({})
    const { result } = renderHook(() => useCombatNavigationActions({ sessionId: 's1', navigate }))

    act(() => result.current.forceEndCombat())
    await act(async () => result.current.confirmForceEndCombat())

    expect(result.current.forceEndConfirmOpen).toBe(false)
    expect(globalThis.confirm).not.toHaveBeenCalled()
    expect(gameApi.endCombat).toHaveBeenCalledWith('s1')
    expect(navigate).toHaveBeenCalledWith('/adventure/s1')
  })

  it('does not end combat when the in-app force confirmation is canceled', () => {
    const navigate = vi.fn()
    const { result } = renderHook(() => useCombatNavigationActions({ sessionId: 's1', navigate }))

    act(() => result.current.forceEndCombat())
    act(() => result.current.cancelForceEndCombat())

    expect(result.current.forceEndConfirmOpen).toBe(false)
    expect(globalThis.confirm).not.toHaveBeenCalled()
    expect(gameApi.endCombat).not.toHaveBeenCalled()
    expect(navigate).not.toHaveBeenCalled()
  })
})
