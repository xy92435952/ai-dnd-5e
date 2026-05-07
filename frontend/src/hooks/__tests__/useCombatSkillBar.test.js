import { describe, expect, it, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

const { getSkillBarMock } = vi.hoisted(() => ({
  getSkillBarMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    getSkillBar: getSkillBarMock,
  },
}))

import { useCombatSkillBar } from '../useCombatSkillBar'

describe('useCombatSkillBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads skill bar when session and player are ready', async () => {
    getSkillBarMock.mockResolvedValue({ bar: [{ k: 'atk' }] })

    const { result } = renderHook(() => useCombatSkillBar({
      sessionId: 'sess-1',
      playerId: 'char-1',
      refreshKey: 0,
    }))

    await waitFor(() => expect(result.current).toEqual([{ k: 'atk' }]))
    expect(getSkillBarMock).toHaveBeenCalledWith('sess-1', 'char-1')
  })

  it('skips loading until ids are ready', () => {
    const { result } = renderHook(() => useCombatSkillBar({
      sessionId: 'sess-1',
      playerId: null,
      refreshKey: 0,
    }))

    expect(result.current).toBe(null)
    expect(getSkillBarMock).not.toHaveBeenCalled()
  })
})
