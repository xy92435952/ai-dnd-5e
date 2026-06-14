import { describe, expect, it } from 'vitest'
import {
  buildConditionImpactTags,
  buildConditionSummaries,
  formatConditionLabel,
  getEndOfTurnRepeatSaveConditions,
} from '../conditionRules'

describe('buildConditionSummaries', () => {
  it('extracts end-of-turn repeat save metadata for Bardic prompts', () => {
    expect(getEndOfTurnRepeatSaveConditions(['blinded', 'poisoned'], {
      blinded: {
        repeat_save: 'end_of_turn',
        save_ability: 'con',
        save_dc: 15,
      },
      poisoned: 2,
    })).toEqual([
      expect.objectContaining({
        key: 'blinded',
        ability: 'con',
        dc: 15,
      }),
    ])
  })

  it('summarizes harmful conditions with duration hints', () => {
    expect(buildConditionSummaries(['poisoned'], { poisoned: 2 })).toEqual([
      {
        key: 'poisoned',
        label: '中毒',
        tone: 'harm',
        summary: '攻击骰和属性检定处于劣势。',
        title: '中毒：攻击骰和属性检定处于劣势。 持续：2 轮。',
        duration: 2,
      },
    ])
  })

  it('marks resistance-style conditions as buffs', () => {
    expect(buildConditionSummaries(['fire_resistance'])[0]).toMatchObject({
      key: 'fire_resistance',
      label: '火焰抗性',
      tone: 'buff',
    })
    expect(formatConditionLabel('fire_resistance')).toBe('火焰抗性')
    expect(formatConditionLabel('marked')).toBe('标记')
    expect(formatConditionLabel('custom_state')).toBe('Custom State')
  })

  it('builds compact deduped impact tags for tactical reading', () => {
    const tags = buildConditionImpactTags(['restrained', 'paralyzed', 'fire_resistance'], { restrained: 2 })
    const labels = tags.map(tag => tag.label)

    expect(labels).toEqual(expect.arrayContaining([
      '速度 0',
      '受击优势',
      '攻击劣势',
      '重击风险',
    ]))
    expect(tags.find(tag => tag.label === '速度 0')?.title).toContain('束缚 (2轮) / 麻痹')
  })

  it('surfaces resistance and generic beneficial effects as good impacts', () => {
    expect(buildConditionImpactTags(['fire_resistance'])).toEqual([
      expect.objectContaining({ key: 'resist', label: '抗性', tone: 'good' }),
    ])
    expect(buildConditionImpactTags(['blessed'])).toEqual([
      expect.objectContaining({ key: 'roll_bonus', label: '攻击/豁免 +d4', tone: 'good' }),
    ])
  })
})
