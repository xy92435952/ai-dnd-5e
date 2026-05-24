import { DEFAULT_SKILL_BAR } from '../data/combat'

/**
 * utils/combat.js — 战斗场景下用到的纯工具函数。
 *
 * 原先散落在 pages/Combat.jsx 顶部和底部的 computeSkillStats /
 * aoeRadiusCells / applyHpUpdate 三个纯函数抽到这里，Combat.jsx 只管
 * render + state。
 */

/**
 * 根据玩家角色 + 目标估算某技能的命中率 / 伤害。
 * 用于技能栏 hover tooltip。
 *
 * @param {object} skill        - skillBar entry，含 kind ('attack' | 'spell' | 'move' | 'bonus') 和 k ('atk' | 'spell' | ...)
 * @param {object} player       - 当前玩家 Character（derived 字段会被读）
 * @param {object|null} target  - 锁定目标实体（有 ac 字段）
 * @param {object|null} hover   - 鼠标悬停的临时目标
 * @returns {Array<{label:string, value:string|number}>|null}
 */
export function computeSkillStats(skill, player, target, hoverTarget) {
  if (!player) return null
  const d = player.derived || {}
  const atkBonus = d.attack_bonus ?? (d.proficiency_bonus || 2) + (d.ability_modifiers?.str || 0)
  const targetAc = (hoverTarget || target)?.ac ?? target?.ac ?? null

  const stats = []
  if (skill.kind === 'attack') {
    if (targetAc != null) {
      // 命中率 = P(d20 + atkBonus >= targetAc)
      const needed = targetAc - atkBonus
      const pct = needed <= 1 ? 95 : needed >= 20 ? 5 : Math.max(5, Math.min(95, (21 - needed) * 5))
      stats.push({ label: '命中率', value: `${pct}%` })
      stats.push({ label: '攻击加值', value: `+${atkBonus}` })
    } else {
      stats.push({ label: '命中率', value: '需选目标' })
      stats.push({ label: '攻击加值', value: `+${atkBonus}` })
    }
  } else if (skill.kind === 'spell') {
    stats.push({ label: '法术 DC', value: d.spell_save_dc ?? '—' })
    stats.push({ label: '施法加值', value: `+${(d.proficiency_bonus || 2) + (d.ability_modifiers?.cha || 0)}` })
  } else if (skill.kind === 'move') {
    stats.push({ label: '移动力', value: `${d.speed ?? 30} 尺` })
  } else if (skill.kind === 'bonus' && skill.k === 'pot') {
    stats.push({ label: '恢复', value: '2d4+2' })
  }
  return stats
}

/**
 * 粗略估算 AoE 法术的格子半径：从描述里抓 "N尺"，5尺/格。
 *
 * @param {object} spell
 * @returns {number} 格子数；非 AoE 法术返回 0；抓不到描述则默认 3（15ft）
 */
export function aoeRadiusCells(spell) {
  if (!spell || !spell.aoe) return 0
  const m = (spell.desc || '').match(/(\d+)\s*尺/)
  if (m) return Math.max(1, Math.round(parseInt(m[1]) / 5))
  return 3
}

/**
 * 不可变地更新 combat.entities[targetId].hp_current。
 * HP 下限 0。调用方无需 structuredClone。
 *
 * @param {object} combat
 * @param {string|null} targetId
 * @param {number|null|undefined} newHp
 * @returns {object} 新的 combat 对象（未命中时返回原对象）
 */
export function applyHpUpdate(combat, targetId, newHp) {
  if (!targetId || newHp === null || newHp === undefined) return combat
  const entities = { ...combat.entities }
  if (entities[targetId]) {
    entities[targetId] = { ...entities[targetId], hp_current: Math.max(0, newHp) }
  }
  return { ...combat, entities }
}

/**
 * 不可变地更新指定玩家 HP。
 */
export function applyPlayerHpUpdate(combat, playerId, hpCurrent) {
  if (!combat || !playerId) return combat
  const updated = { ...combat, entities: { ...combat.entities } }
  if (updated.entities[playerId]) {
    updated.entities[playerId] = {
      ...updated.entities[playerId],
      hp_current: hpCurrent,
    }
  }
  return updated
}

/**
 * 批量应用 AoE HP 结果。后端有的返回 new_hp，有的返回 hp，这里统一。
 */
export function applyAoeHpUpdates(combat, aoeResults = []) {
  if (!combat || !aoeResults?.length) return combat

  let updated = combat
  for (const aoe of aoeResults) {
    const hp = aoe.new_hp != null ? aoe.new_hp : aoe.hp
    if (hp != null) {
      updated = applyHpUpdate(updated, aoe.target_id, hp)
    }
  }
  return updated
}

