import { describe, expect, it } from 'vitest'
import { buildCombatLogView } from '../combatLog'
import { buildHazardDiceResult, formatHazardLog } from '../combatHazards'

describe('combatHazards', () => {
  const savedHazard = {
    triggered: true,
    target_id: 'char-1',
    target_name: 'Hero',
    label: 'sparking conduit',
    terrain: 'hazard',
    cell: '6_5',
    damage_dice: '2d6',
    damage_type: 'lightning',
    damage_roll: { notation: '2d6', rolls: [4, 4], total: 8 },
    rolled_damage: 8,
    damage: 4,
    final_damage: 4,
    hp_before: 10,
    hp_after: 6,
    saving_throw: {
      ability: 'dex',
      d20: 15,
      modifier: 2,
      total: 17,
      dc: 13,
      success: true,
    },
    save_success: true,
  }
  const turnStartHazard = {
    ...savedHazard,
    trigger: 'turn_start',
    target_name: 'Goblin',
    label: 'Sparking Conduit',
    damage: 8,
    final_damage: 8,
    hp_before: 12,
    hp_after: 4,
    saving_throw: {
      ability: 'dex',
      d20: 4,
      modifier: 1,
      total: 5,
      dc: 99,
      success: false,
    },
    save_success: false,
  }
  const immuneTurnStartHazard = {
    ...turnStartHazard,
    damage: 0,
    final_damage: 0,
    damage_after_save: 8,
    hp_after: 12,
    resistance_applied: true,
  }
  const resistantTurnStartHazard = {
    ...turnStartHazard,
    damage: 4,
    final_damage: 4,
    damage_after_save: 8,
    hp_after: 8,
    resistance_applied: true,
  }
  const vulnerableTurnStartHazard = {
    ...turnStartHazard,
    damage: 16,
    final_damage: 16,
    damage_after_save: 8,
    hp_after: 0,
    resistance_applied: true,
  }

  it('formats movement hazard logs with localized save and damage details', () => {
    expect(formatHazardLog(savedHazard)).toBe(
      'Hero 触发 sparking conduit，敏捷豁免 17 vs DC13 成功，受到 4 闪电伤害（HP 10→6）',
    )
  })

  it('builds combat-log dice payloads that expose hazard saves, damage dice, and final damage', () => {
    const dice = buildHazardDiceResult(savedHazard)

    expect(dice).toMatchObject({
      type: 'hazard',
      label: 'sparking conduit',
      cell: '6_5',
      damage: 8,
      total_damage: 4,
      damage_type: 'lightning',
      dc_source: expect.objectContaining({
        type: 'environment',
        label: 'sparking conduit',
        ability: 'dex',
        dc: 13,
        trigger: 'movement_hazard',
      }),
      saving_throw: expect.objectContaining({ ability: 'dex', total: 17, dc: 13, success: true }),
      target_state: expect.objectContaining({
        target_id: 'char-1',
        target_name: 'Hero',
        hp_after: 6,
      }),
    })

    const view = buildCombatLogView({
      role: 'system',
      log_type: 'combat',
      content: formatHazardLog(savedHazard),
      dice_result: dice,
    })

    expect(view.feedback).toEqual([{ kind: 'save-success', label: '豁免成功' }])
    expect(view.sections.find(section => section.kind === 'rules')).toEqual({
      kind: 'rules',
      label: '规则',
      items: ['环境DC · sparking conduit · 敏捷豁免 · DC13 · 进入触发'],
    })
    expect(view.sections.find(section => section.kind === 'dice')).toEqual({
      kind: 'dice',
      label: '骰子',
      items: [
        'Hero 敏捷豁免 d20 15 +2 = 17 vs DC13 → 成功',
        '伤害骰 2d6 = 8 闪电',
        '伤害 8',
        '实际伤害 4',
      ],
    })
  })

  it('labels start-of-turn hazard DC sources without falling back to enter-trigger copy', () => {
    const dice = buildHazardDiceResult(turnStartHazard)

    expect(dice).toMatchObject({
      type: 'hazard',
      trigger: 'turn_start_hazard',
      dc_source: expect.objectContaining({
        type: 'environment',
        label: 'Sparking Conduit',
        ability: 'dex',
        dc: 99,
        trigger: 'turn_start_hazard',
      }),
    })

    const liveView = buildCombatLogView({
      role: 'system',
      log_type: 'combat',
      content: formatHazardLog(turnStartHazard),
      dice_result: dice,
    })
    expect(liveView.sections.find(section => section.kind === 'rules')).toEqual({
      kind: 'rules',
      label: '规则',
      items: ['环境DC · Sparking Conduit · 敏捷豁免 · DC99 · 回合开始触发'],
    })

    const refreshedView = buildCombatLogView({
      role: 'system',
      log_type: 'combat',
      content: 'Goblin starts turn in Sparking Conduit.',
      dice_result: { hazard: turnStartHazard },
    })
    expect(refreshedView.sections.find(section => section.kind === 'rules')?.items).toContain(
      '环境DC · Sparking Conduit · 敏捷豁免 · DC99 · 回合开始触发',
    )
  })

  it('explains hazard damage immunity when final damage is reduced to zero', () => {
    const view = buildCombatLogView({
      role: 'system',
      log_type: 'combat',
      content: formatHazardLog(immuneTurnStartHazard),
      dice_result: { hazard: immuneTurnStartHazard },
    })

    expect(view.sections.find(section => section.kind === 'rules')?.items).toEqual([
      '闪电免疫伤害 · 闪电 · 8 -> 0',
      '环境DC · Sparking Conduit · 敏捷豁免 · DC99 · 回合开始触发',
    ])
    expect(view.sections.find(section => section.kind === 'dice')?.items).toEqual([
      'Goblin 敏捷豁免 d20 4 +1 = 5 vs DC99 → 失败',
      '伤害骰 2d6 = 8 闪电',
      '伤害 8',
      '实际伤害 0',
    ])
  })

  it('explains hazard damage resistance when final damage is reduced', () => {
    const view = buildCombatLogView({
      role: 'system',
      log_type: 'combat',
      content: formatHazardLog(resistantTurnStartHazard),
      dice_result: { hazard: resistantTurnStartHazard },
    })

    expect(view.sections.find(section => section.kind === 'rules')?.items).toEqual([
      '闪电抗性减伤 · 闪电 · 8 -> 4',
      '环境DC · Sparking Conduit · 敏捷豁免 · DC99 · 回合开始触发',
    ])
  })

  it('explains hazard damage vulnerability when final damage is increased', () => {
    const view = buildCombatLogView({
      role: 'system',
      log_type: 'combat',
      content: formatHazardLog(vulnerableTurnStartHazard),
      dice_result: { hazard: vulnerableTurnStartHazard },
    })

    expect(view.sections.find(section => section.kind === 'rules')?.items).toEqual([
      '闪电易伤增伤 · 闪电 · 8 -> 16',
      '环境DC · Sparking Conduit · 敏捷豁免 · DC99 · 回合开始触发',
    ])
  })
})
