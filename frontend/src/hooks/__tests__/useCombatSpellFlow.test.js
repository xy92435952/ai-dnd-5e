import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { spellRollMock, spellConfirmMock, rollDice3DMock } = vi.hoisted(() => ({
  spellRollMock: vi.fn(),
  spellConfirmMock: vi.fn(),
  rollDice3DMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    spellRoll: spellRollMock,
    spellConfirm: spellConfirmMock,
  },
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  rollDice3D: rollDice3DMock,
}))

import { useCombatSpellFlow } from '../useCombatSpellFlow'

describe('useCombatSpellFlow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    spellRollMock.mockResolvedValue({
      pending_spell_id: 'pending-spell-1',
      damage_dice: '2d6',
      targets: [{ id: 'enemy-1', name: '训练假人' }],
      turn_state: { action_used: true },
    })
    spellConfirmMock.mockResolvedValue({
      target_id: 'enemy-1',
      target_new_hp: 3,
      remaining_slots: { '1st': 1 },
      narration: '魔法飞弹击中训练假人',
      turn_state: { action_used: true, spell_cast: true },
      combat_over: false,
    })
    rollDice3DMock.mockResolvedValue({ total: 7, rolls: [3, 4] })
  })

  it('runs the two-step spell flow and applies confirm results after the dice delay', async () => {
    const processingRef = { current: false }
    const setIsProcessing = vi.fn()
    const setSpellModalOpen = vi.fn()
    const setError = vi.fn()
    const setTurnState = vi.fn()
    const setCombat = vi.fn()
    const setPlayerSpellSlots = vi.fn()
    const addLog = vi.fn()
    const setSelectedTarget = vi.fn()
    const setCombatOver = vi.fn()
    const showDice = vi.fn()

    const { result } = renderHook(() => useCombatSpellFlow({
      sessionId: 'sess-1',
      playerId: 'char-1',
      selectedTarget: 'enemy-1',
      isProcessing: false,
      processingRef,
      setIsProcessing,
      setSpellModalOpen,
      setError,
      setTurnState,
      setCombat,
      setPlayerSpellSlots,
      addLog,
      setSelectedTarget,
      setCombatOver,
      showDice,
    }))

    await act(async () => {
      await result.current({ name: '魔法飞弹', type: 'damage' }, 1)
    })

    expect(spellRollMock).toHaveBeenCalledWith(
      'sess-1',
      'char-1',
      '魔法飞弹',
      1,
      'enemy-1',
      ['enemy-1'],
    )
    expect(addLog).toHaveBeenCalledWith({
      role: 'system',
      content: '魔法飞弹 → 训练假人 — 掷骰 2d6',
      log_type: 'system',
    })
    expect(setSpellModalOpen).toHaveBeenCalledWith(false)
    expect(processingRef.current).toBe(true)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200)
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(6, 2)
    expect(showDice).toHaveBeenCalledWith({ faces: 6, result: 7, label: '魔法飞弹', count: 2 })
    expect(spellConfirmMock).toHaveBeenCalledWith('sess-1', 'pending-spell-1', [3, 4])

    const hpUpdater = setCombat.mock.calls[0][0]
    expect(hpUpdater({
      entities: {
        'enemy-1': { id: 'enemy-1', name: '训练假人', hp_current: 7 },
      },
    }).entities['enemy-1'].hp_current).toBe(3)
    expect(setTurnState).toHaveBeenLastCalledWith({ action_used: true, spell_cast: true })
    expect(setPlayerSpellSlots).toHaveBeenCalledWith({ '1st': 1 })
    expect(addLog).toHaveBeenLastCalledWith({
      role: 'player',
      content: '魔法飞弹击中训练假人',
      log_type: 'combat',
    })
    expect(setSelectedTarget).toHaveBeenCalledWith(null)
    expect(processingRef.current).toBe(false)
    expect(setIsProcessing).toHaveBeenLastCalledWith(false)
  })

  it('does not cast when the current user does not control this turn', async () => {
    const setIsProcessing = vi.fn()
    const setSpellModalOpen = vi.fn()

    const { result } = renderHook(() => useCombatSpellFlow({
      sessionId: 'sess-1',
      playerId: 'char-1',
      selectedTarget: 'enemy-1',
      isProcessing: false,
      canActThisTurn: false,
      processingRef: { current: false },
      setIsProcessing,
      setSpellModalOpen,
      setError: vi.fn(),
      setTurnState: vi.fn(),
      setCombat: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      addLog: vi.fn(),
      setSelectedTarget: vi.fn(),
      setCombatOver: vi.fn(),
      showDice: vi.fn(),
    }))

    await act(async () => {
      await result.current({ name: '魔法飞弹', type: 'damage' }, 1)
    })

    expect(spellRollMock).not.toHaveBeenCalled()
    expect(setSpellModalOpen).not.toHaveBeenCalled()
    expect(setIsProcessing).not.toHaveBeenCalled()
  })
})
