import { afterEach, describe, expect, it, vi } from 'vitest'
import { normalizeDiceRollResult } from '../DiceRollerOverlay'

describe('normalizeDiceRollResult', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('expands DiceBox grouped rollsArray into raw dice values', () => {
    const result = normalizeDiceRollResult([
      {
        value: 22,
        qty: 2,
        rollsArray: [
          { sides: 20, value: 18 },
          { sides: 20, value: 4 },
        ],
      },
    ], 20, 2)

    expect(result).toEqual({ total: 22, rolls: [18, 4] })
  })

  it('uses child roll values before grouped value totals', () => {
    const result = normalizeDiceRollResult([
      {
        value: 12,
        rolls: {
          first: { value: 8 },
          second: { value: 4 },
        },
      },
    ], 20, 2)

    expect(result).toEqual({ total: 12, rolls: [8, 4] })
  })

  it('pads missing dice with bounded fallback rolls', () => {
    vi.spyOn(Math, 'random')
      .mockReturnValueOnce(0)
      .mockReturnValueOnce(0.99)

    const result = normalizeDiceRollResult(null, 20, 2)

    expect(result).toEqual({ total: 21, rolls: [1, 20] })
  })
})
