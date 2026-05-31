import { describe, expect, it } from 'vitest'
import { buildSpellRuleBadges, buildSpellRulePreview } from '../spellRuleBadges'

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

  it('previews spell effect, resolution, and timing before selection', () => {
    expect(buildSpellRulePreview({
      name: 'Fireball',
      level: 3,
      type: 'damage',
      damage: '8d6',
      save: 'dex',
      half_on_save: true,
      casting_time: '1 action',
      range: '150 ft',
    })).toEqual([
      { key: 'effect', label: 'Effect', value: 'Damage 8d6' },
      { key: 'resolve', label: 'Resolve', value: 'DEX save · half on save' },
      { key: 'timing', label: 'Timing', value: '1 action · Range 150 ft' },
    ])
  })

  it('includes caster DC and spell attack bonus when available', () => {
    expect(buildSpellRulePreview({
      name: 'Hold Person',
      level: 2,
      type: 'control',
      save: 'wis',
      casting_time: '1 action',
    }, {
      caster: { derived: { spell_save_dc: 15 } },
    })).toContainEqual({ key: 'resolve', label: 'Resolve', value: 'WIS save · DC 15' })

    expect(buildSpellRulePreview({
      name: 'Guiding Bolt',
      level: 1,
      type: 'damage',
      desc: 'Make a ranged spell attack.',
    }, {
      caster: { derived: { spell_attack_bonus: 6 } },
    })).toContainEqual({ key: 'resolve', label: 'Resolve', value: 'Spell attack roll · +6' })
  })
})
