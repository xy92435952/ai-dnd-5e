import { describe, expect, it } from 'vitest'
import {
  buildCombatLogImpactSummary,
  buildCombatLogView,
  buildCombatResultImpactSummary,
  buildCombatStateChangeSummary,
} from '../combatLog'

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
    expect(view.feedback).toEqual([{ kind: 'hit', label: '命中' }])
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

  it('builds outcome feedback for attacks, saves, death saves, and concentration breaks', () => {
    expect(buildCombatLogView({
      dice_result: { attack: { hit: false, attack_total: 7, target_ac: 15 } },
    }).feedback).toEqual([{ kind: 'miss', label: '未命中' }])

    expect(buildCombatLogView({
      dice_result: { attack: { hit: true, is_crit: true, attack_total: 25, target_ac: 15 } },
    }).feedback).toEqual([{ kind: 'crit', label: '暴击' }])

    expect(buildCombatLogView({
      dice_result: { save_success: true },
    }).feedback).toEqual([{ kind: 'save-success', label: '豁免成功' }])

    expect(buildCombatLogView({
      dice_result: { save_result: { success: false } },
    }).feedback).toEqual([{ kind: 'save-failure', label: '豁免失败' }])

    expect(buildCombatLogView({
      dice_result: { type: 'death_save', d20: 12, outcome: 'stable' },
    }).feedback).toEqual([{ kind: 'death-save-success', label: '死亡豁免成功' }])

    expect(buildCombatLogView({
      dice_result: { type: 'death_save', d20: 5, outcome: 'failure' },
    }).feedback).toEqual([{ kind: 'death-save-failure', label: '死亡豁免失败' }])

    expect(buildCombatLogView({
      state_changes: ['专注中断：祝福术'],
    }).feedback).toEqual([{ kind: 'concentration-break', label: '专注中断' }])
  })

  it('surfaces defender interception as a rule and feedback badge', () => {
    const view = buildCombatLogView({
      role: 'player',
      log_type: 'combat',
      content: 'Shield Guard knocks the blade aside.',
      dice_result: {
        attack: {
          d20: 12,
          attack_bonus: 5,
          attack_total: 17,
          target_ac: 18,
          hit: false,
          defender_interception: {
            defender_name: 'Shield Guard',
            protected_target_name: 'Cult Priest',
            effect: 'disadvantage',
          },
        },
      },
    })

    expect(view.feedback).toEqual([
      { kind: 'miss', label: '未命中' },
      { kind: 'defender-interception', label: '护卫干扰' },
    ])
    expect(view.sections.find(section => section.kind === 'rules')).toEqual({
      kind: 'rules',
      label: '规则',
      items: [
        '未命中 · 17 vs AC18',
        'Shield Guard 护卫干扰：保护 Cult Priest，本次攻击劣势',
      ],
    })
  })

  it('does not infer a miss from spell damage logs without attack outcome', () => {
    const view = buildCombatLogView({
      role: 'player',
      log_type: 'combat',
      content: 'Fire Bolt scorches Voltaic Spark.',
      dice_result: {
        attack: {},
        damage: 6,
        total_damage: 6,
      },
      state_changes: ['Voltaic Spark HP 15 -> 9'],
    })

    expect(view.tone).toBe('dmg')
    expect(view.feedback).toEqual([])
    expect(view.sections.find(section => section.kind === 'rules')).toBeUndefined()
  })

  it('summarizes reaction hp rollback from reaction effects', () => {
    expect(buildCombatStateChangeSummary({
      reaction_type: 'shield',
      reaction_effect: {
        hp_before_reaction: 3,
        hp_after_reaction: 12,
        hp_restored: 9,
      },
      turn_state: { reaction_used: true },
    }, {
      targetName: 'Tester',
    })).toEqual([
      'Tester HP 3 -> 12（反应恢复 9）',
      '反应已用',
    ])
  })

  it('does not duplicate reaction hp rollback when target_state is also present', () => {
    const summary = buildCombatStateChangeSummary({
      reaction_type: 'shield',
      reaction_effect: {
        hp_before_reaction: 3,
        hp_after_reaction: 12,
        hp_restored: 9,
      },
      target_state: {
        target_id: 'char-2',
        hp_current: 12,
      },
      turn_state: { reaction_used: true },
    }, {
      targetName: 'Tester',
    })

    expect(summary.some(item => item.startsWith('Tester HP 3 -> 12'))).toBe(true)
    expect(summary).not.toContain('Tester HP 12')
  })

  it('summarizes defender interception from action result payloads', () => {
    expect(buildCombatStateChangeSummary({
      defender_interception: {
        defender_name: 'Shield Guard',
        protected_target_name: 'Cult Priest',
      },
      turn_state: { reaction_used: true },
    })).toEqual([
      '反应已用',
      'Shield Guard 护卫干扰：保护 Cult Priest，本次攻击劣势',
    ])
  })

  it('summarizes skirmisher reposition from ai turn payloads', () => {
    expect(buildCombatStateChangeSummary({
      skirmisher_reposition: {
        from: { x: 5, y: 2 },
        to: { x: 5, y: 0 },
        steps: 2,
      },
    })).toEqual([
      '游击撤步 10ft：5,2 -> 5,0',
    ])
  })

  it('explains reaction damage prevention and Cutting Words rules in state summaries', () => {
    expect(buildCombatStateChangeSummary({
      reaction_type: 'cutting_words_damage',
      reaction_effect: {
        cutting_words: { type: 'cutting_words', die: 'd8', roll: 3 },
        damage_roll_before: 8,
        damage_roll_after: 5,
        damage_prevented: 3,
        hp_restored: 3,
      },
      turn_state: { reaction_used: true },
    })).toEqual([
      'Cutting Words d8=3: damage 8 -> 5; prevented 3',
      '反应已用',
    ])
  })

  it('renders Cutting Words and contested grapple rules in combat log views', () => {
    const view = buildCombatLogView({
      role: 'player',
      log_type: 'combat',
      content: 'Lore Bard grapples the guard.',
      dice_result: {
        type: 'grapple',
        success: true,
        attacker_roll: { total: 18 },
        target_roll: { total: 17 },
        cutting_words: {
          type: 'cutting_words',
          die: 'd8',
          roll: 3,
          check_total_before: 20,
          check_total_after: 17,
          check_prevented: 3,
        },
      },
    })

    expect(view.sections.find(section => section.kind === 'rules')).toEqual({
      kind: 'rules',
      label: '规则',
      items: [
        'Grapple contest: attacker 18 vs target 17; success',
        'Cutting Words d8=3: check 20 -> 17; prevented 3',
      ],
    })
  })

  it('renders Cutting Words attack prevention from reaction dice payloads', () => {
    const view = buildCombatLogView({
      role: 'player',
      log_type: 'combat',
      content: 'Cutting Words ruins the attack.',
      dice_result: {
        type: 'reaction',
        reaction_type: 'cutting_words',
        cutting_words: { type: 'cutting_words', die: 'd8', roll: 6 },
        attack_total_before: 19,
        attack_total_after: 13,
        target_ac: 15,
        blocked_attack: true,
        damage_prevented: 8,
      },
    })

    expect(view.sections.find(section => section.kind === 'rules')?.items).toContain(
      'Cutting Words d8=6: attack 19 -> 13 vs AC15; hit blocked',
    )
  })

  it('summarizes multi-target result impacts without double-counting duplicated AoE payloads', () => {
    const targetResults = [
      {
        target_id: 'goblin-1',
        target_name: 'Goblin',
        is_enemy: true,
        damage: 12,
        new_hp: 0,
        save: { success: false },
      },
      {
        target_id: 'ally-1',
        target_name: 'Companion',
        is_enemy: false,
        damage: 6,
        new_hp: 8,
        save: { success: true },
      },
    ]

    expect(buildCombatResultImpactSummary({
      aoe_results: targetResults,
      target_results: targetResults,
    })).toEqual([
      { key: 'targets', label: '影响 2 个', tone: 'info', title: 'Goblin、Companion' },
      { key: 'enemies', label: '敌方 1', tone: 'good', title: 'Goblin' },
      { key: 'allies', label: '友方 1', tone: 'warning', title: 'Companion' },
      { key: 'damage', label: '总伤害 18', tone: 'bad', title: 'Goblin、Companion' },
      { key: 'save-failed', label: '豁免失败 1', tone: 'bad', title: 'Goblin、Companion' },
      { key: 'save-succeeded', label: '成功 1', tone: 'good', title: 'Goblin、Companion' },
      { key: 'downed', label: '倒下 1', tone: 'bad', title: 'Goblin' },
    ])
  })

  it('infers compact impact chips from multi-target HP state rows when result payloads are absent', () => {
    expect(buildCombatLogImpactSummary({
      state_changes: [
        'Goblin HP 12 -> 0',
        'Companion HP 14 -> 8',
        '动作已用',
      ],
    })).toEqual([
      {
        key: 'hp-updates',
        label: 'HP变化 2 项',
        tone: 'info',
        title: 'Goblin HP 12 -> 0；Companion HP 14 -> 8',
      },
      {
        key: 'downed',
        label: '倒下 1',
        tone: 'bad',
        title: 'Goblin HP 12 -> 0',
      },
    ])
  })
})
