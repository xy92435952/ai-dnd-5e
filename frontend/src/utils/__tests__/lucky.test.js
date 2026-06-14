import { describe, expect, it } from 'vitest'
import { getLuckyPointsRemaining, updateLuckyPointsRemaining } from '../lucky'

describe('lucky utils', () => {
  it('reads remaining Lucky points from character or resource objects', () => {
    expect(getLuckyPointsRemaining({ class_resources: { lucky_points_remaining: 2 } })).toBe(2)
    expect(getLuckyPointsRemaining({ lucky_points_remaining: 1 })).toBe(1)
    expect(getLuckyPointsRemaining({})).toBe(0)
  })

  it('updates class_resources without mutating the original character', () => {
    const character = {
      id: 'char-1',
      class_resources: { lucky_points_remaining: 2, second_wind_used: false },
    }

    const updated = updateLuckyPointsRemaining(character, 1)

    expect(updated).toEqual({
      id: 'char-1',
      class_resources: { lucky_points_remaining: 1, second_wind_used: false },
    })
    expect(character.class_resources.lucky_points_remaining).toBe(2)
  })
})
