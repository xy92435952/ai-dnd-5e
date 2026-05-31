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

  it('surfaces save DC and half-on-save resolution before casting', () => {
    const plan = buildSpellCastPlan({
      spell: {
        name: 'Burning Hands',
        level: 1,
        type: 'damage',
        damage: '3d6',
        save: 'dex',
        half_on_save: true,
        upcast_dice: '1d6',
      },
      level: 2,
      slots: { '2nd': 1 },
      playerId: 'hero-1',
      selectedTarget: 'enemy-1',
      combat: {
        entities: {
          'hero-1': { id: 'hero-1', derived: { spell_save_dc: 14 } },
          'enemy-1': { id: 'enemy-1', name: 'Goblin', is_enemy: true },
        },
      },
    })

    expect(row(plan, '判定').value).toBe('DEX save · DC 14 · success halves damage')
    expect(row(plan, '升环').value).toBe('+1 slot level · 1d6 per level')
  })

  it('surfaces spell attack bonus and concentration before casting', () => {
    const plan = buildSpellCastPlan({
      spell: {
        name: 'Guiding Bolt',
        level: 1,
        type: 'damage',
        damage: '4d6',
        concentration: true,
        desc: 'Make a ranged spell attack.',
      },
      level: 1,
      slots: { '1st': 1 },
      playerId: 'cleric-1',
      selectedTarget: 'enemy-1',
      combat: {
        entities: {
          'cleric-1': { id: 'cleric-1', derived: { spell_attack_bonus: 6 } },
          'enemy-1': { id: 'enemy-1', name: 'Skeleton', is_enemy: true },
        },
      },
    })

    expect(row(plan, '判定').value).toBe('Spell attack +6')
    expect(row(plan, '维持').value).toBe('Concentration; taking damage may force a check')
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
    expect(row(plan, '放置').value).toBe('预览中 · 中心 5, 5；点击格子可锁定')
    expect(plan.aoePlacement).toMatchObject({
      locked: false,
      canReset: false,
      label: '预览中 · 中心 5, 5；点击格子可锁定',
    })
    expect(row(plan, '命中单位').value).toBe('3 个：施法者、训练假人、同伴')
    expect(plan.aoeBreakdown).toMatchObject({
      total: 3,
      enemies: 1,
      allies: 1,
      self: 1,
      risk: 'friendly_fire',
    })
    expect(plan.aoeBreakdown.chips.map(chip => chip.label)).toEqual([
      'Enemies 1',
      'Allies 1',
      'Self',
      'Friendly fire',
    ])
  })

  it('shows directional anchors for cone and line style AoE spells', () => {
    const plan = buildSpellCastPlan({
      spell: {
        name: 'Burning Hands',
        level: 1,
        type: 'damage',
        aoe: true,
        damage: '3d6',
        desc: '15 尺锥形区域',
      },
      level: 1,
      slots: { '1st': 1 },
      playerId: 'hero-1',
      aoeHover: '5_8',
      combat: {
        entities: {
          'hero-1': { id: 'hero-1', name: 'Wizard', is_enemy: false, hp_current: 20 },
          'enemy-1': { id: 'enemy-1', name: 'Goblin', is_enemy: true, hp_current: 7 },
        },
        entity_positions: {
          'hero-1': { x: 5, y: 5 },
          'enemy-1': { x: 5, y: 6 },
        },
      },
    })

    expect(row(plan, '区域').value).toBe('锥形区域 · 15 尺 · 方向点 5, 8')
    expect(row(plan, '放置').value).toBe('预览中 · 方向点 5, 8；点击格子可锁定')
    expect(row(plan, '方向').value).toBe('南 · 从 Wizard 指向 5, 8')
  })

  it('shows AoE target caps and excluded candidates', () => {
    const plan = buildSpellCastPlan({
      spell: {
        name: 'Mass Healing Word',
        level: 3,
        type: 'heal',
        aoe: true,
        heal: '1d4',
        max_targets: 2,
        desc: '30 尺范围内最多 2 个队友恢复生命值',
      },
      level: 3,
      slots: { '3rd': 1 },
      playerId: 'hero-1',
      aoeHover: '5_5',
      combat: {
        entities: {
          'hero-1': { id: 'hero-1', name: 'Cleric', is_enemy: false, hp_current: 12 },
          'ally-1': { id: 'ally-1', name: 'Rogue', is_enemy: false, hp_current: 8 },
          'ally-2': { id: 'ally-2', name: 'Wizard', is_enemy: false, hp_current: 6 },
          'ally-3': { id: 'ally-3', name: 'Fighter', is_enemy: false, hp_current: 4 },
          'enemy-1': { id: 'enemy-1', name: 'Goblin', is_enemy: true, hp_current: 7 },
        },
        entity_positions: {
          'hero-1': { x: 5, y: 5 },
          'ally-1': { x: 6, y: 5 },
          'ally-2': { x: 4, y: 5 },
          'ally-3': { x: 5, y: 6 },
          'enemy-1': { x: 5, y: 4 },
        },
      },
    })

    expect(row(plan, '命中单位').value).toBe('2/2 个：Cleric、Rogue')
    expect(row(plan, '目标上限').value).toBe('最多 2 个；排除 Wizard、Fighter')
    expect(plan.aoeBreakdown).toMatchObject({
      limit: 2,
      excluded: 2,
    })
    expect(plan.aoeBreakdown.chips.map(chip => chip.label)).toContain('Limit 2/2')
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
