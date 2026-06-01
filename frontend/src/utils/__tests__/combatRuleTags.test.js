import { describe, expect, it } from 'vitest'
import { buildCombatRuleTags } from '../combatRuleTags'

describe('combatRuleTags', () => {
  it('explains advantage, cover and effective AC from attack prediction metadata', () => {
    expect(buildCombatRuleTags({
      advantage: true,
      cover_bonus: 2,
      cover_detail: {
        bonus: 2,
        raw_bonus: 2,
        cells: [{ cell: '2_0', terrain: 'cover', weight: 1 }],
      },
      target_ac: 14,
      effective_target_ac: 16,
      advantage_sources: ['Pack Tactics'],
      modifiers: ['Advantage', 'Half cover', 'Pack Tactics'],
    })).toEqual([
      {
        key: 'advantage',
        label: '优势',
        tone: 'good',
        title: '掷两个 d20，取较高结果。优势来源：Pack Tactics。',
      },
      {
        key: 'advantage-source',
        label: '优势: Pack Tactics',
        sources: ['Pack Tactics'],
        tone: 'good',
        title: '优势来源：Pack Tactics。',
      },
      {
        key: 'cover-2',
        label: '半掩护 +2 AC',
        tone: 'bad',
        title: '掩护使本次攻击的 AC 从 14 提升到 16。路径经过 2_0 cover。',
      },
      {
        key: 'effective-ac',
        label: '有效 AC 16',
        tone: 'warning',
        title: '基础 AC 14；掩护和修正后本次攻击有效 AC 16。',
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
      '劣势',
      '3/4 掩护 +5 AC',
      '有效 AC 18',
    ])
    expect(tags[0].title).toContain('取较低结果')
    expect(tags[1].title).toBe('掩护使本次攻击的 AC 从 13 提升到 18。')
  })

  it('shows a flat roll when advantage and disadvantage cancel out', () => {
    expect(buildCombatRuleTags({
      advantage: false,
      disadvantage: false,
      advantage_sources: ['target restrained'],
      disadvantage_sources: ['attacker poisoned'],
      effective_target_ac: 12,
    }).map(tag => tag.label)).toEqual([
      '优势抵消',
      '优势: 目标束缚',
      '劣势: 攻击者中毒',
      '有效 AC 12',
    ])
  })

  it('summarizes multiple source labels without repeating vague state modifiers', () => {
    const tags = buildCombatRuleTags({
      disadvantage: true,
      disadvantage_sources: ['attacker poisoned', 'target invisible'],
      modifiers: ['劣势', '攻击者状态+', '目标状态+'],
    })

    expect(tags.map(tag => tag.label)).toEqual([
      '劣势',
      '劣势: 攻击者中毒 +1',
    ])
    expect(tags[1].sources).toEqual(['攻击者中毒', '目标隐形'])
    expect(tags[0].title).toContain('攻击者中毒 / 目标隐形')
  })

  it('shows when cover is bypassed by a feature', () => {
    const tags = buildCombatRuleTags({
      cover_bonus: 0,
      target_ac: 14,
      effective_target_ac: 14,
      cover_detail: {
        bonus: 0,
        raw_bonus: 2,
        ignored_by: 'Sharpshooter',
        cells: [{ cell: '2_0', terrain: 'wall', weight: 1 }],
      },
    })

    expect(tags.map(tag => tag.label)).toEqual(['忽略掩护', '有效 AC 14'])
    expect(tags[0].title).toBe('掩护原本会提供 +2 AC，但被 Sharpshooter 忽略。路径经过 2_0 wall。')
  })

  it('returns no tags without prediction metadata', () => {
    expect(buildCombatRuleTags(null)).toEqual([])
  })
})
