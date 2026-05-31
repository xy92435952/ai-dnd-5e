import { describe, expect, it } from 'vitest'
import { buildSpellRuleBadges } from '../spellRuleBadges'

describe('buildSpellRuleBadges', () => {
  it('summarizes aoe save concentration spells', () => {
    expect(buildSpellRuleBadges({
      name: 'Entangle',
      level: 1,
      type: 'control',
      aoe: true,
      target_type: 'ground point',
      save: 'str',
      concentration: true,
    })).toEqual([
      { key: 'level', label: 'L1' },
      { key: 'type', label: 'Control' },
      { key: 'aoe', label: 'AoE' },
      { key: 'target', label: 'Point' },
      { key: 'save', label: 'Save STR' },
      { key: 'concentration', label: 'Concentration' },
    ])
  })

  it('marks cantrip attack roll spells', () => {
    expect(buildSpellRuleBadges({
      name: 'Fire Bolt',
      level: 0,
      type: 'damage',
      target_type: 'enemy',
      desc: 'Make a ranged spell attack.',
    }, { isCantrip: true })).toContainEqual({ key: 'attack', label: 'Attack roll' })
  })
})
