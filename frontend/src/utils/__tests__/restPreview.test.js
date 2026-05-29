import { describe, expect, it } from 'vitest'
import { buildRestPreview, summarizeRestPreview } from '../restPreview'

describe('restPreview', () => {
  it('summarizes long rest healing, spell slots, conditions, and death saves', () => {
    const party = [{
      id: 'hero-1',
      name: 'Aria',
      char_class: 'Wizard',
      level: 4,
      hp_current: 5,
      hp_max: 18,
      hit_dice_remaining: 1,
      spell_slots: { '1st': 0, '2nd': 1 },
      derived: { spell_slots_max: { '1st': 3, '2nd': 2 } },
      conditions: ['poisoned', 'blinded'],
      death_saves: { successes: 1, failures: 1, stable: false },
    }]

    const [preview] = buildRestPreview(party, 'long')

    expect(preview.name).toBe('Aria')
    expect(preview.slotRestores).toEqual(['1st+3', '2nd+1'])
    expect(preview.conditionChanges).toEqual(['poisoned'])
    expect(preview.effects).toEqual(expect.arrayContaining([
      'HP 恢复到 18/18',
      '法术位 1st+3/2nd+1',
      '恢复部分生命骰',
      '尝试移除 poisoned',
      '重置濒死豁免',
    ]))
  })

  it('flags short rest hit-dice risk and pact slot recovery', () => {
    const summary = summarizeRestPreview([
      {
        id: 'fighter-1',
        name: 'Borin',
        char_class: 'Fighter',
        level: 2,
        hp_current: 3,
        hp_max: 14,
        hit_dice_remaining: 0,
        spell_slots: {},
        derived: {},
      },
      {
        id: 'warlock-1',
        name: 'Nyx',
        char_class: 'Warlock',
        level: 3,
        hp_current: 12,
        hp_max: 12,
        hit_dice_remaining: 2,
        spell_slots: { '2nd': 0 },
        derived: { caster_type: 'pact', spell_slots_max: { '2nd': 2 } },
      },
    ], 'short')

    expect(summary.wounded).toBe(1)
    expect(summary.hitDiceRisk).toBe(1)
    expect(summary.slotUsers).toBe(1)
    expect(summary.previews[0].effects).toContain('HP 缺 11，但生命骰不足')
    expect(summary.previews[1].effects).toContain('魔契法术位 2nd+2')
  })
})
