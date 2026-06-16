import { describe, expect, it } from 'vitest'

import { formatAdventureDiceLog } from '../adventureDiceLog'

describe('adventureDiceLog', () => {
  it('formats Feather Fall reaction dice rows without undefined math', () => {
    expect(formatAdventureDiceLog({
      kind: 'reaction',
      reaction_type: 'feather_fall',
      spell_name: 'Feather Fall',
      slot_level: '1st',
      damage_prevented: 11,
    })).toBe('Feather Fall reaction：prevented 11 damage · spent 1st slot')
  })

  it('keeps ordinary d20 dice rows readable', () => {
    expect(formatAdventureDiceLog({
      label: 'Perception',
      raw: 12,
      modifier: 3,
      total: 15,
      dc: 14,
      success: true,
    })).toBe('Perception：12 + 3 = 15 vs DC14 → 成功')
  })

  it('omits missing modifier and total fields instead of rendering undefined math', () => {
    expect(formatAdventureDiceLog({
      kind: 'damage',
      label: 'Hidden Pit damage',
      raw: 7,
      total: 0,
    })).toBe('Hidden Pit damage：7 = 0')
  })

  it('formats dice_result arrays as readable summaries', () => {
    expect(formatAdventureDiceLog([
      {
        label: 'Hidden Pit saving throw',
        raw: 3,
        modifier: 2,
        total: 5,
        dc: 14,
        success: false,
      },
      {
        kind: 'reaction',
        reaction_type: 'feather_fall',
        damage_prevented: 7,
      },
    ])).toBe('Hidden Pit saving throw：3 + 2 = 5 vs DC14 → 失败 | Feather Fall reaction：prevented 7 damage')
  })
})
