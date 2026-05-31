import { describe, expect, it } from 'vitest'
import { buildConditionSummaries } from '../conditionRules'

describe('buildConditionSummaries', () => {
  it('summarizes harmful conditions with duration hints', () => {
    expect(buildConditionSummaries(['poisoned'], { poisoned: 2 })).toEqual([
      {
        key: 'poisoned',
        label: 'Poisoned',
        tone: 'harm',
        summary: 'Disadvantage on attack rolls and ability checks.',
        title: 'Poisoned: Disadvantage on attack rolls and ability checks. Duration: 2 rounds.',
        duration: 2,
      },
    ])
  })

  it('marks resistance-style conditions as buffs', () => {
    expect(buildConditionSummaries(['fire_resistance'])[0]).toMatchObject({
      key: 'fire_resistance',
      label: 'Fire Resistance',
      tone: 'buff',
    })
  })
})
