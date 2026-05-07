import { describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useCombatLog } from '../useCombatLog'

describe('useCombatLog', () => {
  it('appends timestamped combat log entries without mutating existing logs', () => {
    vi.spyOn(Date, 'now').mockReturnValue(12345)
    vi.spyOn(Math, 'random').mockReturnValue(0.6789)

    const { result } = renderHook(() => useCombatLog())

    const before = result.current.logs
    act(() => {
      result.current.addLog({
        role: 'player',
        content: '命中目标',
        log_type: 'combat',
      })
    })

    expect(before).toEqual([])
    expect(result.current.logs).toEqual([{
      id: 'log-12345-0.6789',
      role: 'player',
      content: '命中目标',
      log_type: 'combat',
    }])

    Date.now.mockRestore()
    Math.random.mockRestore()
  })
})
