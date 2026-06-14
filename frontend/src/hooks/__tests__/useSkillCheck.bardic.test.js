import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../api/client', () => ({
  gameApi: {
    skillCheck: vi.fn(),
  },
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  rollDice3D: vi.fn(),
}))

vi.mock('../../juice', () => ({
  JuiceAudio: { crit: vi.fn(), miss: vi.fn(), unlock: vi.fn() },
  shake: vi.fn(),
}))

import { gameApi } from '../../api/client'
import { rollDice3D } from '../../components/DiceRollerOverlay'
import { useSkillCheck } from '../useSkillCheck'

describe('useSkillCheck Bardic Inspiration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('rolls and spends Bardic Inspiration when the pending check opts in', async () => {
    const addLog = vi.fn()
    const onBardicInspirationSpent = vi.fn()
    rollDice3D
      .mockResolvedValueOnce({ total: 10, rolls: [10] })
      .mockResolvedValueOnce({ total: 5, rolls: [5] })
    gameApi.skillCheck.mockResolvedValue({
      d20: 10,
      modifier: 5,
      total: 20,
      success: true,
      proficient: true,
      bardic_inspiration: {
        spent: true,
        die: 'd8',
        roll: 5,
        uses_remaining: 0,
      },
    })

    const { result } = renderHook(() => useSkillCheck({
      sessionId: 'sess-1',
      playerId: 'char-1',
      player: { class_resources: { bardic_inspiration: { die: 'd8', uses_remaining: 1 } } },
      addLog,
      onBardicInspirationSpent,
    }))

    act(() => {
      result.current.setPendingCheck({
        check_type: 'Athletics',
        dc: 20,
        use_bardic_inspiration: true,
      })
    })

    await act(async () => {
      await result.current.rollPending()
    })

    expect(rollDice3D).toHaveBeenNthCalledWith(1, 20, 1)
    expect(rollDice3D).toHaveBeenNthCalledWith(2, 8)
    expect(gameApi.skillCheck).toHaveBeenCalledWith({
      session_id: 'sess-1',
      character_id: 'char-1',
      skill: 'Athletics',
      dc: 20,
      d20_value: 10,
      second_d20_value: null,
      use_bardic_inspiration: true,
      bardic_inspiration_roll: 5,
    })
    expect(onBardicInspirationSpent).toHaveBeenCalledWith(0)
    expect(addLog).toHaveBeenCalledWith(
      'dice',
      expect.stringContaining('Bardic d8+5'),
      'dice',
      expect.objectContaining({ dice_result: expect.any(Object) }),
    )
  })
})
