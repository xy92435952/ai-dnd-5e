import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { attackRollMock, damageRollMock, predictMock, rollDice3DMock } = vi.hoisted(() => ({
  attackRollMock: vi.fn(),
  damageRollMock: vi.fn(),
  predictMock: vi.fn(),
  rollDice3DMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    attackRoll: attackRollMock,
    damageRoll: damageRollMock,
    predict: predictMock,
  },
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  rollDice3D: rollDice3DMock,
}))

vi.mock('../../juice', () => ({
  JuiceAudio: {
    miss: vi.fn(),
    hit: vi.fn(),
    crit: vi.fn(),
  },
  shake: vi.fn(),
}))

import { useCombatAttackFlow } from '../useCombatAttackFlow'

describe('useCombatAttackFlow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    predictMock.mockResolvedValue(null)
    rollDice3DMock.mockResolvedValue({ total: 14, rolls: [14] })
    attackRollMock.mockResolvedValue({
      d20: 14,
      attack_bonus: 5,
      attack_total: 19,
      target_ac: 12,
      hit: false,
      is_crit: false,
      is_fumble: false,
      attacker_name: 'Hero',
      target_name: 'Goblin',
      attacks_made: 1,
      attacks_max: 1,
      damage_dice: '1d8+3',
      pending_attack_id: 'pending-1',
      turn_state: { action_used: true, attacks_made: 1 },
      narration: 'Hero misses Goblin.',
    })
    damageRollMock.mockResolvedValue({
      narration: 'Hero hits Goblin.',
      damage_total: 7,
      total_damage: 7,
      target_id: 'enemy-1',
      target_name: 'Goblin',
      target_new_hp: 5,
      can_smite: false,
      is_crit: false,
      turn_state: { action_used: true, attacks_made: 1 },
    })
  })

  function renderAttackFlow(overrides = {}) {
    const processingRef = { current: false }
    const deps = {
      sessionId: 'sess-1',
      playerId: 'char-1',
      selectedTarget: 'enemy-1',
      isRanged: true,
      selectedWeaponName: 'Longbow',
      combat: {
        round_number: 2,
        current_turn_index: 0,
        turn_order: [{ character_id: 'char-1', id: 'char-1' }],
      },
      isProcessing: false,
      canActThisTurn: true,
      isPlayerTurn: vi.fn(() => true),
      processingRef,
      setIsProcessing: vi.fn(),
      setError: vi.fn(),
      showDice: vi.fn(),
      addLog: vi.fn(),
      setTurnState: vi.fn(),
      setCombat: vi.fn(),
      setSelectedTarget: vi.fn(),
      setSmitePrompt: vi.fn(),
      setCombatOver: vi.fn(),
      ...overrides,
    }
    return { deps, processingRef, ...renderHook(() => useCombatAttackFlow(deps)) }
  }

  it('passes the selected weapon to attack-roll requests', async () => {
    const { result, deps } = renderAttackFlow()

    await act(async () => {
      await result.current()
    })

    expect(attackRollMock).toHaveBeenCalledWith(
      'sess-1',
      'char-1',
      'enemy-1',
      'ranged',
      false,
      14,
      '2:0:char-1',
      'Longbow',
      null,
    )
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: true, attacks_made: 1 })
    expect(deps.setSelectedTarget).toHaveBeenCalledWith(null)
  })

  it('spends Lucky on the next attack roll when enabled', async () => {
    const setUseLuckyAttack = vi.fn()
    const setClassResources = vi.fn()
    rollDice3DMock
      .mockResolvedValueOnce({ total: 2, rolls: [2] })
      .mockResolvedValueOnce({ total: 18, rolls: [18] })
    attackRollMock.mockResolvedValueOnce({
      d20: 18,
      attack_bonus: 5,
      attack_total: 23,
      target_ac: 12,
      hit: false,
      is_crit: false,
      is_fumble: false,
      attacker_name: 'Hero',
      target_name: 'Goblin',
      attacks_made: 1,
      attacks_max: 1,
      damage_dice: '1d8+3',
      pending_attack_id: 'pending-lucky',
      turn_state: { action_used: true, attacks_made: 1 },
      narration: 'Hero misses after spending luck.',
      lucky: {
        spent: true,
        d20_before: 2,
        d20_after: 18,
        lucky_points_remaining: 0,
      },
    })
    const { result, deps } = renderAttackFlow({
      classResources: { lucky_points_remaining: 1 },
      useLuckyAttack: true,
      setUseLuckyAttack,
      setClassResources,
    })

    await act(async () => {
      await result.current()
    })

    expect(rollDice3DMock).toHaveBeenNthCalledWith(1, 20, 1)
    expect(rollDice3DMock).toHaveBeenNthCalledWith(2, 20)
    expect(deps.showDice).toHaveBeenCalledWith({
      faces: 20,
      result: 18,
      label: 'Lucky reroll',
      count: 1,
    })
    expect(attackRollMock).toHaveBeenCalledWith(
      'sess-1',
      'char-1',
      'enemy-1',
      'ranged',
      false,
      2,
      '2:0:char-1',
      'Longbow',
      null,
      { useLucky: true, luckyD20Value: 18 },
    )
    expect(setUseLuckyAttack).toHaveBeenCalledWith(false)
    expect(setClassResources).toHaveBeenCalledWith(expect.any(Function))
    expect(setClassResources.mock.calls[0][0]({ lucky_points_remaining: 1 })).toEqual({
      lucky_points_remaining: 0,
    })
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      dice_result: {
        attack: expect.objectContaining({
          lucky: expect.objectContaining({
            spent: true,
            d20_before: 2,
            d20_after: 18,
          }),
        }),
      },
    }))
  })

  it('rolls two d20s for advantage and forwards both raw dice', async () => {
    rollDice3DMock.mockResolvedValueOnce({ total: 22, rolls: [4, 18] })
    attackRollMock.mockResolvedValueOnce({
      d20: 18,
      d20_rolls: [4, 18],
      selected_d20: 18,
      other_roll: 4,
      d20_selection: 'advantage',
      attack_bonus: 5,
      attack_total: 23,
      target_ac: 12,
      hit: false,
      is_crit: false,
      is_fumble: false,
      advantage: true,
      disadvantage: false,
      roll_state: 'advantage',
      advantage_sources: ['attacker helped'],
      attacker_name: 'Hero',
      target_name: 'Goblin',
      attacks_made: 1,
      attacks_max: 1,
      damage_dice: '1d8+3',
      pending_attack_id: 'pending-adv',
      turn_state: { action_used: true, attacks_made: 1 },
      narration: 'Hero presses the opening.',
    })
    const { result, deps } = renderAttackFlow({
      prediction: { advantage: true, disadvantage: false },
    })

    await act(async () => {
      await result.current()
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(20, 2)
    expect(deps.showDice).toHaveBeenCalledWith({
      faces: 20,
      result: 18,
      label: '攻击检定（优势）',
      count: 2,
    })
    expect(attackRollMock).toHaveBeenCalledWith(
      'sess-1',
      'char-1',
      'enemy-1',
      'ranged',
      false,
      4,
      '2:0:char-1',
      'Longbow',
      18,
    )
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      dice_result: {
        attack: expect.objectContaining({
          d20: 18,
          d20_rolls: [4, 18],
          selected_d20: 18,
          other_roll: 4,
          d20_selection: 'advantage',
          advantage: true,
          roll_state: 'advantage',
        }),
      },
    }))
  })

  it('rolls two d20s for disadvantage and forwards both raw dice', async () => {
    rollDice3DMock.mockResolvedValueOnce({ total: 22, rolls: [18, 4] })
    attackRollMock.mockResolvedValueOnce({
      d20: 4,
      d20_rolls: [18, 4],
      selected_d20: 4,
      other_roll: 18,
      d20_selection: 'disadvantage',
      attack_bonus: 5,
      attack_total: 9,
      target_ac: 12,
      hit: false,
      is_crit: false,
      is_fumble: false,
      advantage: false,
      disadvantage: true,
      roll_state: 'disadvantage',
      disadvantage_sources: ['attacker poisoned'],
      attacker_name: 'Hero',
      target_name: 'Goblin',
      attacks_made: 1,
      attacks_max: 1,
      damage_dice: '1d8+3',
      pending_attack_id: 'pending-dis',
      turn_state: { action_used: true, attacks_made: 1 },
      narration: 'Hero struggles through the poison.',
    })
    const { result, deps } = renderAttackFlow({
      prediction: { advantage: false, disadvantage: true },
    })

    await act(async () => {
      await result.current()
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(20, 2)
    expect(deps.showDice).toHaveBeenCalledWith({
      faces: 20,
      result: 4,
      label: '攻击检定（劣势）',
      count: 2,
    })
    expect(attackRollMock).toHaveBeenCalledWith(
      'sess-1',
      'char-1',
      'enemy-1',
      'ranged',
      false,
      18,
      '2:0:char-1',
      'Longbow',
      4,
    )
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      dice_result: {
        attack: expect.objectContaining({
          d20: 4,
          d20_rolls: [18, 4],
          selected_d20: 4,
          other_roll: 18,
          d20_selection: 'disadvantage',
          disadvantage: true,
          roll_state: 'disadvantage',
        }),
      },
    }))
  })

  it('refreshes prediction before rolling so late hidden advantage uses two d20s', async () => {
    predictMock.mockResolvedValueOnce({
      advantage: true,
      disadvantage: false,
      advantage_sources: ['attacker hidden'],
    })
    rollDice3DMock.mockResolvedValueOnce({ total: 23, rolls: [7, 16] })
    attackRollMock.mockResolvedValueOnce({
      d20: 16,
      d20_rolls: [7, 16],
      selected_d20: 16,
      other_roll: 7,
      d20_selection: 'advantage',
      attack_bonus: 5,
      attack_total: 21,
      target_ac: 12,
      hit: false,
      is_crit: false,
      is_fumble: false,
      advantage: true,
      disadvantage: false,
      roll_state: 'advantage',
      advantage_sources: ['attacker hidden'],
      attacker_name: 'Hero',
      target_name: 'Goblin',
      attacks_made: 1,
      attacks_max: 1,
      damage_dice: '1d8+3',
      pending_attack_id: 'pending-hidden',
      turn_state: { action_used: true, attacks_made: 1 },
      narration: 'Hero reveals their position.',
    })
    const { result } = renderAttackFlow({
      prediction: { advantage: false, disadvantage: false },
    })

    await act(async () => {
      await result.current()
    })

    expect(predictMock).toHaveBeenCalledWith('sess-1', 'char-1', 'enemy-1', 'atk', true)
    expect(rollDice3DMock).toHaveBeenCalledWith(20, 2)
    expect(attackRollMock).toHaveBeenCalledWith(
      'sess-1',
      'char-1',
      'enemy-1',
      'ranged',
      false,
      7,
      '2:0:char-1',
      'Longbow',
      16,
    )
  })

  it('keeps defender interception metadata on the attack log', async () => {
    attackRollMock.mockResolvedValueOnce({
      d20: 14,
      attack_bonus: 5,
      attack_total: 19,
      target_ac: 20,
      hit: false,
      is_crit: false,
      is_fumble: false,
      attacker_name: 'Hero',
      target_name: 'Cult Priest',
      attacks_made: 1,
      attacks_max: 1,
      damage_dice: '1d8+3',
      pending_attack_id: 'pending-guard',
      defender_interception: {
        defender_name: 'Shield Guard',
        protected_target_name: 'Cult Priest',
      },
      turn_state: { action_used: true, attacks_made: 1 },
      narration: 'Shield Guard forces the strike wide.',
    })
    const { result, deps } = renderAttackFlow()

    await act(async () => {
      await result.current()
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      dice_result: {
        attack: expect.objectContaining({
          defender_interception: {
            defender_name: 'Shield Guard',
            protected_target_name: 'Cult Priest',
          },
          disadvantage: true,
        }),
      },
      state_changes: expect.not.arrayContaining([
        expect.stringContaining('护卫干扰'),
      ]),
    }))
  })

  it('passes critical hit context into the smite prompt', async () => {
    vi.useFakeTimers()
    try {
      rollDice3DMock
        .mockResolvedValueOnce({ total: 20, rolls: [20] })
        .mockResolvedValueOnce({ total: 6, rolls: [6] })
      attackRollMock.mockResolvedValueOnce({
        d20: 20,
        attack_bonus: 5,
        attack_total: 25,
        target_ac: 12,
        hit: true,
        is_crit: true,
        is_fumble: false,
        attacker_name: 'Hero',
        target_name: 'Goblin',
        attacks_made: 1,
        attacks_max: 1,
        damage_dice: '1d8+3',
        pending_attack_id: 'pending-crit',
        turn_state: { action_used: true, attacks_made: 1 },
      })
      damageRollMock.mockResolvedValueOnce({
        narration: 'Hero crits Goblin.',
        damage_total: 9,
        total_damage: 15,
        target_id: 'enemy-1',
        target_name: 'Goblin',
        target_new_hp: 2,
        can_smite: true,
        is_crit: true,
        turn_state: { action_used: true, attacks_made: 1 },
      })
      const { result, deps } = renderAttackFlow()

      await act(async () => {
        await result.current()
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1800)
      })

      expect(damageRollMock).toHaveBeenCalledWith('sess-1', 'pending-crit', [6])
      expect(deps.setSmitePrompt).toHaveBeenCalledWith({
        show: true,
        targetId: 'enemy-1',
        isCrit: true,
      })
    } finally {
      vi.useRealTimers()
    }
  })
})
