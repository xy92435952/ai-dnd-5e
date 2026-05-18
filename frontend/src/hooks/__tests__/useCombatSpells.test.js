import { describe, expect, it, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

const { getSpellsMock } = vi.hoisted(() => ({
  getSpellsMock: vi.fn(),
}))

vi.mock('../../api/game', () => ({
  gameApi: {
    getSpells: getSpellsMock,
  },
}))

import { useCombatSpells } from '../useCombatSpells'

describe('useCombatSpells', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads spells and falls back to an empty list', async () => {
    getSpellsMock.mockResolvedValue([{ name: 'Fire Bolt' }])

    const { result } = renderHook(() => useCombatSpells('sess-1'))

    await waitFor(() => expect(result.current).toEqual([{ name: 'Fire Bolt' }]))
  })

  it('keeps empty spells when loading fails', async () => {
    getSpellsMock.mockRejectedValue(new Error('offline'))

    const { result } = renderHook(() => useCombatSpells('sess-1'))

    await waitFor(() => expect(getSpellsMock).toHaveBeenCalled())
    expect(result.current).toEqual([])
  })
})
