import { describe, expect, it } from 'vitest'
import { buildSpellCastPlan } from '../spellCastPlan'

function row(plan, label) {
  return plan.rows.find(item => item.label === label)
}

function preflight(plan, key) {
  return plan.preflight.find(item => item.key === key)
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
          'enemy-1': {
            id: 'enemy-1',
            name: '训练假人',
            is_enemy: true,
            hp_current: 7,
            conditions: ['restrained'],
            condition_durations: { restrained: 2 },
          },
        },
      },
    })

    expect(plan.tone).toBe('ready')
    expect(plan.status).toBe('可施放')
    expect(preflight(plan, 'status')).toMatchObject({ value: '可施放', tone: 'ready' })
    expect(preflight(plan, 'cost')).toMatchObject({ value: '1 环 · 2 -> 1', tone: 'ready' })
    expect(preflight(plan, 'target')).toMatchObject({ value: '训练假人', tone: 'ready' })
    expect(row(plan, '消耗').value).toBe('1 环法术位（剩余 2 -> 1）')
    expect(row(plan, '效果').value).toBe('伤害 1d4+1')
    expect(row(plan, '目标').value).toBe('训练假人')
    expect(row(plan, '状态').value).toBe('可施放')
    expect(plan.targetImpactChips.map(chip => chip.label)).toEqual([
      '速度 0',
      '受击优势',
      '攻击劣势',
      '敏捷劣势',
    ])
    expect(plan.targetImpactChips[0]).toMatchObject({
      key: 'condition-speed_0',
      tone: 'bad',
      title: '移动速度降为 0。 来源：束缚 (2轮)。',
    })
  })

  it('summarizes cantrips as no-slot casts', () => {
    const plan = buildSpellCastPlan({
      spell: { name: '火焰射线', name_en: 'Fire Bolt', level: 0, type: 'damage', damage: '1d10' },
      cantrips: ['Fire Bolt'],
      selectedTarget: 'enemy-1',
      combat: { entities: { 'enemy-1': { id: 'enemy-1', name: '训练假人' } } },
    })

    expect(row(plan, '消耗').value).toBe('戏法，无需法术位')
    expect(preflight(plan, 'cost')).toMatchObject({ value: '戏法', tone: 'ready' })
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
          'enemy-1': {
            id: 'enemy-1',
            name: 'Goblin',
            is_enemy: true,
            derived: { saving_throws: { dex: 5 } },
          },
        },
      },
    })

    expect(row(plan, '判定').value).toBe('敏捷豁免 · DC 14 · 成功减半')
    expect(preflight(plan, 'rule')).toMatchObject({
      label: '判定',
      value: '敏捷豁免 · DC 14 · 9+ · 60%通过 · 成功减半',
      tone: 'warning',
    })
    expect(row(plan, '目标豁免')).toMatchObject({
      value: '敏捷豁免 +5 · d20 需 9+ · 约 60%通过',
      tone: 'warning',
    })
    expect(row(plan, '升环').value).toBe('+1 环 · 每环 1d6')
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
          'enemy-1': { id: 'enemy-1', name: 'Skeleton', is_enemy: true, ac: 15 },
        },
      },
    })

    expect(row(plan, '判定').value).toBe('法术攻击 +6')
    expect(preflight(plan, 'rule')).toMatchObject({
      label: '判定',
      value: '法攻 +6 · AC 15 · 9+ · 60%',
      tone: 'ready',
    })
    expect(row(plan, '目标防御').value).toBe('AC 15 · d20 需 9+ · 约 60%')
    expect(row(plan, '维持').value).toBe('专注；受到伤害可能触发专注检定')
  })

  it('bounds spell attack estimates by natural 1 and natural 20', () => {
    const easy = buildSpellCastPlan({
      spell: { name: 'Fire Bolt', level: 0, type: 'damage', desc: 'Make a ranged spell attack.' },
      cantrips: ['Fire Bolt'],
      playerId: 'wizard-1',
      selectedTarget: 'ooze-1',
      combat: {
        entities: {
          'wizard-1': { id: 'wizard-1', derived: { spell_attack_bonus: 10 } },
          'ooze-1': { id: 'ooze-1', name: 'Ooze', is_enemy: true, ac: 5 },
        },
      },
    })
    const hard = buildSpellCastPlan({
      spell: { name: 'Fire Bolt', level: 0, type: 'damage', desc: 'Make a ranged spell attack.' },
      cantrips: ['Fire Bolt'],
      playerId: 'wizard-1',
      selectedTarget: 'shielded-1',
      combat: {
        entities: {
          'wizard-1': { id: 'wizard-1', derived: { spell_attack_bonus: 5 } },
          'shielded-1': { id: 'shielded-1', name: 'Shielded Knight', is_enemy: true, ac: 30 },
        },
      },
    })

    expect(row(easy, '目标防御').value).toBe('AC 5 · d20 需 2+ · 约 95%')
    expect(row(hard, '目标防御').value).toBe('AC 30 · d20 需 自然20 · 约 5%')
  })

  it('summarizes AoE center and affected living units', () => {
    const plan = buildSpellCastPlan({
      spell: {
        name: '火球术',
        level: 3,
        type: 'damage',
        aoe: true,
        damage: '8d6',
        save: 'dex',
        half_on_save: true,
        desc: '20尺半径球形爆炸',
      },
      level: 3,
      slots: { '3rd': 1 },
      playerId: 'hero-1',
      aoeHover: '5_5',
      combat: {
        entities: {
          'hero-1': {
            id: 'hero-1',
            name: '施法者',
            is_enemy: false,
            hp_current: 20,
            derived: { spell_save_dc: 14, saving_throws: { dex: 2 } },
          },
          'enemy-1': {
            id: 'enemy-1',
            name: '训练假人',
            is_enemy: true,
            hp_current: 7,
            derived: { saving_throws: { dex: 5 } },
          },
          'ally-1': {
            id: 'ally-1',
            name: '同伴',
            is_enemy: false,
            hp_current: 10,
            derived: { saving_throws: { dex: -1 } },
          },
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
    expect(preflight(plan, 'placement')).toMatchObject({
      label: '落点',
      value: '预览中 · 中心 5, 5；点击格子可锁定',
      tone: 'ready',
    })
    expect(row(plan, '命中单位').value).toBe('3 个：施法者、训练假人、同伴')
    expect(row(plan, '目标豁免')).toMatchObject({
      value: '3 个目标 · 平均 45%通过 · 最高 60% / 最低 30%',
      tone: 'warning',
    })
    expect(preflight(plan, 'rule')).toMatchObject({
      value: '敏捷豁免 · DC 14 · 均 45%通过 · 成功减半',
      tone: 'warning',
    })
    expect(row(plan, '敌方')).toMatchObject({ value: '训练假人', tone: 'ready' })
    expect(row(plan, '友方')).toMatchObject({ value: '同伴', tone: 'warning' })
    expect(row(plan, '自身')).toMatchObject({ value: '施法者', tone: 'warning' })
    expect(plan.aoeBreakdown).toMatchObject({
      total: 3,
      enemies: 1,
      allies: 1,
      self: 1,
      risk: 'friendly_fire',
    })
    expect(plan.aoeBreakdown.chips.map(chip => chip.label)).toEqual([
      '敌方 1',
      '友方 1',
      '自身',
      '误伤风险',
    ])
    expect(plan.warnings).toEqual([
      {
        key: 'friendly-fire',
        label: '误伤',
        detail: '伤害范围包含友方或施法者：同伴、施法者',
        tone: 'warning',
      },
    ])
    expect(preflight(plan, 'target')).toMatchObject({
      value: '影响 3 个：敌方 1 / 友方 1 / 自身',
      tone: 'warning',
    })
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
    expect(preflight(plan, 'placement')).toMatchObject({
      value: '预览中 · 方向点 5, 8；点击格子可锁定',
      tone: 'ready',
    })
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
    expect(row(plan, '友方')).toMatchObject({ value: 'Rogue', tone: 'ready' })
    expect(row(plan, '自身')).toMatchObject({ value: 'Cleric', tone: 'ready' })
    expect(row(plan, '目标上限').value).toBe('最多 2 个；排除 Wizard、Fighter')
    expect(plan.aoeBreakdown).toMatchObject({
      limit: 2,
      excluded: 2,
    })
    expect(plan.aoeBreakdown.chips.map(chip => chip.label)).toContain('上限 2/2')
    expect(plan.warnings).toEqual([
      {
        key: 'target-limit',
        label: '上限',
        detail: '超过目标上限，Wizard、Fighter 不会结算。',
        tone: 'warning',
      },
    ])
    expect(preflight(plan, 'target')).toMatchObject({
      value: '影响 2/2 个：友方 1 / 自身',
      tone: 'ready',
    })
  })

  it('warns when an AoE placement has no valid targets', () => {
    const plan = buildSpellCastPlan({
      spell: {
        name: 'Fireball',
        level: 3,
        type: 'damage',
        aoe: true,
        damage: '8d6',
      },
      level: 3,
      slots: { '3rd': 1 },
      playerId: 'hero-1',
      aoeHover: '9_9',
      combat: {
        entities: {
          'hero-1': { id: 'hero-1', name: 'Wizard', is_enemy: false, hp_current: 20 },
          'enemy-1': { id: 'enemy-1', name: 'Goblin', is_enemy: true, hp_current: 7 },
        },
        entity_positions: {
          'hero-1': { x: 1, y: 1 },
          'enemy-1': { x: 1, y: 2 },
        },
      },
    })

    expect(row(plan, '命中单位')).toMatchObject({ value: '0 个', tone: 'warning' })
    expect(plan.warnings).toEqual([
      {
        key: 'empty',
        label: '空范围',
        detail: '当前范围内没有可结算目标。',
        tone: 'warning',
      },
    ])
  })

  it('warns in preflight when an AoE placement is not selected', () => {
    const plan = buildSpellCastPlan({
      spell: {
        name: 'Fireball',
        level: 3,
        type: 'damage',
        aoe: true,
        damage: '8d6',
      },
      level: 3,
      slots: { '3rd': 1 },
      playerId: 'hero-1',
      aoeHover: null,
      combat: {
        entities: {
          'hero-1': { id: 'hero-1', name: 'Wizard', is_enemy: false, hp_current: 20 },
          'enemy-1': { id: 'enemy-1', name: 'Goblin', is_enemy: true, hp_current: 7 },
        },
        entity_positions: {
          'hero-1': { x: 1, y: 1 },
          'enemy-1': { x: 1, y: 2 },
        },
      },
    })

    expect(row(plan, '放置')).toMatchObject({ value: '待确认', tone: 'warning' })
    expect(preflight(plan, 'placement')).toMatchObject({
      label: '落点',
      value: '待确认',
      tone: 'warning',
    })
    expect(preflight(plan, 'target')).toMatchObject({
      value: '待确认落点',
      tone: 'warning',
    })
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
    expect(preflight(plan, 'status')).toMatchObject({
      value: '请选择队友或自己作为法术目标',
      tone: 'blocked',
    })
    expect(row(plan, '状态').value).toBe('请选择队友或自己作为法术目标')
  })
})
