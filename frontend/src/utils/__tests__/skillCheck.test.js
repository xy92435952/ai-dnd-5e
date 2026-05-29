/**
 * skillCheck.js unit tests for choice preview probability, visible metadata,
 * and skill/ability mapping.
 */
import { describe, it, expect } from 'vitest'
import { computeChoicePreview, getChoiceCheckTag, KIND_TO_ABILITY, KIND_TO_SKILL_ZH } from '../skillCheck'

function makePlayer(overrides = {}) {
  return {
    derived: {
      proficiency_bonus: 2,
      ability_modifiers: { str: 3, dex: 2, con: 2, int: 0, wis: 1, cha: -1 },
    },
    proficient_skills: ['运动'],
    ...overrides,
  }
}

describe('computeChoicePreview', () => {
  it('没有 skill_check 标记时返回 null', () => {
    const choice = { tags: [{ dc: 15, kind: 'athletic' }], skill_check: false }
    expect(computeChoicePreview(choice, makePlayer())).toBeNull()
  })

  it('没有 dc metadata 时返回 null', () => {
    const choice = { tags: [], skill_check: true }
    expect(computeChoicePreview(choice, makePlayer())).toBeNull()
  })

  it('player 为 null 时返回 null', () => {
    const choice = { tags: [{ dc: 10, kind: 'insight' }], skill_check: true }
    expect(computeChoicePreview(choice, null)).toBeNull()
  })

  it('熟练 + DC 10 + str_mod 3 会生成低风险预览', () => {
    const choice = { tags: [{ dc: 10, kind: 'athletic' }], skill_check: true }
    const result = computeChoicePreview(choice, makePlayer())

    expect(result).not.toBeNull()
    expect(result.summary).toMatchObject({
      skill: '运动',
      ability: 'STR',
      dc: 10,
      modifier: '+5',
      success: '80%',
      risk: '低风险',
      riskTone: 'low',
    })

    const modRow = result.rows.find(row => row.label.includes('运动修正'))
    expect(modRow.value).toContain('+5')
    expect(modRow.value).toContain('(熟练)')
    expect(result.rows).toContainEqual({ label: '对应属性', value: 'STR' })
    expect(result.rows).toContainEqual({ label: '风险', value: '低风险 · 80%' })
    expect(result.hint).toBe('胜券在握')
  })

  it('不熟练 + 高 DC 会生成高风险预览', () => {
    const choice = { tags: [{ dc: 18, kind: 'arcana' }], skill_check: true }
    const result = computeChoicePreview(choice, makePlayer())

    expect(result.summary).toMatchObject({
      skill: '奥秘',
      ability: 'INT',
      risk: '高风险',
      riskTone: 'high',
    })
    const modRow = result.rows.find(row => row.label.includes('奥秘修正'))
    expect(modRow.value).toBe('+0')
    expect(result.hint).toBe('九死一生')
  })

  it('成功率 clamp 在 [5%, 95%]', () => {
    const easy = { tags: [{ dc: 1, kind: 'check' }], skill_check: true }
    const r1 = computeChoicePreview(easy, makePlayer())
    expect(r1.rows.find(row => row.label === '成功率').value).toBe('95%')

    const hard = { tags: [{ dc: 30, kind: 'check' }], skill_check: true }
    const r2 = computeChoicePreview(hard, makePlayer())
    expect(r2.rows.find(row => row.label === '成功率').value).toBe('5%')
  })

  it('choice.ended 覆盖成功率提示', () => {
    const choice = { tags: [{ dc: 10, kind: 'athletic' }], skill_check: true, ended: true }
    expect(computeChoicePreview(choice, makePlayer()).hint).toContain('结束当前场景')
  })

  it('choice.action 覆盖成功率提示', () => {
    const choice = { tags: [{ dc: 12, kind: 'athletic' }], skill_check: true, action: true }
    expect(computeChoicePreview(choice, makePlayer()).hint).toContain('攻击性行动')
  })

  it('未知 kind 兜底用 wis', () => {
    const choice = { tags: [{ dc: 10, kind: 'mysterious-skill' }], skill_check: true }
    const result = computeChoicePreview(choice, makePlayer())
    const modRow = result.rows.find(row => row.label.includes('修正'))
    expect(modRow.value).toContain('+1')
  })

  it('supports top-level skill check metadata when tags are missing', () => {
    const choice = { text: '看穿谎言', skill_check: true, check_type: '洞察', dc: 14 }

    expect(getChoiceCheckTag(choice)).toMatchObject({
      dc: 14,
      kind: '洞察',
      label: '洞察',
    })

    expect(computeChoicePreview(choice, makePlayer()).summary).toMatchObject({
      skill: '洞察',
      ability: 'WIS',
      dc: 14,
      modifier: '+1',
      success: '40%',
      risk: '中风险',
    })
  })
})

describe('KIND_TO_ABILITY mapping', () => {
  it('覆盖关键技能', () => {
    expect(KIND_TO_ABILITY.athletic).toBe('str')
    expect(KIND_TO_ABILITY.acrobat).toBe('dex')
    expect(KIND_TO_ABILITY.arcana).toBe('int')
    expect(KIND_TO_ABILITY.insight).toBe('wis')
    expect(KIND_TO_ABILITY.persuade).toBe('cha')
    expect(KIND_TO_ABILITY.洞察).toBe('wis')
  })
})

describe('KIND_TO_SKILL_ZH mapping', () => {
  it('返回中文技能名用于熟练匹配和 UI 显示', () => {
    expect(KIND_TO_SKILL_ZH.athletic).toBe('运动')
    expect(KIND_TO_SKILL_ZH.stealth).toBe('隐匿')
    expect(KIND_TO_SKILL_ZH.arcana).toBe('奥秘')
  })
})
