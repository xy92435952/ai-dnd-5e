import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { combatActionMock, classFeatureMock, rollDice3DMock, useItemMock } = vi.hoisted(() => ({
  combatActionMock: vi.fn(),
  classFeatureMock: vi.fn(),
  rollDice3DMock: vi.fn(),
  useItemMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  charactersApi: {
    useItem: useItemMock,
  },
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
      turn_state: { action_used: true, dodging: true },
    })
    classFeatureMock.mockResolvedValue({
      narration: '你恢复了体力',
      turn_state: { bonus_action_used: true },
      class_resources: { second_wind_used: true },
      hp_current: 9,
    })
    useItemMock.mockResolvedValue({
      item: 'Healing Potion',
      effect: 'heal',
      heal_amount: 6,
      hp_after: 10,
      equipment: { gear: [] },
      turn_state: { action_used: true },
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
      session: {
        session_id: 'sess-1',
        player: {
          id: 'char-1',
          name: 'Tester',
          hp_current: 4,
          equipment: {
            gear: [
              { name: 'Healing Potion', zh: '治疗药水', consumable: true },
            ],
          },
        },
      },
      setSession: vi.fn(),
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
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: true, dodging: true })
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

  it('does not run class features when the current user does not control this turn', async () => {
    const { result, deps } = renderActions({ canActThisTurn: false })

    await act(async () => {
      await result.current.handleClassFeature('second_wind')
    })

    expect(classFeatureMock).not.toHaveBeenCalled()
    expect(rollDice3DMock).not.toHaveBeenCalled()
    expect(deps.setIsProcessing).not.toHaveBeenCalled()
  })

  it('uses healing potions through the inventory endpoint and merges session state', async () => {
    const { result, deps, processingRef } = renderActions()

    await act(async () => {
      await result.current.handleHealingPotion()
    })

    expect(useItemMock).toHaveBeenCalledWith('char-1', 'Healing Potion', {
      session_id: 'sess-1',
      use_in_combat: true,
    })
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: true })
    expect(deps.addLog).toHaveBeenCalledWith({
      role: 'player',
      content: '治疗药水 恢复 6 HP',
      log_type: 'combat',
    })
    expect(deps.setSession).toHaveBeenCalledWith(expect.objectContaining({
      player: expect.objectContaining({
        hp_current: 10,
        equipment: { gear: [] },
      }),
    }))
    expect(processingRef.current).toBe(false)
    expect(deps.setIsProcessing).toHaveBeenLastCalledWith(false)
  })

  it('shows a local error when no healing potion is available', async () => {
    const { result, deps } = renderActions({
      session: {
        session_id: 'sess-1',
        player: {
          id: 'char-1',
          equipment: { gear: [{ name: 'Rope' }] },
        },
      },
    })

    await act(async () => {
      await result.current.handleHealingPotion()
    })

    expect(deps.setError).toHaveBeenCalledWith('背包中没有可用的治疗药剂')
    expect(useItemMock).not.toHaveBeenCalled()
    expect(deps.setIsProcessing).not.toHaveBeenCalled()
  })
})
