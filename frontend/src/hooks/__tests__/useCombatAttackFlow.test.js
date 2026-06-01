import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { attackRollMock, damageRollMock, rollDice3DMock } = vi.hoisted(() => ({
  attackRollMock: vi.fn(),
  damageRollMock: vi.fn(),
  rollDice3DMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    attackRoll: attackRollMock,
    damageRoll: damageRollMock,
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
    )
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: true, attacks_made: 1 })
    expect(deps.setSelectedTarget).toHaveBeenCalledWith(null)
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
