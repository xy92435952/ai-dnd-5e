import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { combatActionMock, classFeatureMock, rollDice3DMock } = vi.hoisted(() => ({
  combatActionMock: vi.fn(),
  classFeatureMock: vi.fn(),
  rollDice3DMock: vi.fn(),
}))

vi.mock('../../api/game', () => ({
  gameApi: {
    combatAction: combatActionMock,
    classFeature: classFeatureMock,
  },
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  rollDice3D: rollDice3DMock,
}))

import { useCombatPlayerActions } from '../useCombatPlayerActions'

describe('useCombatPlayerActions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    combatActionMock.mockResolvedValue({
      narration: '你采取了闪避姿态',
      turn_state: { action_used: true },
    })
    classFeatureMock.mockResolvedValue({
      narration: '你恢复了体力',
      turn_state: { bonus_action_used: true },
      class_resources: { second_wind_used: true },
      hp_current: 9,
    })
    rollDice3DMock.mockResolvedValue({ total: 6, rolls: [6] })
  })

  function renderActions(overrides = {}) {
    const processingRef = { current: false }
    const deps = {
      sessionId: 'sess-1',
      playerId: 'char-1',
      combat: { round_number: 1 },
      isProcessing: false,
      isPlayerTurn: vi.fn(() => true),
      processingRef,
      setIsProcessing: vi.fn(),
      setError: vi.fn(),
      setTurnState: vi.fn(),
      setClassResources: vi.fn(),
      setCombat: vi.fn(),
      showDice: vi.fn(),
      addLog: vi.fn(),
      ...overrides,
    }
    return { deps, processingRef, ...renderHook(() => useCombatPlayerActions(deps)) }
  }

  it('runs dodge through the existing combat action endpoint', async () => {
    const { result, deps, processingRef } = renderActions()

    await act(async () => {
      await result.current.handleDodge()
    })

    expect(combatActionMock).toHaveBeenCalledWith('sess-1', '闪避', null, false)
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: true })
    expect(deps.addLog).toHaveBeenCalledWith({
      role: 'player',
      content: '你采取了闪避姿态',
      log_type: 'combat',
    })
    expect(processingRef.current).toBe(false)
    expect(deps.setIsProcessing).toHaveBeenLastCalledWith(false)
  })

  it('rolls feature dice before calling classFeature and applies player hp', async () => {
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleClassFeature('second_wind')
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(10, 1)
    expect(deps.showDice).toHaveBeenCalledWith({
      faces: 10,
      result: 6,
      label: '活力恢复',
      count: 1,
    })
    expect(classFeatureMock).toHaveBeenCalledWith('sess-1', 'second_wind')
    expect(deps.setClassResources).toHaveBeenCalledWith({ second_wind_used: true })

    const hpUpdater = deps.setCombat.mock.calls[0][0]
    expect(hpUpdater({
      entities: {
        'char-1': { id: 'char-1', hp_current: 4 },
      },
    }).entities['char-1'].hp_current).toBe(9)
  })
})