/**
 * 生成威胁区：每个存活敌人相邻 8 格都算威胁格。
 *
 * @param {{ showThreat:boolean, entityPositions:object, entities:object }} args
 * @returns {Set<string>}
 */
export function buildThreatCells({ showThreat, entityPositions = {}, entities = {} }) {
  const set = new Set()
  if (!showThreat) return set

  for (const [id, pos] of Object.entries(entityPositions)) {
    const ent = entities[id]
    if (!ent || !ent.is_enemy || (ent.hp_current ?? 0) <= 0) continue
    for (let dy = -1; dy <= 1; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        if (dx === 0 && dy === 0) continue
        set.add(`${pos.x + dx}_${pos.y + dy}`)
      }
    }
  }
  return set
}

/**
 * 生成 AoE 预览格：以 hover 格为中心，半径 R 内的圆形区域。
 *
 * @param {{ aoePreview: { radius?: number } | null, aoeHover: string | null }} args
 * @returns {{ center:string|null, ring:Set<string> }}
 */
export function buildAoeCells({ aoePreview, aoeHover }) {
  const out = { center: null, ring: new Set() }
  if (!aoePreview || !aoeHover) return out

  const [cx, cy] = aoeHover.split('_').map(Number)
  const radius = aoePreview.radius || 1
  out.center = aoeHover
  for (let dy = -radius; dy <= radius; dy++) {
    for (let dx = -radius; dx <= radius; dx++) {
      const d = Math.sqrt(dx * dx + dy * dy)
      if (d <= radius + 0.5) out.ring.add(`${cx + dx}_${cy + dy}`)
    }
  }
  return out
}

/**
 * 构建固定尺寸战斗格子矩阵，并把实体挂到对应格上。
 *
 * @param {{ rows:number, cols:number, entityPositions:object, entities:object }} args
 * @returns {Array<Array<{x:number, y:number, entityId:string|null, entity:object|null}>>}
 */
export function buildCombatGrid({ rows, cols, entityPositions = {}, entities = {} }) {
  return Array.from({ length: rows }, (_, row) =>
    Array.from({ length: cols }, (_, col) => {
      const entry = Object.entries(entityPositions).find(([, p]) => p.x === col && p.y === row)
      return { x: col, y: row, entityId: entry?.[0] || null, entity: entry ? entities[entry[0]] : null }
    })
  )
}

/**
 * 计算 iso 相机窗口左上角，保证窗口不越界。
 */
export function getCameraWindow({
  playerPos,
  totalWidth,
  totalHeight,
  viewWidth,
  viewHeight,
  fallbackX = 10,
  fallbackY = 6,
}) {
  const cx = Math.max(0, Math.min(totalWidth - viewWidth, (playerPos?.x ?? fallbackX) - viewWidth / 2))
  const cy = Math.max(0, Math.min(totalHeight - viewHeight, (playerPos?.y ?? fallbackY) - viewHeight / 2))
  return { x0: Math.floor(cx), y0: Math.floor(cy) }
}

/**
 * 从 grid_data 中拆出墙体和危险/困难地形集合。
 */
export function buildGridTerrainSets(gridData = {}) {
  const walls = new Set()
  const hazards = new Set()
  for (const [key, value] of Object.entries(gridData)) {
    if (value === 'wall') walls.add(key)
    else if (value === 'hazard' || value === 'difficult') hazards.add(key)
  }
  return { walls, hazards }
}

/**
 * 战斗实体到 sprite key 的兜底映射。
 */
export function getSpriteKind(ent) {
  if (!ent) return 'paladin'
  if (ent.sprite) return ent.sprite
  if (ent.is_enemy) return 'cultist'
  return (ent.char_class || 'fighter').toLowerCase()
}

/**
 * 先攻条展示数据派生：把 turn_order 与实体 HP 合并成 UI chip。
 */
export function buildInitiativeChips({ turnOrder = [], currentTurnIndex = 0, entities = {} }) {
  return (turnOrder || []).map((t, i) => {
    const ent = entities[t.character_id]
    const hp = ent?.hp_current ?? 0
    const hpMax = ent?.hp_max ?? 1
    const pct = Math.max(0, Math.min(100, (hp / hpMax) * 100))
    const isCur = i === (currentTurnIndex ?? 0)
    const dead = hp <= 0
    return { ent, t, i, pct, isCur, dead, low: pct < 34 }
  })
}

/**
 * 当前回合是否为玩家回合。
 */
export function isPlayerCombatTurn(combat) {
  if (!combat) return false
  return combat.turn_order?.[combat.current_turn_index]?.is_player === true
}

/**
 * 从 combat.turn_states 中取指定玩家的回合状态。
 */
export function getPlayerTurnState(combat, playerId) {
  if (!combat || !playerId) return null
  return combat.turn_states?.[playerId] || null
}

