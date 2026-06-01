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
      { key: 'level', label: '1环' },
      { key: 'type', label: '控制' },
      { key: 'aoe', label: '范围' },
      { key: 'target', label: '地点' },
      { key: 'save', label: '力量豁免' },
      { key: 'concentration', label: '专注' },
    ])
  })

  it('marks cantrip attack roll spells', () => {
    expect(buildSpellRuleBadges({
      name: 'Fire Bolt',
      level: 0,
      type: 'damage',
      target_type: 'enemy',
      desc: 'Make a ranged spell attack.',
    }, { isCantrip: true })).toContainEqual({ key: 'attack', label: '法术攻击' })
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
      { key: 'effect', label: '效果', value: '伤害 8d6' },
      { key: 'resolve', label: '结算', value: '敏捷豁免 · 成功减半' },
      { key: 'timing', label: '时机', value: '1 动作 · 射程 150 ft' },
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
    })).toContainEqual({ key: 'resolve', label: '结算', value: '感知豁免 · DC 15' })

    expect(buildSpellRulePreview({
      name: 'Guiding Bolt',
      level: 1,
      type: 'damage',
      desc: 'Make a ranged spell attack.',
    }, {
      caster: { derived: { spell_attack_bonus: 6 } },
    })).toContainEqual({ key: 'resolve', label: '结算', value: '法术攻击检定 · +6' })
  })
})
