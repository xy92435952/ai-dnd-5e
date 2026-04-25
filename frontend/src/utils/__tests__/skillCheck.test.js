/**
 * skillCheck.js 单元测试 —— computeChoicePreview 的成功率推导。
 *
 * 主要验：
 *   - 没 skill_check 标记的选项返回 null
 *   - 熟练加值正确叠加
 *   - 边界 dc（极易/极难）成功率被 clamp 到 [5%, 95%]
 *   - hint 文案按规则触发
 */
import { describe, it, expect } from 'vitest'
import { computeChoicePreview, KIND_TO_ABILITY, KIND_TO_SKILL_ZH } from '../skillCheck'


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
  it('没 skill_check 标记 → null', () => {
    const choice = { tags: [{ dc: 15, kind: 'athletic' }], skill_check: false }
    expect(computeChoicePreview(choice, makePlayer())).toBeNull()
  })

  it('没 dc tag → null', () => {
    const choice = { tags: [], skill_check: true }
    expect(computeChoicePreview(choice, makePlayer())).toBeNull()
  })

  it('player 为 null → null', () => {
    const choice = { tags: [{ dc: 10, kind: 'insight' }], skill_check: true }
    expect(computeChoicePreview(choice, null)).toBeNull()
  })

  it('熟练 + DC 10 + str_mod 3 → modifier=5, 成功率高', () => {
    const choice = { tags: [{ dc: 10, kind: 'athletic' }], skill_check: true }
    const result = computeChoicePreview(choice, makePlayer())
    expect(result).not.toBeNull()
    const modRow = result.rows.find(r => r.label.includes('运动修正'))
    expect(modRow.value).toContain('+5')
    expect(modRow.value).toContain('(熟)')
    // dc 10 - 5 = 5 → P(d20 >= 5) = 80% → hint "胜券在握"
    expect(result.hint).toBe('胜券在握')
  })

  it('不熟练 + 高 DC → 成功率低', () => {
    const choice = { tags: [{ dc: 18, kind: 'arcana' }], skill_check: true }
    const result = computeChoicePreview(choice, makePlayer())
    // arcana → int_mod=0, 不在 proficient_skills
    const modRow = result.rows.find(r => r.label.includes('奥秘修正'))
    expect(modRow.value).toBe('+0')
    // dc 18 - 0 = 18 → 成功率 < 30% → hint "九死一生"
    expect(result.hint).toBe('九死一生')
  })

  it('成功率 clamp 在 [5%, 95%]', () => {
    // dc 1 (极易) → 应该被 clamp 到 95%
    const easy = { tags: [{ dc: 1, kind: 'check' }], skill_check: true }
    const r1 = computeChoicePreview(easy, makePlayer())
    expect(r1.rows.find(r => r.label === '成功率').value).toBe('95%')

    // dc 30 (极难) + 不熟练 wis check → 应该被 clamp 到 5%
    const hard = { tags: [{ dc: 30, kind: 'check' }], skill_check: true }
    const r2 = computeChoicePreview(hard, makePlayer())
    expect(r2.rows.find(r => r.label === '成功率').value).toBe('5%')
  })

  it('choice.ended → hint "结束当前场景"，覆盖成功率 hint', () => {
    const choice = { tags: [{ dc: 10, kind: 'athletic' }], skill_check: true, ended: true }
    expect(computeChoicePreview(choice, makePlayer()).hint).toContain('结束当前场景')
  })

  it('choice.action → hint "攻击性行动"，覆盖成功率 hint', () => {
    const choice = { tags: [{ dc: 12, kind: 'athletic' }], skill_check: true, action: true }
    expect(computeChoicePreview(choice, makePlayer()).hint).toContain('攻击性行动')
  })

  it('未知 kind 兜底用 wis', () => {
    const choice = { tags: [{ dc: 10, kind: 'mysterious-skill' }], skill_check: true }
    const result = computeChoicePreview(choice, makePlayer())
    // wis_mod = 1（无熟练），modifier=+1
    const modRow = result.rows.find(r => r.label.includes('修正'))
    expect(modRow.value).toContain('+1')
  })
})


describe('KIND_TO_ABILITY mapping', () => {
  it('完整覆盖关键技能', () => {
    expect(KIND_TO_ABILITY.athletic).toBe('str')
    expect(KIND_TO_ABILITY.acrobat).toBe('dex')
    expect(KIND_TO_ABILITY.arcana).toBe('int')
    expect(KIND_TO_ABILITY.insight).toBe('wis')
    expect(KIND_TO_ABILITY.persuade).toBe('cha')
  })
})


describe('KIND_TO_SKILL_ZH mapping', () => {
  it('返回中文技能名（用于熟练查表）', () => {
    expect(KIND_TO_SKILL_ZH.athletic).toBe('运动')
    expect(KIND_TO_SKILL_ZH.stealth).toBe('隐匿')
    expect(KIND_TO_SKILL_ZH.arcana).toBe('奥秘')
  })
})
