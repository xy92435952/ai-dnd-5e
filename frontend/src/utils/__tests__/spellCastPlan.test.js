import { describe, expect, it } from 'vitest'
import { buildSpellCastPlan } from '../spellCastPlan'

function row(plan, label) {
  return plan.rows.find(item => item.label === label)
}

describe('buildSpellCastPlan', () => {
  it('summarizes selected single-target spell cost, effect, target, and status', () => {
    const plan = buildSpellCastPlan({
      spell: {
        name: '魔法飞弹',
        level: 1,
        type: 'damage',
        damage: '1d4+1',
        target_type: 'enemy',
      },
      level: 1,
      slots: { '1st': 2 },
      selectedTarget: 'enemy-1',
      combat: {
        entities: {
          'enemy-1': { id: 'enemy-1', name: '训练假人', is_enemy: true, hp_current: 7 },
        },
      },
    })

    expect(plan.tone).toBe('ready')
    expect(plan.status).toBe('可施放')
    expect(row(plan, '消耗').value).toBe('1 环法术位（剩余 2）')
    expect(row(plan, '效果').value).toBe('伤害 1d4+1')
    expect(row(plan, '目标').value).toBe('训练假人')
    expect(row(plan, '状态').value).toBe('可施放')
  })

  it('summarizes cantrips as no-slot casts', () => {
    const plan = buildSpellCastPlan({
      spell: { name: '火焰射线', name_en: 'Fire Bolt', level: 0, type: 'damage', damage: '1d10' },
      cantrips: ['Fire Bolt'],
      selectedTarget: 'enemy-1',
      combat: { entities: { 'enemy-1': { id: 'enemy-1', name: '训练假人' } } },
    })

    expect(row(plan, '消耗').value).toBe('戏法，无需法术位')
  })

  it('summarizes AoE center and affected living units', () => {
    const plan = buildSpellCastPlan({
      spell: {
        name: '火球术',
        level: 3,
        type: 'damage',
        aoe: true,
        damage: '8d6',
        desc: '20尺半径球形爆炸',
      },
      level: 3,
      slots: { '3rd': 1 },
      playerId: 'hero-1',
      aoeHover: '5_5',
      combat: {
        entities: {
          'hero-1': { id: 'hero-1', name: '施法者', is_enemy: false, hp_current: 20 },
          'enemy-1': { id: 'enemy-1', name: '训练假人', is_enemy: true, hp_current: 7 },
          'ally-1': { id: 'ally-1', name: '同伴', is_enemy: false, hp_current: 10 },
          'down-1': { id: 'down-1', name: '倒地单位', is_enemy: true, hp_current: 0 },
        },
        entity_positions: {
          'hero-1': { x: 5, y: 5 },
          'enemy-1': { x: 6, y: 5 },
          'ally-1': { x: 4, y: 5 },
          'down-1': { x: 5, y: 6 },
        },
      },
    })

    expect(row(plan, '区域').value).toBe('球形区域 · 20 尺 · 中心 5, 5')
    expect(row(plan, '命中单位').value).toBe('3 个：施法者、训练假人、同伴')
  })

  it('marks blocked casts with the player-facing reason', () => {
    const plan = buildSpellCastPlan({
      spell: { name: 'Cure Wounds', level: 1, type: 'heal', heal: '1d8', target_type: 'ally' },
      level: 1,
      slots: { '1st': 1 },
      selectedTarget: 'enemy-1',
      combat: { entities: { 'enemy-1': { id: 'enemy-1', name: '训练假人', is_enemy: true } } },
      disabledReason: '请选择队友或自己作为法术目标',
    })

    expect(plan.tone).toBe('blocked')
    expect(plan.status).toBe('无法施放')
    expect(row(plan, '状态').value).toBe('请选择队友或自己作为法术目标')
  })
})
