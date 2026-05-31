import { describe, expect, it } from 'vitest'
import { buildConditionImpactTags, buildConditionSummaries } from '../conditionRules'

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

  it('builds compact deduped impact tags for tactical reading', () => {
    const tags = buildConditionImpactTags(['restrained', 'paralyzed', 'fire_resistance'], { restrained: 2 })
    const labels = tags.map(tag => tag.label)

    expect(labels).toEqual(expect.arrayContaining([
      'Speed 0',
      'Hit adv',
      'Atk disadv',
      'Crit risk',
    ]))
    expect(tags.find(tag => tag.label === 'Speed 0')?.title).toContain('Restrained (2r) / Paralyzed')
  })

  it('surfaces resistance and generic beneficial effects as good impacts', () => {
    expect(buildConditionImpactTags(['fire_resistance'])).toEqual([
      expect.objectContaining({ key: 'resist', label: 'Resist', tone: 'good' }),
    ])
    expect(buildConditionImpactTags(['blessed'])).toEqual([
      expect.objectContaining({ key: 'buff_active', label: 'Buff', tone: 'good' }),
    ])
  })
})
