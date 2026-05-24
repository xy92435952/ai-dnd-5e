import { describe, it, expect } from 'vitest'
import {
  applyAoeHpUpdates,
  applyPlayerHpUpdate,
  buildAoeCells,
  buildCombatGrid,
  buildGridTerrainSets,
  buildInitiativeChips,
  buildThreatCells,
  canActInCombatTurn,
  getAoePreviewCenterKey,
  getCombatPredictionActionKey,
  getCameraWindow,
  getCombatSkillBar,
  getCurrentTurnLabel,
  getPlayerAvailableSpells,
  getPlayerTurnState,
  isMyCombatTurn,
  isPlayerCombatTurn,
  getSpriteKind,
  parseDiceNotation,
} from '../combat'
import { DEFAULT_SKILL_BAR } from '../../data/combat'


describe('combat grid helpers', () => {
  const positions = {
    player: { x: 2, y: 2 },
    enemy1: { x: 3, y: 3 },
    enemy2: { x: 8, y: 8 },
    ally: { x: 4, y: 4 },
  }
  const entities = {
    player: { id: 'player', is_enemy: false, char_class: 'Paladin' },
    enemy1: { id: 'enemy1', is_enemy: true, hp_current: 7 },
    enemy2: { id: 'enemy2', is_enemy: true, hp_current: 0 },
    ally: { id: 'ally', is_enemy: false, hp_current: 5 },
  }

  it('buildThreatCells 标记存活敌人的相邻八格，忽略死亡敌人', () => {
    const cells = buildThreatCells({ showThreat: true, entityPositions: positions, entities })

    expect(cells.has('2_2')).toBe(true)
    expect(cells.has('3_3')).toBe(false)
    expect(cells.has('7_7')).toBe(false)
  })

  it('buildThreatCells 在 showThreat 关闭时返回空集合', () => {
    expect(buildThreatCells({ showThreat: false, entityPositions: positions, entities }).size).toBe(0)
  })

  it('buildAoeCells 以 hover 格为中心按半径生成圆形格集合', () => {
    const cells = buildAoeCells({ aoePreview: { radius: 1 }, aoeHover: '5_5' })

    expect(cells.center).toBe('5_5')
    expect(cells.ring.has('5_5')).toBe(true)
    expect(cells.ring.has('6_5')).toBe(true)
    expect(cells.ring.has('7_5')).toBe(false)
  })

  it('getAoePreviewCenterKey 优先以选中目标为中心，否则回退玩家位置', () => {
    expect(getAoePreviewCenterKey({
      selectedTarget: 'enemy1',
      entityPositions: { enemy1: { x: 7, y: 4 } },
      playerPos: { x: 2, y: 2 },
    })).toBe('7_4')

    expect(getAoePreviewCenterKey({
      selectedTarget: 'missing',
      entityPositions: {},
      playerPos: { x: 2, y: 2 },
    })).toBe('2_2')
  })

  it('buildCombatGrid 生成固定尺寸格子并挂载实体', () => {
    const grid = buildCombatGrid({ rows: 3, cols: 4, entityPositions: positions, entities })

    expect(grid).toHaveLength(3)
    expect(grid[0]).toHaveLength(4)
    expect(grid[2][2]).toMatchObject({ x: 2, y: 2, entityId: 'player', entity: entities.player })
  })

  it('getCameraWindow 以玩家为中心并限制在地图边界内', () => {
    expect(getCameraWindow({ playerPos: { x: 10, y: 6 }, totalWidth: 20, totalHeight: 12, viewWidth: 12, viewHeight: 8 }))
      .toEqual({ x0: 4, y0: 2 })
    expect(getCameraWindow({ playerPos: { x: 1, y: 1 }, totalWidth: 20, totalHeight: 12, viewWidth: 12, viewHeight: 8 }))
      .toEqual({ x0: 0, y0: 0 })
    expect(getCameraWindow({ playerPos: { x: 19, y: 11 }, totalWidth: 20, totalHeight: 12, viewWidth: 12, viewHeight: 8 }))
      .toEqual({ x0: 8, y0: 4 })
  })

  it('buildGridTerrainSets 分出墙和危险地形', () => {
    const { walls, hazards } = buildGridTerrainSets({
      '1_1': 'wall',
      '2_2': 'hazard',
      '3_3': 'difficult',
      '4_4': 'floor',
    })

    expect(walls.has('1_1')).toBe(true)
    expect(hazards.has('2_2')).toBe(true)
    expect(hazards.has('3_3')).toBe(true)
    expect(hazards.has('4_4')).toBe(false)
  })

  it('getSpriteKind 优先使用 sprite 字段，其次敌人和职业兜底', () => {
    expect(getSpriteKind({ sprite: 'lich', is_enemy: true })).toBe('lich')
    expect(getSpriteKind({ is_enemy: true })).toBe('cultist')
    expect(getSpriteKind({ char_class: 'Wizard' })).toBe('wizard')
    expect(getSpriteKind(null)).toBe('paladin')
  })

  it('buildInitiativeChips 为先攻条派生血量、当前回合和死亡状态', () => {
    const chips = buildInitiativeChips({
      turnOrder: [
        { character_id: 'player', name: 'Hero', initiative: 18 },
        { character_id: 'enemy1', name: 'Goblin', initiative: 7, is_enemy: true },
        { character_id: 'enemy2', name: 'Skeleton', initiative: 3, is_enemy: true },
      ],
      currentTurnIndex: 1,
      entities: {
        player: { hp_current: 10, hp_max: 20 },
        enemy1: { hp_current: 2, hp_max: 10 },
        enemy2: { hp_current: 0, hp_max: 8 },
      },
    })

    expect(chips[0]).toMatchObject({ pct: 50, isCur: false, dead: false, low: false })
    expect(chips[1]).toMatchObject({ pct: 20, isCur: true, dead: false, low: true })
    expect(chips[2]).toMatchObject({ pct: 0, isCur: false, dead: true, low: true })
  })

  it('getPlayerAvailableSpells 优先使用已知法术/戏法列表', () => {
    const spells = [
      { name: 'Magic Missile', classes: ['Wizard'] },
      { name: 'Fire Bolt', classes: ['Wizard', 'Sorcerer'] },
      { name: 'Cure Wounds', classes: ['Cleric'] },
    ]

    expect(getPlayerAvailableSpells({
      spells,
      knownSpells: ['Magic Missile'],
      cantrips: ['Fire Bolt'],
      playerClass: 'Cleric',
    }).map(s => s.name)).toEqual(['Magic Missile', 'Fire Bolt'])
  })

  it('getPlayerAvailableSpells 没有已知列表时按中英文职业过滤', () => {
    const spells = [
      { name: 'Bless', classes: ['Cleric', 'Paladin'] },
      { name: 'Shield', classes: ['Wizard', 'Sorcerer'] },
      { name: 'Cure Wounds', classes: ['Cleric'] },
    ]

    expect(getPlayerAvailableSpells({ spells, playerClass: '牧师' }).map(s => s.name))
      .toEqual(['Bless', 'Cure Wounds'])
    expect(getPlayerAvailableSpells({ spells, playerClass: 'Wizard' }).map(s => s.name))
      .toEqual(['Shield'])
  })

  it('getCombatSkillBar 使用后端技能栏，空值时回退默认本地技能栏', () => {
    const serverBar = [{ k: 'custom', label: '自定义', available: true }]

    expect(getCombatSkillBar(serverBar)).toBe(serverBar)
    expect(getCombatSkillBar([])).toBe(DEFAULT_SKILL_BAR)
    expect(getCombatSkillBar(null)).toBe(DEFAULT_SKILL_BAR)
  })

  it('parseDiceNotation 解析 NdM 掷骰表达式并支持默认值', () => {
    expect(parseDiceNotation('2d6')).toEqual({ count: 2, faces: 6 })
    expect(parseDiceNotation('d8')).toEqual({ count: 1, faces: 8 })
    expect(parseDiceNotation('', { defaultCount: 3, defaultFaces: 4 })).toEqual({ count: 3, faces: 4 })
  })

  it('applyAoeHpUpdates 不可变地批量应用 AoE HP 结果', () => {
    const combat = {
      entities: {
        a: { hp_current: 10 },
        b: { hp_current: 8 },
        c: { hp_current: 6 },
      },
    }

    const updated = applyAoeHpUpdates(combat, [
      { target_id: 'a', new_hp: 5 },
      { target_id: 'b', hp: -2 },
      { target_id: 'missing', new_hp: 1 },
    ])

    expect(updated).not.toBe(combat)
    expect(updated.entities.a.hp_current).toBe(5)
    expect(updated.entities.b.hp_current).toBe(0)
    expect(updated.entities.c).toBe(combat.entities.c)
  })

  it('isPlayerCombatTurn 识别当前回合是否为玩家', () => {
    expect(isPlayerCombatTurn({
      current_turn_index: 1,
      turn_order: [{ is_player: false }, { is_player: true }],
    })).toBe(true)
    expect(isPlayerCombatTurn(null)).toBe(false)
  })

  it('getPlayerTurnState 从 combat.turn_states 中取当前玩家状态', () => {
    const state = { action_used: false }
    expect(getPlayerTurnState({ turn_states: { p1: state } }, 'p1')).toBe(state)
    expect(getPlayerTurnState({ turn_states: {} }, 'p1')).toBeNull()
  })

  it('getCombatPredictionActionKey 按职业推导预测动作', () => {
    expect(getCombatPredictionActionKey('Paladin')).toBe('smite')
    expect(getCombatPredictionActionKey('游荡者')).toBe('sneak')
    expect(getCombatPredictionActionKey('法师')).toBe('firebolt')
    expect(getCombatPredictionActionKey('牧师')).toBe('sacred_flame')
    expect(getCombatPredictionActionKey('Fighter')).toBe('atk')
  })

  it('多人回合 helper 生成当前回合标签并判断是否轮到我', () => {
    const combat = {
      current_turn_index: 0,
      turn_order: [{ character_id: 'c1', name: 'AliceHero' }],
    }
    const room = {
      members: [{ character_id: 'c1', display_name: 'Alice' }],
    }

    expect(isMyCombatTurn({ room, combat, myCharacterId: 'c1' })).toBe(true)
    expect(isMyCombatTurn({ room, combat, myCharacterId: 'c2' })).toBe(false)
    expect(isMyCombatTurn({ room: null, combat, myCharacterId: null })).toBe(true)
    expect(canActInCombatTurn({ room, combat, myCharacterId: 'c1' })).toBe(true)
    expect(canActInCombatTurn({ room, combat, myCharacterId: 'c2' })).toBe(false)
    expect(canActInCombatTurn({
      room: null,
      combat: { ...combat, turn_order: [{ ...combat.turn_order[0], is_player: true }] },
      myCharacterId: null,
    })).toBe(true)
    expect(getCurrentTurnLabel({ room, combat })).toBe('当前回合：Alice（AliceHero）')
    expect(getCurrentTurnLabel({ room, combat: { ...combat, turn_order: [{ character_id: 'bot', name: 'Enemy' }] } }))
      .toBe('当前回合：Enemy（AI 托管）')
  })

  it('applyPlayerHpUpdate 只更新指定玩家 HP', () => {
    const combat = {
      entities: {
        p1: { hp_current: 4 },
        p2: { hp_current: 7 },
      },
    }

    const updated = applyPlayerHpUpdate(combat, 'p1', 12)
    expect(updated).not.toBe(combat)
    expect(updated.entities.p1.hp_current).toBe(12)
    expect(updated.entities.p2).toBe(combat.entities.p2)
  })
})
