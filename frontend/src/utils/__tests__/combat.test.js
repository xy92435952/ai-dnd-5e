import { describe, it, expect } from 'vitest'
import {
  applyActionResultEntityStates,
  applyAoeHpUpdates,
  applyEntityStateUpdate,
  applyPlayerHpUpdate,
  applyWeaponResourceToCombat,
  buildAoeCells,
  buildSpellAoePreview,
  buildCombatPreviewRows,
  buildCombatGrid,
  buildGridTerrainSets,
  buildInitiativeChips,
  buildThreatCells,
  canActInCombatTurn,
  collectSpellCastTargetIds,
  computeSkillStats,
  canDriveAiCombatTurns,
  formatWeaponResourceLog,
  getSpellCastDisabledReason,
  getSpellMaxTargets,
  getAoePreviewCenterKey,
  getAoeTemplateType,
  getAiCombatTurnDriverUserId,
  getCombatPredictionActionKey,
  getCombatTurnToken,
  getCameraWindow,
  getCombatSkillBar,
  getCombatLifeState,
  getCurrentTurnLabel,
  getEquippedWeaponResourceSummary,
  getMagicInitiateSpellCastInfo,
  getSkillUnavailableReason,
  getPlayerAvailableSpells,
  getPlayerTurnState,
  isMyCombatTurn,
  isCombatEntityDead,
  isPlayerCombatTurn,
  getSpriteKind,
  parseDiceNotation,
  spellNameMatches,
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
    expect(cells.template).toBe('sphere')
    expect(cells.ring.has('5_5')).toBe(true)
    expect(cells.ring.has('6_5')).toBe(true)
    expect(cells.ring.has('7_5')).toBe(false)
  })

  it('buildAoeCells supports cone, line, cube and aura templates', () => {
    const cone = buildAoeCells({
      aoePreview: { template: 'cone', radius: 3 },
      aoeHover: '5_8',
      origin: { x: 5, y: 5 },
    })
    expect(cone.center).toBe('5_8')
    expect(cone.ring.has('5_6')).toBe(true)
    expect(cone.ring.has('4_7')).toBe(true)
    expect(cone.ring.has('8_5')).toBe(false)

    const line = buildAoeCells({
      aoePreview: { template: 'line', radius: 3 },
      aoeHover: '8_5',
      origin: { x: 5, y: 5 },
    })
    expect(line.ring.has('6_5')).toBe(true)
    expect(line.ring.has('8_5')).toBe(true)
    expect(line.ring.has('6_6')).toBe(false)

    const cube = buildAoeCells({
      aoePreview: { template: 'cube', radius: 3, size: 3 },
      aoeHover: '5_5',
    })
    expect(cube.ring.has('4_4')).toBe(true)
    expect(cube.ring.has('6_6')).toBe(true)
    expect(cube.ring.has('7_7')).toBe(false)

    const aura = buildAoeCells({
      aoePreview: { template: 'aura', radius: 1 },
      aoeHover: '9_9',
      origin: { x: 5, y: 5 },
    })
    expect(aura.center).toBe('5_5')
    expect(aura.ring.has('6_5')).toBe(true)
    expect(aura.ring.has('9_9')).toBe(false)
  })

  it('buildSpellAoePreview infers common DnD area templates from spell text', () => {
    expect(buildSpellAoePreview({
      name: '火球术',
      aoe: true,
      desc: '半径20尺爆炸',
    })).toEqual({ radius: 4, template: 'sphere', spellName: '火球术' })
    expect(buildSpellAoePreview({
      name: '灼热之手',
      aoe: true,
      desc: '15尺锥形区域喷射火焰',
    })).toEqual({ radius: 3, template: 'cone', spellName: '灼热之手' })
    expect(buildSpellAoePreview({
      name: '闪电箭',
      aoe: true,
      desc: '100尺长直线',
    })).toEqual({ radius: 20, template: 'line', spellName: '闪电箭' })
    expect(buildSpellAoePreview({
      name: '雷鸣波',
      aoe: true,
      desc: '15尺立方区域',
    })).toEqual({ radius: 3, template: 'cube', spellName: '雷鸣波', size: 3 })
    expect(getAoeTemplateType({
      name: '神灵守护',
      aoe: true,
      desc: '15尺内敌人减速',
    })).toBe('aura')
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

  it('collectSpellCastTargetIds returns living entities inside the AoE preview', () => {
    expect(collectSpellCastTargetIds({
      spell: {
        name: '火球术',
        type: 'damage',
        aoe: true,
        desc: '半径10尺爆炸',
      },
      playerId: 'player',
      aoeHover: '3_3',
      combat: {
        entity_positions: {
          player: { x: 2, y: 2 },
          enemy1: { x: 3, y: 3 },
          enemy2: { x: 8, y: 8 },
          ally: { x: 4, y: 4 },
          deadEnemy: { x: 2, y: 3 },
        },
        entities: {
          player: { id: 'player', is_enemy: false, hp_current: 12 },
          enemy1: { id: 'enemy1', is_enemy: true, hp_current: 7 },
          enemy2: { id: 'enemy2', is_enemy: true, hp_current: 7 },
          ally: { id: 'ally', is_enemy: false, hp_current: 5 },
          deadEnemy: { id: 'deadEnemy', is_enemy: true, hp_current: 0 },
        },
      },
    })).toEqual(['player', 'enemy1', 'ally'])
  })

  it('collectSpellCastTargetIds honors explicit AoE target caps', () => {
    expect(getSpellMaxTargets({
      name: 'Mass Healing Word',
      type: 'heal',
      aoe: true,
      max_targets: 2,
    })).toBe(2)

    const cappedArgs = {
      spell: {
        name: 'Mass Healing Word',
        type: 'heal',
        aoe: true,
        max_targets: 2,
        desc: 'up to 6 creatures recover hit points',
      },
      playerId: 'player',
      aoeHover: '3_3',
      combat: {
        entity_positions: {
          player: { x: 2, y: 2 },
          ally1: { x: 3, y: 3 },
          ally2: { x: 4, y: 3 },
          ally3: { x: 4, y: 4 },
          enemy1: { x: 3, y: 4 },
        },
        entities: {
          player: { id: 'player', is_enemy: false, hp_current: 4 },
          ally1: { id: 'ally1', is_enemy: false, hp_current: 5 },
          ally2: { id: 'ally2', is_enemy: false, hp_current: 6 },
          ally3: { id: 'ally3', is_enemy: false, hp_current: 7 },
          enemy1: { id: 'enemy1', is_enemy: true, hp_current: 7 },
        },
      },
    }

    expect(collectSpellCastTargetIds(cappedArgs)).toEqual(['player', 'ally1'])
    expect(collectSpellCastTargetIds({ ...cappedArgs, ignoreTargetCap: true })).toEqual(['player', 'ally1', 'ally2', 'ally3'])
  })

  it('getSpellCastDisabledReason blocks invalid target types and empty AoE cells before submit', () => {
    const combat = {
      entity_positions: {
        hero: { x: 1, y: 1 },
        ally: { x: 2, y: 1 },
        enemy: { x: 8, y: 8 },
        dead: { x: 2, y: 2 },
      },
      entities: {
        hero: { id: 'hero', is_enemy: false, hp_current: 10 },
        ally: { id: 'ally', is_enemy: false, hp_current: 0, death_saves: { failures: 3 } },
        enemy: { id: 'enemy', is_enemy: true, hp_current: 7 },
        dead: { id: 'dead', is_enemy: true, hp_current: 0, life_state: 'dead' },
      },
    }

    expect(getSpellCastDisabledReason({
      spell: { name: 'Cure Wounds', type: 'heal', level: 1, target_type: 'ally' },
      selectedTarget: 'enemy',
      playerId: 'hero',
      combat,
    })).toBe('请选择队友或自己作为法术目标')

    expect(getSpellCastDisabledReason({
      spell: { name: 'Fire Bolt', type: 'damage', level: 0, target_type: 'enemy' },
      selectedTarget: 'hero',
      playerId: 'hero',
      combat,
    })).toBe('请选择敌人作为法术目标')

    expect(getSpellCastDisabledReason({
      spell: { name: 'Fireball', type: 'damage', level: 3, aoe: true, desc: '5ft radius blast' },
      playerId: 'hero',
      aoeHover: '12_12',
      combat,
    })).toBe('法术范围内没有可结算目标')
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
    const { walls, hazards, objectives, terrainDetails } = buildGridTerrainSets({
      '1_1': 'wall',
      '2_2': 'hazard',
      '3_3': 'difficult',
      '4_4': { terrain: 'hazard', damage_dice: '1d6' },
      '5_5': { terrain: 'total_cover' },
      '6_6': { objective: true, name: 'Seal the rift' },
      '7_7': 'floor',
    })

    expect(walls.has('1_1')).toBe(true)
    expect(walls.has('5_5')).toBe(true)
    expect(hazards.has('2_2')).toBe(true)
    expect(hazards.has('3_3')).toBe(true)
    expect(hazards.has('4_4')).toBe(true)
    expect(objectives.has('6_6')).toBe(true)
    expect(hazards.has('7_7')).toBe(false)
    expect(terrainDetails['4_4']).toMatchObject({
      key: '4_4',
      terrain: 'hazard',
      label: '危险',
      damageDice: '1d6',
    })
    expect(terrainDetails['6_6']).toMatchObject({
      key: '6_6',
      terrain: 'objective',
      label: 'Seal the rift',
    })
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
        { character_id: 'ally', name: 'Downed Ally', initiative: 2 },
      ],
      currentTurnIndex: 1,
      entities: {
        player: { hp_current: 10, hp_max: 20 },
        enemy1: { hp_current: 2, hp_max: 10 },
        enemy2: { hp_current: 0, hp_max: 8, life_state: 'dead' },
        ally: { hp_current: 0, hp_max: 12, life_state: 'dying' },
      },
    })

    expect(chips[0]).toMatchObject({ pct: 50, isCur: false, dead: false, low: false })
    expect(chips[1]).toMatchObject({ pct: 20, isCur: true, dead: false, low: true })
    expect(chips[2]).toMatchObject({ pct: 0, isCur: false, dead: true, lifeState: 'dead', low: true })
    expect(chips[3]).toMatchObject({ pct: 0, isCur: false, dead: false, lifeState: 'dying', low: true })
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

  it('getPlayerAvailableSpells matches English known spell names to localized spell data', () => {
    const spells = [
      { name: '火焰射线', name_en: 'Fire Bolt', classes: ['Wizard'] },
      { name: '治愈创伤', name_en: 'Cure Wounds', classes: ['Cleric'] },
      { name: '祝福', name_en: 'Bless', classes: ['Cleric'] },
    ]

    expect(getPlayerAvailableSpells({
      spells,
      knownSpells: ['cure-wounds'],
      cantrips: ['Fire Bolt'],
      playerClass: 'Wizard',
    }).map(s => s.name)).toEqual(['火焰射线', '治愈创伤'])
    expect(spellNameMatches(spells[0], 'fire_bolt')).toBe(true)
  })

  it('getPlayerAvailableSpells includes Magic Initiate feat cantrips and spell', () => {
    const spells = [
      { name: 'Mage Hand', level: 0, classes: ['Wizard'] },
      { name: 'Light', level: 0, classes: ['Cleric'] },
      { name: 'Shield', level: 1, classes: ['Wizard'] },
      { name: 'Cure Wounds', level: 1, classes: ['Cleric'] },
    ]
    const feats = [{
      name: 'Magic Initiate',
      cantrips: ['Mage Hand', 'Light'],
      spell: 'Shield',
    }]

    expect(getPlayerAvailableSpells({ spells, feats }).map(s => s.name))
      .toEqual(['Mage Hand', 'Light', 'Shield'])
    expect(getMagicInitiateSpellCastInfo({
      spell: spells[2],
      character: {
        feats,
        class_resources: { magic_initiate_spell_uses_remaining: 1 },
      },
      castLevel: 1,
    })).toMatchObject({
      matches: true,
      remaining: 1,
      canUse: true,
    })
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

  it('applyEntityStateUpdate 合并死亡豁免、条件和生命状态', () => {
    const combat = {
      entities: {
        hero: {
          id: 'hero',
          hp_current: 7,
          death_saves: null,
          conditions: [],
          life_state: 'alive',
        concentration: 'Bless',
        temporary_hp: 0,
        class_resources: {},
      },
        ally: { id: 'ally', hp_current: 5 },
      },
    }

    const updated = applyEntityStateUpdate(combat, {
      target_id: 'hero',
      new_hp: 0,
      death_saves: { successes: 0, failures: 1, stable: false },
      conditions: ['unconscious'],
      life_state: 'dying',
      concentration: null,
      temporary_hp: 4,
      class_resources: { temporary_hp: 4, temporary_hp_source: 'armor_of_agathys' },
    })

    expect(updated).not.toBe(combat)
    expect(updated.entities.hero).toMatchObject({
      hp_current: 0,
      death_saves: { successes: 0, failures: 1, stable: false },
      conditions: ['unconscious'],
      life_state: 'dying',
      concentration: null,
      temporary_hp: 4,
      class_resources: { temporary_hp: 4, temporary_hp_source: 'armor_of_agathys' },
    })
    expect(updated.entities.ally).toBe(combat.entities.ally)
  })

  it('applyActionResultEntityStates applies target, aoe and resurrection state results', () => {
    const combat = {
      entities: {
        enemy: { id: 'enemy', hp_current: 8 },
        bystander: { id: 'bystander', hp_current: 6 },
        webbed: { id: 'webbed', hp_current: 9, conditions: [] },
        'breath-hit': { id: 'breath-hit', hp_current: 10, conditions: [] },
        cleric: {
          id: 'cleric',
          hp_current: 0,
          death_saves: { successes: 0, failures: 3, stable: false },
          conditions: ['unconscious'],
          life_state: 'dead',
        },
        hero: {
          id: 'hero',
          class_resources: { magic_initiate_spell_uses_remaining: 1 },
        },
      },
    }

    const updated = applyActionResultEntityStates(combat, {
      target_state: {
        target_id: 'enemy',
        new_hp: 0,
        death_saves: { successes: 0, failures: 0, stable: false },
        conditions: ['unconscious'],
        life_state: 'dying',
      },
      aoe_results: [
        { target_id: 'bystander', new_hp: 2, conditions: ['burning'] },
        { target_id: 'webbed', conditions: ['restrained'], condition_durations: { restrained: 600 } },
      ],
      target_results: [
        { target_id: 'breath-hit', new_hp: 4, conditions: ['burning'] },
      ],
      resurrection_results: [
        { target_id: 'cleric', resurrected: true, new_hp: 1, death_saves: null, conditions: [], life_state: 'alive' },
      ],
      caster_state: {
        target_id: 'hero',
        entity_id: 'hero',
        class_resources: { magic_initiate_spell_uses_remaining: 0 },
      },
    })

    expect(updated.entities.enemy.life_state).toBe('dying')
    expect(updated.entities.bystander).toMatchObject({ hp_current: 2, conditions: ['burning'] })
    expect(updated.entities.webbed).toMatchObject({
      conditions: ['restrained'],
      condition_durations: { restrained: 600 },
    })
    expect(updated.entities['breath-hit']).toMatchObject({ hp_current: 4, conditions: ['burning'] })
    expect(updated.entities.cleric).toMatchObject({
      hp_current: 1,
      death_saves: null,
      conditions: [],
      life_state: 'alive',
    })
    expect(updated.entities.hero.class_resources.magic_initiate_spell_uses_remaining).toBe(0)
  })

  it('formats and applies weapon resource updates from attack rolls', () => {
    expect(formatWeaponResourceLog({
      weapon: 'Longbow',
      resource_type: 'ammunition',
      consumed: true,
      ammo_remaining: 19,
    })).toBe('Longbow 弹药 -1，剩余 19')
    expect(formatWeaponResourceLog({
      weapon: 'Javelin',
      resource_type: 'thrown_weapon',
      consumed: true,
      weapon_removed: true,
    })).toBe('投出 Javelin，背包中移除 1 件')

    const combat = {
      entities: {
        hero: {
          id: 'hero',
          equipment: {
            weapons: [
              { name: 'Longbow', ammo: 20, equipped: true },
              { name: 'Javelin', equipped: false, properties: ['thrown(30/120)'] },
            ],
          },
        },
      },
    }

    const updatedAmmo = applyWeaponResourceToCombat(combat, 'hero', {
      weapon: 'Longbow',
      resource_type: 'ammunition',
      consumed: true,
      ammo_remaining: 19,
    })

    expect(updatedAmmo).not.toBe(combat)
    expect(updatedAmmo.entities.hero.equipment.weapons[0].ammo).toBe(19)
    expect(combat.entities.hero.equipment.weapons[0].ammo).toBe(20)
  })

  it('applies thrown weapon removal and keeps a replacement equipped', () => {
    const combat = {
      entities: {
        hero: {
          id: 'hero',
          equipment: {
            weapons: [
              { name: 'Javelin', equipped: true, properties: ['thrown(30/120)'] },
              { name: 'Javelin', equipped: false, properties: ['thrown(30/120)'] },
            ],
          },
        },
      },
    }

    const updated = applyWeaponResourceToCombat(combat, 'hero', {
      weapon: 'Javelin',
      resource_type: 'thrown_weapon',
      consumed: true,
      weapon_removed: true,
    })

    expect(updated.entities.hero.equipment.weapons).toEqual([
      { name: 'Javelin', equipped: true, properties: ['thrown(30/120)'] },
    ])
  })

  it('summarizes equipped ammo and thrown weapon resources for the HUD', () => {
    expect(getEquippedWeaponResourceSummary({
      equipment: {
        weapons: [
          { name: 'Longbow', ammo: 7, equipped: true },
        ],
      },
    })).toEqual({ label: 'Longbow', value: '弹药 7' })

    expect(getEquippedWeaponResourceSummary({
      equipment: {
        weapons: [
          { name: 'Javelin', equipped: true, properties: ['thrown(30/120)'] },
          { name: 'Javelin', equipped: false, properties: ['thrown(30/120)'] },
        ],
      },
    })).toEqual({ label: 'Javelin', value: '投掷 2' })
  })

  it('getCombatLifeState separates dying, stable and dead zero-hp entities', () => {
    expect(getCombatLifeState({ hp_current: 0, death_saves: { failures: 0, stable: false } })).toBe('dying')
    expect(getCombatLifeState({ hp_current: 0, death_saves: { failures: 1, stable: true } })).toBe('stable')
    expect(getCombatLifeState({ hp_current: 0, death_saves: { failures: 3, stable: false } })).toBe('dead')
    expect(isCombatEntityDead({ hp_current: 0, death_saves: { failures: 1, stable: false } })).toBe(false)
    expect(isCombatEntityDead({ hp_current: 0, death_saves: { failures: 3, stable: false } })).toBe(true)
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

  it('computeSkillStats keeps item healing hints independent from bonus action kind', () => {
    expect(computeSkillStats(
      { k: 'pot_heal', kind: 'item' },
      { derived: {} },
      null,
    )).toEqual([{ label: '恢复', value: '2d4+2' }])
  })

  it('requires a completed main-hand attack before offhand skill use', () => {
    const skill = { k: 'off_attack', kind: 'bonus', available: true }

    expect(getSkillUnavailableReason({
      skill,
      turnState: { action_used: true, attacks_made: 0, bonus_action_used: false },
      isPlayerTurn: true,
      selectedTarget: 'enemy-1',
    })).toBe('需要先完成主手攻击')

    expect(getSkillUnavailableReason({
      skill,
      turnState: { action_used: false, attacks_made: 1, bonus_action_used: false },
      isPlayerTurn: true,
      selectedTarget: 'enemy-1',
    })).toBe('')
  })

  it('prioritizes spent action economy over missing target hints', () => {
    expect(getSkillUnavailableReason({
      skill: { k: 'atk', kind: 'attack', available: true },
      turnState: { action_used: true },
      isPlayerTurn: true,
      selectedTarget: null,
    })).toBe('本回合动作已使用')
  })

  it('buildCombatPreviewRows surfaces hit chance, damage, cover and resource cost', () => {
    expect(buildCombatPreviewRows({
      prediction: {
        hit_rate: 0.64,
        crit_rate: 0.0975,
        expected_damage: 6.4,
        damage_min: 4,
        damage_max: 11,
        damage_dice: '1d8+3',
        damage_type: '切割',
        target_ac: 13,
        effective_target_ac: 15,
        cover_bonus: 2,
        attack_bonus: 5,
        advantage: true,
        modifiers: ['优势', '半掩护'],
      },
      skill: { k: 'atk', kind: 'attack', cost: '动作' },
      target: { ac: 13 },
    })).toEqual([
      { label: '命中率', value: '64%', tone: 'good' },
      { label: '暴击率', value: '10%' },
      { label: '伤害', value: '1d8+3 · 期望 6.4 切割' },
      { label: '伤害范围', value: '4-11 切割' },
      { label: '目标AC', value: '13 -> 15' },
      { label: '掩护', value: '+2 AC' },
      { label: '攻击加值', value: '+5' },
      { label: '态势', value: '优势 / 半掩护' },
      { label: '资源', value: '动作' },
    ])
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

  it('多人 AI 回合只由一个确定客户端自动推进', () => {
    const room = {
      host_user_id: 'host',
      members: [
        { user_id: 'host', is_online: true },
        { user_id: 'guest', is_online: true },
      ],
    }

    expect(getAiCombatTurnDriverUserId(room)).toBe('host')
    expect(canDriveAiCombatTurns({ room, myUserId: 'host' })).toBe(true)
    expect(canDriveAiCombatTurns({ room, myUserId: 'guest' })).toBe(false)
    expect(canDriveAiCombatTurns({
      room: {
        ...room,
        members: [
          { user_id: 'host', is_online: false },
          { user_id: 'guest', is_online: true },
        ],
      },
      myUserId: 'guest',
    })).toBe(true)
    expect(canDriveAiCombatTurns({ room: null, myUserId: null })).toBe(true)
  })

  it('getCombatTurnToken 以回合数、先攻索引和当前施动者生成幂等牌', () => {
    expect(getCombatTurnToken({
      round_number: 2,
      current_turn_index: 1,
      turn_order: [
        { character_id: 'hero-1' },
        { character_id: 'enemy-1' },
      ],
    })).toBe('2:1:enemy-1')
    expect(getCombatTurnToken({ turn_order: [] })).toBeNull()
    expect(getCombatTurnToken(null)).toBeNull()
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