export function hasPendingAiReaction(combat) {
  return Object.values(combat?.turn_states || {}).some(ts => Boolean(ts?.pending_ai_attack))
}

/**
 * 多人战斗中判断当前回合是否归当前用户控制的角色。
 */
export function isMyCombatTurn({ room, combat, myCharacterId }) {
  if (!room) return true
  if (!combat?.turn_order?.length) return false
  const cur = combat.turn_order[combat.current_turn_index || 0]
  return cur?.character_id === myCharacterId
}

/**
 * 多人战斗顶部当前回合标签。
 */
export function getCurrentTurnLabel({ room, combat }) {
  if (!room || !combat?.turn_order?.length) return ''
  const cur = combat.turn_order[combat.current_turn_index || 0]
  if (!cur) return ''
  const member = (room.members || []).find(mb => mb.character_id === cur.character_id)
  if (member) return `当前回合：${member.display_name}（${cur.name}）`
  return `当前回合：${cur.name}（AI 托管）`
}

/**
 * 用玩家职业推导 /predict 的 action_key。
 */
export function getCombatPredictionActionKey(playerClass = '') {
  if (playerClass?.includes('Paladin') || playerClass?.includes('圣武')) return 'smite'
  if (playerClass?.includes('Rogue') || playerClass?.includes('游荡')) return 'sneak'
  if (playerClass?.includes('Wizard') || playerClass?.includes('法师')) return 'firebolt'
  if (playerClass?.includes('Cleric') || playerClass?.includes('牧师')) return 'sacred_flame'
  return 'atk'
}

const CLASS_SPELL_MAP = {
  Fighter: 'Fighter',
  战士: 'Fighter',
  Wizard: 'Wizard',
  法师: 'Wizard',
  Sorcerer: 'Sorcerer',
  术士: 'Sorcerer',
  Cleric: 'Cleric',
  牧师: 'Cleric',
  Bard: 'Bard',
  吟游诗人: 'Bard',
  Druid: 'Druid',
  德鲁伊: 'Druid',
  Warlock: 'Warlock',
  邪术师: 'Warlock',
  Paladin: 'Paladin',
  圣武士: 'Paladin',
  Ranger: 'Ranger',
  游侠: 'Ranger',
}

/**
 * 玩家实际可用法术：优先使用角色已知法术/戏法；没有列表时按职业过滤。
 */
export function getPlayerAvailableSpells({
  spells = [],
  knownSpells = [],
  cantrips = [],
  playerClass = '',
}) {
  const known = new Set([...(knownSpells || []), ...(cantrips || [])])
  if (known.size > 0) {
    return spells.filter(s => known.has(s.name))
  }
  if (playerClass) {
    const mappedClass = CLASS_SPELL_MAP[playerClass] || playerClass.replace(/[\u4e00-\u9fff]/g, '') || playerClass
    return spells.filter(s => s.classes?.includes(mappedClass))
  }
  return spells
}

/**
 * 后端技能栏为空时使用本地兜底。
 */
export function getCombatSkillBar(skillBar) {
  return skillBar && skillBar.length ? skillBar : DEFAULT_SKILL_BAR
}

/**
 * 解析 "NdM" / "dM" 掷骰表达式。
 */
export function parseDiceNotation(
  diceText,
  { defaultCount = 1, defaultFaces = 8 } = {},
) {
  const diceMatch = String(diceText || '').match(/(\d*)d(\d+)/)
  return {
    count: diceMatch ? parseInt(diceMatch[1] || '1') : defaultCount,
    faces: diceMatch ? parseInt(diceMatch[2]) : defaultFaces,
  }
}

export function getAoePreviewCenterKey({
  selectedTarget,
  entityPositions = {},
  playerPos,
}) {
  if (selectedTarget && entityPositions[selectedTarget]) {
    const pos = entityPositions[selectedTarget]
    return `${pos.x}_${pos.y}`
  }
  return playerPos ? `${playerPos.x}_${playerPos.y}` : null
}

export function countEntitiesInAoe({
  spell,
  selectedTarget,
  entityPositions = {},
  entities = {},
}) {
  if (!spell?.aoe || !selectedTarget || !entityPositions[selectedTarget]) {
    return selectedTarget ? 1 : 0
  }
  const radius = aoeRadiusCells(spell)
  const center = entityPositions[selectedTarget]
  let count = 0
  for (const [id, pos] of Object.entries(entityPositions)) {
    const entity = entities[id]
    if (!entity || entity.hp_current <= 0) continue
    if (Math.max(Math.abs(pos.x - center.x), Math.abs(pos.y - center.y)) <= radius) {
      count += 1
    }
  }
  return Math.max(count, 1)
}
