import { afterEach, describe, expect, it, vi } from 'vitest'
import { selectD20Roll } from '../d20Roll'

describe('selectD20Roll', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('selects the higher d20 for advantage', () => {
    expect(selectD20Roll({ rolls: [4, 18], total: 22 }, 'advantage')).toEqual({
      d20: 4,
      secondD20: 18,
      selected: 18,
      rolls: [4, 18],
    })
  })

  it('selects the lower d20 for disadvantage', () => {
    expect(selectD20Roll({ rolls: [18, 4], total: 22 }, 'disadvantage')).toEqual({
      d20: 18,
      secondD20: 4,
      selected: 4,
      rolls: [18, 4],
    })
  })

  it('pads missing advantage dice so callers still send two raw d20s', () => {
    vi.spyOn(Math, 'random').mockReturnValueOnce(0.85)

    expect(selectD20Roll({ rolls: [3], total: 3 }, 'advantage')).toEqual({
      d20: 3,
      secondD20: 18,
      selected: 18,
      rolls: [3, 18],
    })
  })

  it('uses one d20 for normal rolls', () => {
    expect(selectD20Roll({ rolls: [12, 19], total: 31 }, 'normal')).toEqual({
      d20: 12,
      secondD20: null,
      selected: 12,
      rolls: [12],
    })
  })
})
