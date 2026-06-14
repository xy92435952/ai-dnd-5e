import { describe, expect, it } from 'vitest'
import {
  getBardicInspiration,
  hasBardicInspiration,
  updateBardicInspirationUses,
} from '../bardicInspiration'

describe('bardic inspiration utils', () => {
  it('reads an available granted inspiration die from character resources', () => {
    expect(getBardicInspiration({
      class_resources: {
        bardic_inspiration: {
          die: 'd8',
          uses_remaining: 1,
          source_character_name: 'Lyra',
        },
      },
    })).toEqual({
      die: 'd8',
      faces: 8,
      uses_remaining: 1,
      source_character_name: 'Lyra',
    })
  })

  it('returns null when no unused die remains', () => {
    expect(getBardicInspiration({ bardic_inspiration: { die: 'd8', uses_remaining: 0 } })).toBeNull()
    expect(hasBardicInspiration({ bardic_inspiration: { die: 'd8', uses_remaining: 0 } })).toBe(false)
  })

  it('updates remaining uses without mutating the original character', () => {
    const character = {
      id: 'char-1',
      class_resources: {
        bardic_inspiration: {
          die: 'd8',
          uses_remaining: 1,
        },
      },
    }

    const updated = updateBardicInspirationUses(character, 0)

    expect(updated).toEqual({
      id: 'char-1',
      class_resources: {
        bardic_inspiration: {
          die: 'd8',
          uses_remaining: 0,
        },
      },
    })
    expect(character.class_resources.bardic_inspiration.uses_remaining).toBe(1)
  })
})
