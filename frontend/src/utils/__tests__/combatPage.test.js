import { describe, it, expect, vi } from 'vitest'
import { COMBAT_GRID, ignoreOptionalEffect } from '../combatPage'

describe('COMBAT_GRID', () => {
  it('keeps the page grid and viewport dimensions stable', () => {
    expect(COMBAT_GRID).toEqual({
      width: 20,
      height: 12,
      viewWidth: 12,
      viewHeight: 8,
    })
  })
})

describe('ignoreOptionalEffect', () => {
  it('runs supported optional effects', () => {
    const fn = vi.fn()
    ignoreOptionalEffect(fn)
    expect(fn).toHaveBeenCalledOnce()
  })

  it('swallows unsupported optional effect failures', () => {
    expect(() => ignoreOptionalEffect(() => {
      throw new Error('audio unavailable')
    })).not.toThrow()
  })
})
