import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { spellRollMock, spellConfirmMock, rollDice3DMock } = vi.hoisted(() => ({
  spellRollMock: vi.fn(),
  spellConfirmMock: vi.fn(),
  rollDice3DMock: vi.fn(),
}))

vi.mock('../../api/game', () => ({
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

  it('logs AoE mechanical results separately from narration', async () => {
    const processingRef = { current: false }
    const addLog = vi.fn()
    spellRollMock.mockResolvedValue({
      pending_spell_id: 'pending-spell-aoe',
      damage_dice: '8d6',
      targets: [
        { id: 'enemy-1', name: '哥布林' },
        { id: 'enemy-2', name: '骷髅' },
      ],
      turn_state: { action_used: true },
    })
    spellConfirmMock.mockResolvedValue({
      remaining_slots: { '3rd': 0 },
      narration: '火球在敌群中炸开。',
      turn_state: { action_used: true, spell_cast: true },
      combat_over: false,
      aoe_results: [
        { target_id: 'enemy-1', name: '哥布林', damage: 12, new_hp: 0 },
        { target_id: 'enemy-2', name: '骷髅', damage: 6, new_hp: 2 },
      ],
    })
    rollDice3DMock.mockResolvedValue({ total: 18, rolls: [4, 4, 3, 2, 1, 1, 2, 1] })

    const { result } = renderHook(() => useCombatSpellFlow({
      sessionId: 'sess-1',
      playerId: 'char-1',
      selectedTarget: 'enemy-1',
      isProcessing: false,
      processingRef,
      setIsProcessing: vi.fn(),
      setSpellModalOpen: vi.fn(),
      setError: vi.fn(),
      setTurnState: vi.fn(),
      setCombat: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      addLog,
      setSelectedTarget: vi.fn(),
      setCombatOver: vi.fn(),
      showDice: vi.fn(),
    }))

    await act(async () => {
      await result.current({ name: '火球术', type: 'damage', aoe: { radius: 20 } }, 3)
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200)
    })

    expect(addLog).toHaveBeenCalledWith({
      role: 'system',
      content: '范围结算：哥布林 12伤害；骷髅 6伤害',
      log_type: 'combat_mechanics',
    })
    expect(addLog).toHaveBeenLastCalledWith({
      role: 'player',
      content: '火球在敌群中炸开。',
      log_type: 'combat',
    })
  })
})
