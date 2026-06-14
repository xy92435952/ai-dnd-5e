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
      dice_result: { type: 'death_save', d20: 20, outcome: 'revive' },
      state_changes: ['Tester HP 1'],
    })
    expect(processingRef.current).toBe(false)
    expect(deps.setIsProcessing).toHaveBeenLastCalledWith(false)
  })

  it('spends Bardic Inspiration on a death save when enabled', async () => {
    const setClassResources = vi.fn()
    const setUseBardicDeathSave = vi.fn()
    rollDice3DMock
      .mockResolvedValueOnce({ total: 6, rolls: [6] })
      .mockResolvedValueOnce({ total: 4, rolls: [4] })
    deathSaveMock.mockResolvedValueOnce({
      character_id: 'char-1',
      character_name: 'Tester',
      d20: 6,
      total: 10,
      save_succeeded: true,
      outcome: 'success',
      hp_current: 0,
      death_saves: { successes: 1, failures: 0, stable: false },
      class_resources: { bardic_inspiration: { die: 'd8', uses_remaining: 0 } },
      bardic_inspiration: {
        spent: true,
        die: 'd8',
        roll: 4,
        uses_remaining: 0,
      },
      life_state: 'dying',
      target_state: {
        target_id: 'char-1',
        hp_current: 0,
        death_saves: { successes: 1, failures: 0, stable: false },
        conditions: ['unconscious'],
        class_resources: { bardic_inspiration: { die: 'd8', uses_remaining: 0 } },
        life_state: 'dying',
      },
    })
    const { result, deps } = renderDeathSave({
      classResources: { bardic_inspiration: { die: 'd8', uses_remaining: 1 } },
      useBardicDeathSave: true,
      setUseBardicDeathSave,
      setClassResources,
    })

    await act(async () => {
      await result.current()
    })

    expect(rollDice3DMock).toHaveBeenNthCalledWith(1, 20)
    expect(rollDice3DMock).toHaveBeenNthCalledWith(2, 8)
    expect(deps.showDice).toHaveBeenCalledWith({
      faces: 8,
      result: 4,
      label: 'Bardic Inspiration d8',
      count: 1,
    })
    expect(deathSaveMock).toHaveBeenCalledWith(
      'sess-1',
      'char-1',
      6,
      { useBardicInspiration: true, bardicInspirationRoll: 4 },
    )
    expect(setUseBardicDeathSave).toHaveBeenCalledWith(false)
    expect(setClassResources).toHaveBeenCalledWith(expect.any(Function))
    expect(setClassResources.mock.calls[0][0]({ bardic_inspiration: { die: 'd8', uses_remaining: 1 } })).toEqual({
      bardic_inspiration: { die: 'd8', uses_remaining: 0 },
    })

    const sessionUpdater = deps.setSession.mock.calls[0][0]
    expect(sessionUpdater({
      player: {
        id: 'char-1',
        hp_current: 0,
        death_saves: { successes: 0, failures: 0, stable: false },
        class_resources: { bardic_inspiration: { die: 'd8', uses_remaining: 1 } },
      },
    }).player.class_resources.bardic_inspiration.uses_remaining).toBe(0)
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      dice_result: expect.objectContaining({
        type: 'death_save',
        d20: 6,
        total: 10,
        bardic_inspiration: expect.objectContaining({ spent: true, roll: 4 }),
      }),
    }))
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
