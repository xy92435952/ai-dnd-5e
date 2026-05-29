import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { attackRollMock, rollDice3DMock } = vi.hoisted(() => ({
  attackRollMock: vi.fn(),
  rollDice3DMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    attackRoll: attackRollMock,
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
})
