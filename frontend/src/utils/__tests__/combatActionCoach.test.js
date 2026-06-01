import { describe, expect, it } from 'vitest'
import { buildCombatActionCoach } from '../combatActionCoach'

describe('buildCombatActionCoach', () => {
  it('stays hidden outside actionable player turns', () => {
    expect(buildCombatActionCoach({ isPlayerTurn: false })).toEqual({ visible: false, items: [] })
    expect(buildCombatActionCoach({ isPlayerTurn: true, syncBlocked: true })).toEqual({ visible: false, items: [] })
    expect(buildCombatActionCoach({ isPlayerTurn: true, isProcessing: true })).toEqual({ visible: false, items: [] })
  })

  it('prompts for a target before target-based actions', () => {
    const coach = buildCombatActionCoach({
      isPlayerTurn: true,
      turnState: { action_used: false, movement_max: 6, movement_used: 2, reaction_used: false },
      skillBar: [{ k: 'atk', kind: 'attack', available: true }],
      selectedTarget: null,
    })

    expect(coach.visible).toBe(true)
    expect(coach.items).toContainEqual({ key: 'action', label: '动作', value: '选目标', tone: 'warn' })
    expect(coach.items).toContainEqual({ key: 'target', label: '目标', value: '选目标', tone: 'warn' })
    expect(coach.items).toContainEqual({ key: 'move', label: '移动', value: '4 格', tone: 'ready' })
    expect(coach.items).toContainEqual({ key: 'reaction', label: '反应', value: '保留', tone: 'ready' })
  })

  it('summarizes the selected target with AC, hit chance, and attack rules', () => {
    const coach = buildCombatActionCoach({
      isPlayerTurn: true,
      turnState: { action_used: false, movement_max: 6, movement_used: 0, reaction_used: false },
      skillBar: [{ k: 'atk', kind: 'attack', available: true }],
      selectedTarget: 'enemy-1',
      selectedTargetEntity: { id: 'enemy-1', name: 'Goblin Boss', is_enemy: true, hp_current: 7, hp_max: 30, ac: 15 },
      prediction: {
        hit_rate: 0.55,
        disadvantage: true,
        target_ac: 15,
        effective_target_ac: 20,
        cover_bonus: 5,
        cover_detail: { bonus: 5, raw_bonus: 5 },
        disadvantage_sources: ['attacker poisoned', 'target invisible'],
      },
    })

    expect(coach.items).toContainEqual({
      key: 'target',
      label: '目标',
      value: '敌人 · Goblin Boss · 危急 · AC 15 · 命中 55% · 劣势 · 3/4 掩护 +5 AC · 有效 AC 20',
      tone: 'ready',
    })
    expect(coach.items).toContainEqual({
      key: 'rules',
      label: '来源',
      value: '攻击者中毒 / 目标隐形',
      tone: 'warn',
    })
    expect(coach.items).toContainEqual({ key: 'action', label: '动作', value: '可用', tone: 'ready' })
  })

  it('marks advantage-only rule sources as ready guidance', () => {
    const coach = buildCombatActionCoach({
      isPlayerTurn: true,
      turnState: { action_used: false, movement_max: 6, movement_used: 0, reaction_used: false },
      skillBar: [{ k: 'atk', kind: 'attack', available: true }],
      selectedTarget: 'enemy-1',
      selectedTargetEntity: { id: 'enemy-1', name: 'Goblin Boss', is_enemy: true, ac: 15 },
      prediction: {
        hit_rate: 0.8,
        advantage: true,
        advantage_sources: ['target restrained'],
      },
    })

    expect(coach.items).toContainEqual({
      key: 'rules',
      label: '来源',
      value: '目标束缚',
      tone: 'ready',
    })
  })

  it('marks allied selected targets in the target summary', () => {
    const coach = buildCombatActionCoach({
      isPlayerTurn: true,
      turnState: { action_used: false, movement_max: 6, movement_used: 0, reaction_used: false },
      skillBar: [{ k: 'heal', kind: 'spell', available: true }],
      selectedTarget: 'ally-1',
      selectedTargetEntity: { id: 'ally-1', name: 'Asha', is_enemy: false, hp_current: 8, hp_max: 20, ac: 14 },
    })

    expect(coach.items).toContainEqual({
      key: 'target',
      label: '目标',
      value: '友军 · Asha · 受伤 · AC 14',
      tone: 'ready',
    })
  })

  it('summarizes spent action resources and bonus availability', () => {
    const coach = buildCombatActionCoach({
      isPlayerTurn: true,
      turnState: {
        action_used: true,
        bonus_action_used: false,
        reaction_used: true,
        movement_max: 6,
        movement_used: 6,
      },
      skillBar: [{ k: 'off_attack', kind: 'bonus', available: true }],
      selectedTarget: 'enemy-1',
    })

    expect(coach.items).toContainEqual({ key: 'action', label: '动作', value: '已用', tone: 'spent' })
    expect(coach.items).toContainEqual({ key: 'bonus', label: '附赠', value: '可用', tone: 'ready' })
    expect(coach.items).toContainEqual({ key: 'move', label: '移动', value: '0 格', tone: 'spent' })
    expect(coach.items).toContainEqual({ key: 'reaction', label: '反应', value: '已用', tone: 'spent' })
  })

  it('surfaces Help mode as an allied-target prompt', () => {
    const coach = buildCombatActionCoach({
      isPlayerTurn: true,
      helpMode: true,
      turnState: {
        action_used: false,
        bonus_action_used: false,
        reaction_used: false,
        movement_max: 6,
        movement_used: 1,
      },
      skillBar: [{ k: 'help', label: '协助', kind: 'action', available: true }],
    })

    expect(coach.items).toContainEqual({ key: 'action', label: '动作', value: '选队友', tone: 'warn' })
    expect(coach.items).toContainEqual({ key: 'assist', label: '协助', value: '选队友', tone: 'warn' })
    expect(coach.items).toContainEqual({ key: 'move', label: '移动', value: '5 格', tone: 'ready' })
  })

  it('summarizes attack mode and selected weapon', () => {
    const coach = buildCombatActionCoach({
      isPlayerTurn: true,
      isRanged: true,
      selectedWeaponName: 'Longbow',
      turnState: {
        action_used: false,
        bonus_action_used: false,
        reaction_used: false,
        movement_max: 6,
        movement_used: 0,
      },
      skillBar: [{ k: 'atk', label: '攻击', kind: 'attack', available: true }],
    })

    expect(coach.items).toContainEqual({ key: 'mode', label: '方式', value: '远程 · Longbow', tone: 'ready' })
  })
})
