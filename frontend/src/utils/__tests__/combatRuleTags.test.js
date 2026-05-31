import { describe, expect, it } from 'vitest'
import { buildCombatRuleTags } from '../combatRuleTags'

describe('combatRuleTags', () => {
  it('explains advantage, cover and effective AC from attack prediction metadata', () => {
    expect(buildCombatRuleTags({
      advantage: true,
      cover_bonus: 2,
      target_ac: 14,
      effective_target_ac: 16,
      advantage_sources: ['Pack Tactics'],
      modifiers: ['Advantage', 'Half cover', 'Pack Tactics'],
    })).toEqual([
      {
        key: 'advantage',
        label: 'Advantage',
        tone: 'good',
        title: 'Roll two d20 and use the higher result. Advantage sources: Pack Tactics.',
      },
      {
        key: 'advantage-source',
        label: 'Adv: Pack Tactics',
        tone: 'good',
        title: 'Advantage sources: Pack Tactics.',
      },
      {
        key: 'cover-2',
        label: 'Half cover +2 AC',
        tone: 'bad',
        title: 'Cover raises AC from 14 to 16 for this attack.',
      },
      {
        key: 'effective-ac',
        label: 'Eff AC 16',
        tone: 'warning',
        title: 'Base AC 14; effective AC 16 after cover and modifiers.',
      },
    ])
  })

  it('explains disadvantage and three-quarters cover', () => {
    const tags = buildCombatRuleTags({
      disadvantage: true,
      cover_bonus: 5,
      target_ac: 13,
      effective_target_ac: 18,
    })

    expect(tags.map(tag => tag.label)).toEqual([
      'Disadvantage',
      '3/4 cover +5 AC',
      'Eff AC 18',
    ])
    expect(tags[0].title).toContain('lower result')
    expect(tags[1].title).toBe('Cover raises AC from 13 to 18 for this attack.')
  })

  it('shows a flat roll when advantage and disadvantage cancel out', () => {
    expect(buildCombatRuleTags({
      advantage: false,
      disadvantage: false,
      advantage_sources: ['target restrained'],
      disadvantage_sources: ['attacker poisoned'],
      effective_target_ac: 12,
    }).map(tag => tag.label)).toEqual([
      'Flat roll',
      'Adv: target restrained',
      'Dis: attacker poisoned',
      'Eff AC 12',
    ])
  })

  it('summarizes multiple source labels without repeating vague state modifiers', () => {
    const tags = buildCombatRuleTags({
      disadvantage: true,
      disadvantage_sources: ['attacker poisoned', 'target invisible'],
      modifiers: ['劣势', '攻击者状态+', '目标状态+'],
    })

    expect(tags.map(tag => tag.label)).toEqual([
      'Disadvantage',
      'Dis: attacker poisoned +1',
    ])
    expect(tags[0].title).toContain('attacker poisoned / target invisible')
  })

  it('returns no tags without prediction metadata', () => {
    expect(buildCombatRuleTags(null)).toEqual([])
  })
})
