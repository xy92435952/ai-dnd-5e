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
 * @param {object} skill        - skillBar entry，含 kind ('attack' | 'spell' | 'move' | 'action' | 'bonus' | 'item')
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
  } else if (skill.k === 'pot' || skill.k === 'pot_heal') {
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

function normalizeEntityStateUpdate(targetId, update = {}) {
  if (!targetId && !update?.target_id && !update?.entity_id) return null
  const resolvedTargetId = targetId || update.target_id || update.entity_id
  const rawHp = update.hp_current ?? update.new_hp ?? update.hp
  const normalized = { target_id: resolvedTargetId }

  if (rawHp !== null && rawHp !== undefined) {
    normalized.hp_current = Math.max(0, rawHp)
  }
  if ('death_saves' in update) normalized.death_saves = update.death_saves
  if ('conditions' in update) normalized.conditions = update.conditions || []
  if ('condition_durations' in update) normalized.condition_durations = update.condition_durations || {}
  if ('life_state' in update) normalized.life_state = update.life_state
  if ('concentration' in update) normalized.concentration = update.concentration
  if ('temporary_hp' in update) normalized.temporary_hp = update.temporary_hp || 0
  if ('wild_shape_hp' in update) normalized.wild_shape_hp = update.wild_shape_hp || 0
  if ('class_resources' in update) normalized.class_resources = update.class_resources || {}
  return normalized
}

/**
 * 不可变地更新 combat.entities[targetId] 的 HP / death_saves / conditions / life_state。
 * 兼容旧调用 applyHpUpdate(combat, targetId, newHp) 和新调用 applyEntityStateUpdate(combat, update)。
 */
export function applyEntityStateUpdate(combat, targetIdOrUpdate, maybeUpdate) {
  if (!combat) return combat
  const update = typeof targetIdOrUpdate === 'object'
    ? normalizeEntityStateUpdate(null, targetIdOrUpdate)
    : normalizeEntityStateUpdate(targetIdOrUpdate, typeof maybeUpdate === 'object'
      ? maybeUpdate
      : { hp_current: maybeUpdate })
  if (!update?.target_id) return combat

  const current = combat.entities?.[update.target_id]
  if (!current) return combat

  const entities = { ...(combat.entities || {}) }
  const nextEntity = { ...current }
  if ('hp_current' in update) nextEntity.hp_current = update.hp_current
  if ('death_saves' in update) nextEntity.death_saves = update.death_saves
  if ('conditions' in update) nextEntity.conditions = update.conditions
  if ('condition_durations' in update) nextEntity.condition_durations = update.condition_durations
  if ('life_state' in update) nextEntity.life_state = update.life_state
  if ('concentration' in update) nextEntity.concentration = update.concentration
  if ('temporary_hp' in update) nextEntity.temporary_hp = update.temporary_hp
  if ('wild_shape_hp' in update) nextEntity.wild_shape_hp = update.wild_shape_hp
  if ('class_resources' in update) nextEntity.class_resources = update.class_resources
  entities[update.target_id] = nextEntity
  return { ...combat, entities }
}

export function applyHpUpdate(combat, targetId, newHp) {
  return applyEntityStateUpdate(combat, targetId, newHp)
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
    updated = applyEntityStateUpdate(updated, aoe)
  }
  return updated
}

export function applyEntityStateUpdates(combat, updates = []) {
  if (!combat || !updates?.length) return combat
  return updates.reduce((updated, update) => applyEntityStateUpdate(updated, update), combat)
}

export function applyActionResultEntityStates(combat, result = {}) {
  if (!combat || !result) return combat

  let updated = combat
  if (result.target_state) {
    updated = applyEntityStateUpdate(updated, result.target_state)
  } else if (result.target_id && result.target_new_hp !== null && result.target_new_hp !== undefined) {
    updated = applyEntityStateUpdate(updated, result.target_id, result.target_new_hp)
  }
  updated = applyEntityStateUpdates(updated, result.aoe_results || [])
  updated = applyEntityStateUpdates(updated, result.resurrection_results || [])
  return updated
}

export function getCombatLifeState(ent) {
  if (!ent) return 'alive'
  if (ent.life_state) return ent.life_state
  const hp = ent.hp_current ?? 0
  const saves = ent.death_saves || {}
  if (hp > 0) return 'alive'
  if ((saves.failures || 0) >= 3) return 'dead'
  if (saves.stable) return 'stable'
  if ('death_saves' in ent || ent.is_enemy === false || ent.is_player) return 'dying'
  return hp <= 0 ? 'dead' : 'alive'
}

export function isCombatEntityDead(ent) {
  return getCombatLifeState(ent) === 'dead'
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
    const lifeState = getCombatLifeState(ent)
    const dead = lifeState === 'dead'
    return { ent, t, i, pct, isCur, dead, lifeState, low: pct < 34 }
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
 * 当前登录用户是否能主动操作本回合。
 */
export function canActInCombatTurn({ room, combat, myCharacterId }) {
  if (!room) return isPlayerCombatTurn(combat)
  return isMyCombatTurn({ room, combat, myCharacterId })
}

export function getAiCombatTurnDriverUserId(room) {
  if (!room) return null
  const members = Array.isArray(room.members)
    ? room.members.filter(member => member?.user_id)
    : []
  const onlineMembers = members.filter(member => member.is_online !== false)
  const candidates = onlineMembers.length ? onlineMembers : members
  const host = candidates.find(member => member.user_id === room.host_user_id)
  return host?.user_id || candidates[0]?.user_id || room.host_user_id || null
}

export function canDriveAiCombatTurns({ room, myUserId }) {
  if (!room) return true
  if (!myUserId) return false
  return getAiCombatTurnDriverUserId(room) === myUserId
}

export function getCombatTurnToken(combat) {
  if (!combat?.turn_order?.length) return null
  const turnIndex = combat.current_turn_index ?? 0
  const current = combat.turn_order[turnIndex]
  const actorId = current?.character_id || current?.id
  if (!actorId) return null
  return `${combat.round_number || 1}:${turnIndex}:${actorId}`
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
  const known = new Set([...(knownSpells || []), ...(cantrips || [])].map(normalizeSpellKey))
  if (known.size > 0) {
    return spells.filter(s => known.has(normalizeSpellKey(s.name)) || known.has(normalizeSpellKey(s.name_en)))
  }
  if (playerClass) {
    const mappedClass = CLASS_SPELL_MAP[playerClass] || playerClass.replace(/[\u4e00-\u9fff]/g, '') || playerClass
    return spells.filter(s => s.classes?.includes(mappedClass))
  }
  return spells
}

export function normalizeSpellKey(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[\s_-]+/g, '')
}

export function spellNameMatches(spell, targetName) {
  const target = normalizeSpellKey(targetName)
  return !!target && [spell?.name, spell?.name_en].some(name => normalizeSpellKey(name) === target)
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
