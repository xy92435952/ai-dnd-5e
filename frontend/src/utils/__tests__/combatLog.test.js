import { describe, expect, it } from 'vitest'
import { buildCombatLogView, buildCombatStateChangeSummary } from '../combatLog'

describe('combatLog', () => {
  it('separates attack rules, dice, narration, and hp state changes', () => {
    const view = buildCombatLogView({
      role: 'player',
      content: 'Tester 劈中训练假人。',
      log_type: 'combat',
      dice_result: {
        attack: {
          d20: 14,
          attack_bonus: 5,
          attack_total: 19,
          target_ac: 13,
          hit: true,
        },
        damage: 6,
        total_damage: 4,
      },
      state_changes: ['训练假人 HP 7 -> 3', '动作已用'],
    })

    expect(view.roleLabel).toBe('玩家')
    expect(view.tone).toBe('dmg')
    expect(view.sections).toEqual([
      { kind: 'rules', label: '规则', items: ['命中 · 19 vs AC13'] },
      { kind: 'dice', label: '骰子', items: ['d20 14 +5 = 19', '伤害 6', '实际伤害 4'] },
      { kind: 'narration', label: '叙事', items: ['Tester 劈中训练假人。'] },
      { kind: 'state', label: '状态', items: ['训练假人 HP 7 -> 3', '动作已用'] },
    ])
  })

  it('summarizes result payload state changes without depending on narration text', () => {
    expect(buildCombatStateChangeSummary({
      target_id: 'enemy-1',
      target_new_hp: 0,
      target_state: {
        target_id: 'enemy-1',
        hp_current: 0,
        death_saves: { successes: 0, failures: 1 },
        conditions: ['unconscious'],
        life_state: 'dying',
      },
      remaining_slots: { '1st': 1 },
      turn_state: {
        action_used: true,
        reaction_used: true,
        attacks_made: 1,
        attacks_max: 2,
        movement_used: 2,
        movement_max: 6,
      },
      combat_over: true,
    }, {
      targetName: '训练假人',
      hpBefore: 7,
    })).toEqual([
      '训练假人 HP 7 -> 0',
      '死亡豁免 成功 0/3，失败 1/3',
      '状态 unconscious',
      '法术位剩余 1环 1',
      '动作已用，反应已用，攻击 1/2，移动剩余 4/6',
      '战斗结束',
    ])
  })

  it('keeps miss and death-save dice visually distinct', () => {
    expect(buildCombatLogView({
      role: 'system',
      log_type: 'dice',
      content: 'Tester 死亡豁免成功并稳定下来。',
      dice_result: { type: 'death_save', d20: 17 },
    })).toMatchObject({
      tone: 'dice',
      sections: expect.arrayContaining([
        { kind: 'dice', label: '骰子', items: ['死亡豁免 d20 17'] },
      ]),
    })

    expect(buildCombatLogView({
      role: 'enemy',
      log_type: 'combat',
      content: '哥布林挥空。',
      dice_result: {
        attack: { d20: 3, attack_total: 7, target_ac: 15, hit: false },
      },
    })).toMatchObject({
      tone: 'miss',
    })
  })
})
