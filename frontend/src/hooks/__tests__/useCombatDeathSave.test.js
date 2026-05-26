import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { deathSaveMock, rollDice3DMock } = vi.hoisted(() => ({
  deathSaveMock: vi.fn(),
  rollDice3DMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    deathSave: deathSaveMock,
  },
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  rollDice3D: rollDice3DMock,
}))

import { useCombatDeathSave } from '../useCombatDeathSave'

describe('useCombatDeathSave', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    rollDice3DMock.mockResolvedValue({ total: 20, rolls: [20] })
    deathSaveMock.mockResolvedValue({
      character_id: 'char-1',
      character_name: 'Tester',
      d20: 20,
      outcome: 'revive',
      hp_current: 1,
      death_saves: null,
      life_state: 'alive',
      target_state: {
        target_id: 'char-1',
        hp_current: 1,
        new_hp: 1,
        death_saves: null,
        conditions: [],
        life_state: 'alive',
      },
    })
  })

  function renderDeathSave(overrides = {}) {
    const processingRef = { current: false }
    const deps = {
      sessionId: 'sess-1',
      playerId: 'char-1',
      isProcessing: false,
      processingRef,
      setIsProcessing: vi.fn(),
      setError: vi.fn(),
      setCombat: vi.fn(),
      setSession: vi.fn(),
      showDice: vi.fn(),
      addLog: vi.fn(),
      ...overrides,
    }
    return { deps, processingRef, ...renderHook(() => useCombatDeathSave(deps)) }
  }

  it('rolls d20, calls death-save endpoint, and merges life state into combat/session', async () => {
    const { result, deps, processingRef } = renderDeathSave()

    await act(async () => {
      await result.current()
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(20)
    expect(deps.showDice).toHaveBeenCalledWith({ faces: 20, result: 20, label: '死亡豁免' })
    expect(deathSaveMock).toHaveBeenCalledWith('sess-1', 'char-1', 20)

    const combatUpdater = deps.setCombat.mock.calls[0][0]
    expect(combatUpdater({
      entities: {
        'char-1': {
          id: 'char-1',
          hp_current: 0,
          death_saves: { successes: 0, failures: 2, stable: false },
          conditions: ['unconscious'],
          life_state: 'dying',
        },
      },
    }).entities['char-1']).toMatchObject({
      hp_current: 1,
      death_saves: null,
      conditions: [],
      life_state: 'alive',
    })

    const sessionUpdater = deps.setSession.mock.calls[0][0]
    expect(sessionUpdater({
      player: {
        id: 'char-1',
        hp_current: 0,
        death_saves: { successes: 0, failures: 2, stable: false },
        conditions: ['unconscious'],
        life_state: 'dying',
      },
    }).player).toMatchObject({
      hp_current: 1,
      death_saves: null,
      conditions: [],
      life_state: 'alive',
    })
    expect(deps.addLog).toHaveBeenCalledWith({
      role: 'system',
      content: 'Tester 掷出自然 20，恢复 1 HP！',
      log_type: 'dice',
    })
    expect(processingRef.current).toBe(false)
    expect(deps.setIsProcessing).toHaveBeenLastCalledWith(false)
  })

  it('does nothing when the current user cannot act this turn', async () => {
    const { result, deps } = renderDeathSave({ canActThisTurn: false })

    await act(async () => {
      await result.current()
    })

    expect(rollDice3DMock).not.toHaveBeenCalled()
    expect(deathSaveMock).not.toHaveBeenCalled()
    expect(deps.setIsProcessing).not.toHaveBeenCalled()
  })
})
