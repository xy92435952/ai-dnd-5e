import { DEFAULT_SKILL_BAR } from '../data/combat'

/**
 * utils/combat.js — 战斗场景下用到的纯工具函数。
 *
 * 原先散落在 pages/Combat.jsx 顶部和底部的 computeSkillStats /
 * aoeRadiusCells / applyHpUpdate 三个纯函数抽到这里，Combat.jsx 只管
 * render + state。
 */

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const number = Number(value)
  return `${Math.round((number <= 1 ? number * 100 : number))}%`
}

function formatSigned(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const number = Number(value)
  return number >= 0 ? `+${number}` : `${number}`
}

function formatDamagePreview(prediction = {}) {
  const dice = prediction.damage_dice && prediction.damage_dice !== '—' ? prediction.damage_dice : ''
  const expected = prediction.expected_damage ?? null
  const type = prediction.damage_type || ''
  if (dice && expected !== null) return `${dice} · 期望 ${expected}${type ? ` ${type}` : ''}`
  if (expected !== null) return `期望 ${expected}${type ? ` ${type}` : ''}`
  return dice || '—'
}

function formatDamageRange(prediction = {}) {
  const min = prediction.damage_min
  const max = prediction.damage_max
  if (min === null || min === undefined || max === null || max === undefined) return null
  const type = prediction.damage_type || ''
  return `${min}-${max}${type ? ` ${type}` : ''}`
}

function normalizeModifierTags(prediction = {}) {
  const tags = Array.isArray(prediction.modifiers) ? [...prediction.modifiers] : []
  if (prediction.advantage && !tags.includes('优势')) tags.unshift('优势')
  if (prediction.disadvantage && !tags.includes('劣势')) tags.unshift('劣势')
  return tags
}

export function buildCombatPreviewRows({ prediction = null, skill = null, player = null, target = null } = {}) {
  const rows = []

  if (prediction) {
    rows.push({ label: '命中率', value: formatPercent(prediction.hit_rate), tone: prediction.advantage ? 'good' : prediction.disadvantage ? 'bad' : 'neutral' })
    if (prediction.crit_rate !== undefined) rows.push({ label: '暴击率', value: formatPercent(prediction.crit_rate) })
    rows.push({ label: '伤害', value: formatDamagePreview(prediction) })
    const damageRange = formatDamageRange(prediction)
    if (damageRange) rows.push({ label: '伤害范围', value: damageRange })

    const targetAc = prediction.target_ac ?? prediction.target?.ac ?? target?.ac
    const effectiveAc = prediction.effective_target_ac ?? targetAc
    if (effectiveAc !== undefined) {
      rows.push({
        label: '目标AC',
        value: prediction.cover_bonus > 0 && targetAc !== effectiveAc
          ? `${targetAc} -> ${effectiveAc}`
          : `${effectiveAc}`,
      })
    }
    if (prediction.cover_bonus > 0) rows.push({ label: '掩护', value: `+${prediction.cover_bonus} AC` })
    if (prediction.attack_bonus !== undefined) rows.push({ label: '攻击加值', value: formatSigned(prediction.attack_bonus) })

    const tags = normalizeModifierTags(prediction)
    if (tags.length) rows.push({ label: '态势', value: tags.join(' / ') })
  } else if (skill) {
    rows.push(...computeSkillStats(skill, player, target))
  }

  if (skill?.cost) rows.push({ label: '资源', value: skill.cost })
  return rows
}

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

export function getAoeTemplateType(spell = {}) {
  const text = `${spell.template || ''} ${spell.shape || ''} ${spell.name || ''} ${spell.name_en || ''} ${spell.desc || ''}`.toLowerCase()
  if (/cone|锥/.test(text)) return 'cone'
  if (/line|直线/.test(text)) return 'line'
  if (/cube|立方/.test(text)) return 'cube'
  if (/aura|self|自身|以你为中心|内敌人|within .* feet of you/.test(text)) return 'aura'
  return 'sphere'
}

export function buildSpellAoePreview(spell) {
  if (!spell?.aoe) return null
  const template = getAoeTemplateType(spell)
  const radius = aoeRadiusCells(spell)
  const preview = {
    radius,
    template,
    spellName: spell.name,
  }
  if (template === 'cube') preview.size = Math.max(1, radius)
  return preview
}

function readPositiveInteger(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) && numeric > 0 ? Math.floor(numeric) : null
}

export function getSpellMaxTargets(spell = {}, level = spell?.level ?? 0) {
  const targeting = spell.targeting && typeof spell.targeting === 'object' ? spell.targeting : {}
  const explicit = readPositiveInteger(
    spell.max_targets
    ?? spell.maxTargets
    ?? spell.target_count
    ?? spell.targetCount
    ?? targeting.max_targets
    ?? targeting.maxTargets
    ?? targeting.target_count
    ?? targeting.targetCount,
  )
  if (explicit) return explicit

  const text = `${spell.targets || ''} ${spell.target || ''} ${spell.desc || ''} ${spell.description || ''}`.toLowerCase()
  const explicitText = text.match(/(?:up to|maximum|max|最多)\s*(\d+)/)
  if (explicitText) return readPositiveInteger(explicitText[1])

  const baseLevel = readPositiveInteger(spell.level)
  if (baseLevel && level > baseLevel && /additional target|one extra target|多一个目标|额外目标/.test(text)) {
    return 1 + Math.max(0, level - baseLevel)
  }

  return null
}

function getSpellTargetSide(spell = {}) {
  const targeting = spell.targeting && typeof spell.targeting === 'object' ? spell.targeting : {}
  const targetType = normalizeTargetHint(
    spell.target_type
    ?? spell.targetType
    ?? spell.target
    ?? targeting.target_type
    ?? targeting.targetType
    ?? targeting.type,
  )
  if (['self', 'self_only', 'self_target', 'selftarget'].includes(targetType)) return 'self'
  if (['ally', 'allies', 'friendly', 'friend', 'party', 'willing'].includes(targetType)) return 'ally'
  if (['enemy', 'enemies', 'hostile', 'foe'].includes(targetType)) return 'enemy'
  if (String(spell.type || '').toLowerCase() === 'heal') return 'ally'
  return 'any'
}

function getSelectedSpellTargetId({ spell, selectedTarget, playerId }) {
  if (!spell || spell.aoe) return null
  if (String(spell.type || '').toLowerCase() === 'heal') return selectedTarget || playerId || null
  return selectedTarget || null
}

function getSpellTargetEntityIssue({ spell, targetId, entities = {}, playerId = null } = {}) {
  if (!spell || !targetId || !entities?.[targetId]) return ''
  const entity = entities[targetId]
  const targetSide = getSpellTargetSide(spell)
  const spellType = String(spell.type || '').toLowerCase()

  if (isCombatEntityDead(entity)) {
    return spellType === 'heal'
      ? '目标已死亡，普通治疗无法复活'
      : '目标已经无法作为法术目标'
  }
  if (targetSide === 'self' && playerId && targetId !== playerId) return '这个法术只能以自己为目标'
  if (targetSide === 'ally' && entity.is_enemy) return '请选择队友或自己作为法术目标'
  if (targetSide === 'enemy' && !entity.is_enemy) return '请选择敌人作为法术目标'
  return ''
}

export function getSpellCastDisabledReason({
  spell,
  level = 0,
  cantrips = [],
  available = null,
  selectedTarget = null,
  aoeHover = null,
  playerId = null,
  combat = null,
} = {}) {
  if (!spell) return '请选择法术'

  const isCantrip = spell.level === 0 || (cantrips || []).some(name => spellNameMatches(spell, name))
  if (!isCantrip && typeof available === 'function' && available(level) <= 0) return `没有可用的 ${level} 环法术位`

  const spellType = String(spell.type || '').toLowerCase()
  const isAoe = !!spell.aoe
  const template = isAoe ? getAoeTemplateType(spell) : null
  const needsSelectedTarget = !isAoe && (skillRequiresTarget(spell) || ['damage', 'control'].includes(spellType))
  if (needsSelectedTarget && !selectedTarget) return '请先选择一个目标再施法'

  const selectedTargetId = getSelectedSpellTargetId({ spell, selectedTarget, playerId })
  const targetIssue = getSpellTargetEntityIssue({
    spell,
    targetId: selectedTargetId,
    entities: combat?.entities || {},
    playerId,
  })
  if (targetIssue) return targetIssue

  if (isAoe && template !== 'aura' && !aoeHover) {
    return '请先在战场上确认法术中心点'
  }

  if (isAoe && combat) {
    const targetIds = collectSpellCastTargetIds({ spell, selectedTarget, playerId, combat, aoeHover, level })
    if (!targetIds.length) return '法术范围内没有可结算目标'
  }

  return ''
}

export function collectSpellCastTargetIds({
  spell,
  selectedTarget = null,
  playerId = null,
  combat = null,
  aoeHover = null,
  level = spell?.level ?? 0,
  ignoreTargetCap = false,
} = {}) {
  if (!spell) return []
  if (!spell.aoe) {
    const target = spell.type === 'heal' ? (selectedTarget || playerId) : selectedTarget
    return target ? [target] : []
  }

  const entityPositions = combat?.entity_positions || {}
  const entities = combat?.entities || {}
  const playerPos = playerId ? entityPositions[playerId] : null
  const centerKey = aoeHover || getAoePreviewCenterKey({
    selectedTarget,
    entityPositions,
    playerPos,
  })
  const cells = buildAoeCells({
    aoePreview: buildSpellAoePreview(spell),
    aoeHover: centerKey,
    origin: playerPos,
  })
  if (!cells.ring.size) return []

  const targetIds = Object.entries(entityPositions)
    .filter(([, pos]) => pos && cells.ring.has(`${pos.x}_${pos.y}`))
    .filter(([entityId]) => {
      const entity = entities[entityId]
      if (!entity || isCombatEntityDead(entity)) return false
      if (spell.type === 'heal') return !entity.is_enemy
      return true
    })
    .map(([entityId]) => entityId)
  const maxTargets = getSpellMaxTargets(spell, level)
  return maxTargets && !ignoreTargetCap ? targetIds.slice(0, maxTargets) : targetIds
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
  updated = applyEntityStateUpdates(updated, result.target_results || [])
  updated = applyEntityStateUpdates(updated, result.resurrection_results || [])
  return updated
}

export function formatWeaponResourceLog(resource = null) {
  if (!resource?.consumed || !resource.weapon) return ''
  if (resource.resource_type === 'ammunition') {
    const remaining = resource.ammo_remaining ?? resource.ammo
    return remaining !== null && remaining !== undefined
      ? `${resource.weapon} 弹药 -1，剩余 ${remaining}`
      : `${resource.weapon} 弹药 -1`
  }
  if (resource.resource_type === 'thrown_weapon') {
    return resource.weapon_removed
      ? `投出 ${resource.weapon}，背包中移除 1 件`
      : `投出 ${resource.weapon}`
  }
  return ''
}

export function applyWeaponResourceToCombat(combat, entityId, resource = null) {
  if (!combat || !entityId || !resource?.consumed || !resource.weapon) return combat
  const entity = combat.entities?.[entityId]
  const weapons = entity?.equipment?.weapons
  if (!entity || !Array.isArray(weapons)) return combat

  let nextWeapons = weapons
  let changed = false

  if (resource.resource_type === 'ammunition' && resource.ammo_remaining !== undefined) {
    let updatedOne = false
    nextWeapons = weapons.map(weapon => {
      if (!updatedOne && weapon?.name === resource.weapon) {
        updatedOne = true
        changed = true
        return { ...weapon, ammo: resource.ammo_remaining }
      }
      return weapon
    })
  } else if (resource.resource_type === 'thrown_weapon' && resource.weapon_removed) {
    const equippedIndex = weapons.findIndex(weapon => weapon?.name === resource.weapon && weapon?.equipped)
    const fallbackIndex = weapons.findIndex(weapon => weapon?.name === resource.weapon)
    const removeIndex = equippedIndex >= 0 ? equippedIndex : fallbackIndex
    if (removeIndex >= 0) {
      const removedWasEquipped = !!weapons[removeIndex]?.equipped
      nextWeapons = weapons.filter((_, index) => index !== removeIndex)
      if (removedWasEquipped && !nextWeapons.some(weapon => weapon?.equipped)) {
        const replacementIndex = nextWeapons.findIndex(weapon => weapon?.name === resource.weapon)
        if (replacementIndex >= 0) {
          nextWeapons = nextWeapons.map((weapon, index) => (
            index === replacementIndex ? { ...weapon, equipped: true } : weapon
          ))
        }
      }
      changed = true
    }
  }

  if (!changed) return combat

  return {
    ...combat,
    entities: {
      ...combat.entities,
      [entityId]: {
        ...entity,
        equipment: {
          ...(entity.equipment || {}),
          weapons: nextWeapons,
        },
      },
    },
  }
}

export function getEquippedWeaponResourceSummary(character = null) {
  const weapons = character?.equipment?.weapons || []
  if (!Array.isArray(weapons) || weapons.length === 0) return null

  const ammoWeapon = weapons.find(weapon => weapon?.equipped && weapon?.ammo !== undefined)
    || weapons.find(weapon => weapon?.ammo !== undefined)
  if (ammoWeapon) {
    return { label: ammoWeapon.name, value: `弹药 ${ammoWeapon.ammo}` }
  }

  const thrownWeapon = weapons.find(weapon => weapon?.equipped && hasThrownProperty(weapon))
    || weapons.find(hasThrownProperty)
  if (!thrownWeapon?.name) return null

  const remaining = weapons.filter(weapon => weapon?.name === thrownWeapon.name).length
  return { label: thrownWeapon.name, value: `投掷 ${remaining}` }
}

function hasThrownProperty(weapon = {}) {
  const properties = weapon.properties || []
  if (typeof properties === 'string') return properties.toLowerCase().includes('thrown')
  return properties.some(prop => String(prop || '').toLowerCase().includes('thrown'))
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
 * 生成 AoE 预览格：支持 sphere/cone/line/cube/aura 等模板。
 *
 * @param {{ aoePreview: { radius?: number, template?: string, size?: number } | null, aoeHover: string | null, origin?: {x:number,y:number} | null }} args
 * @returns {{ center:string|null, ring:Set<string>, template:string|null }}
 */
export function buildAoeCells({ aoePreview, aoeHover, origin = null }) {
  const out = { center: null, ring: new Set(), template: null }
  if (!aoePreview || !aoeHover) return out

  const template = aoePreview.template || 'sphere'
  out.template = template
  const [hx, hy] = aoeHover.split('_').map(Number)
  const originPos = origin && Number.isFinite(origin.x) && Number.isFinite(origin.y)
    ? { x: Number(origin.x), y: Number(origin.y) }
    : null
  const center = template === 'aura' && originPos ? originPos : { x: hx, y: hy }
  const cx = center.x
  const cy = center.y
  const radius = aoePreview.radius || 1

  out.center = `${cx}_${cy}`
  if (template === 'cube') {
    const half = Math.max(0, Math.floor(((aoePreview.size || radius || 1) - 1) / 2))
    for (let dy = -half; dy <= half; dy++) {
      for (let dx = -half; dx <= half; dx++) out.ring.add(`${cx + dx}_${cy + dy}`)
    }
    return out
  }

  if ((template === 'cone' || template === 'line') && originPos) {
    const dir = normalizeTemplateDirection({ from: originPos, to: { x: hx, y: hy } })
    if (!dir) return out
    for (let y = originPos.y - radius; y <= originPos.y + radius; y++) {
      for (let x = originPos.x - radius; x <= originPos.x + radius; x++) {
        if (x === originPos.x && y === originPos.y) continue
        if (template === 'line' && isPointOnLineTemplate({ x, y, origin: originPos, dir, length: radius })) {
          out.ring.add(`${x}_${y}`)
        }
        if (template === 'cone' && isPointInConeTemplate({ x, y, origin: originPos, dir, length: radius })) {
          out.ring.add(`${x}_${y}`)
        }
      }
    }
    return out
  }

  for (let dy = -radius; dy <= radius; dy++) {
    for (let dx = -radius; dx <= radius; dx++) {
      const d = Math.sqrt(dx * dx + dy * dy)
      if (d <= radius + 0.5) out.ring.add(`${cx + dx}_${cy + dy}`)
    }
  }
  return out
}

function normalizeTemplateDirection({ from, to }) {
  const dx = Math.sign((to?.x ?? from.x) - from.x)
  const dy = Math.sign((to?.y ?? from.y) - from.y)
  if (dx === 0 && dy === 0) return null
  return { x: dx, y: dy }
}

function templateProjection({ x, y, origin, dir }) {
  const dx = x - origin.x
  const dy = y - origin.y
  const dirLength = Math.sqrt(dir.x * dir.x + dir.y * dir.y)
  const distance = Math.sqrt(dx * dx + dy * dy)
  const forward = (dx * dir.x + dy * dir.y) / dirLength
  const alignment = distance ? forward / distance : 0
  const lateral = Math.sqrt(Math.max(0, distance * distance - forward * forward))
  return { distance, forward, alignment, lateral }
}

function isPointOnLineTemplate({ x, y, origin, dir, length }) {
  const { forward, lateral } = templateProjection({ x, y, origin, dir })
  return forward > 0 && forward <= length + 0.5 && lateral <= 0.55
}

function isPointInConeTemplate({ x, y, origin, dir, length }) {
  const { distance, forward, alignment } = templateProjection({ x, y, origin, dir })
  return forward > 0 && distance <= length + 0.5 && alignment >= 0.55
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
  const objectives = new Set()
  const terrainDetails = {}
  for (const [key, value] of Object.entries(gridData)) {
    const terrain = getGridTerrainKind(value)
    if (['wall', 'cover', 'half_cover', 'three_quarters_cover', 'total_cover', 'blocking', 'blocker', 'opaque'].includes(terrain)) {
      walls.add(key)
    } else if (['hazard', 'difficult', 'difficult_terrain'].includes(terrain)) {
      hazards.add(key)
    } else if (terrain === 'objective') {
      objectives.add(key)
    }
    if (terrain) terrainDetails[key] = buildGridTerrainDetail(key, value, terrain)
  }
  return { walls, hazards, objectives, terrainDetails }
}

export function buildGridTerrainDetail(key, value, terrain = getGridTerrainKind(value)) {
  const data = value && typeof value === 'object' ? value : {}
  const label = data.name || data.label || data.title || terrainLabel(terrain)
  return {
    key,
    terrain,
    label,
    damageDice: data.damage_dice || data.damage || '',
    saveDc: data.save_dc || data.dc || '',
    saveAbility: data.save_ability || data.ability || '',
    coverLevel: data.cover_level || data.cover || '',
  }
}

export function getGridTerrainKind(value) {
  if (typeof value === 'string') return normalizeGridTerrainKind(value)
  if (!value || typeof value !== 'object') return ''
  if (value.hazard === true) return 'hazard'
  if (value.objective === true) return 'objective'
  const raw = value.terrain || value.type || value.kind || value.category || ''
  if (raw) return normalizeGridTerrainKind(raw)
  if (value.cover || value.cover_bonus || value.cover_level) return 'cover'
  return ''
}

function normalizeGridTerrainKind(value) {
  return String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_')
}

function terrainLabel(terrain) {
  if (terrain === 'total_cover') return 'Total cover'
  if (['wall', 'blocking', 'blocker', 'opaque'].includes(terrain)) return 'Wall'
  if (['cover', 'half_cover', 'three_quarters_cover'].includes(terrain)) return 'Cover'
  if (['difficult', 'difficult_terrain'].includes(terrain)) return 'Difficult terrain'
  if (terrain === 'hazard') return 'Hazard'
  if (terrain === 'objective') return 'Objective'
  return terrain || 'Terrain'
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

const AUTO_HIT_DAMAGE_SPELL_KEYS = new Set([
  normalizeSpellKey('Magic Missile'),
  normalizeSpellKey('魔法飞弹'),
  normalizeSpellKey('榄旀硶椋炲脊'),
])

export function spellRequiresAttackRoll(spell = {}) {
  if (String(spell?.type || '').toLowerCase() !== 'damage') return false
  if (spell?.save) return false
  const keys = [spell?.name, spell?.name_en].map(normalizeSpellKey).filter(Boolean)
  return !keys.some(key => AUTO_HIT_DAMAGE_SPELL_KEYS.has(key))
}

/**
 * 后端技能栏为空时使用本地兜底。
 */
export function getCombatSkillBar(skillBar) {
  return skillBar && skillBar.length ? skillBar : DEFAULT_SKILL_BAR
}

const TARGET_REQUIRED_SKILL_KEYS = new Set(['atk', 'sneak', 'shove', 'grapple', 'off_attack', 'firebolt', 'sacred_flame'])
const TARGET_REQUIRED_TYPES = new Set(['ally', 'enemy', 'creature', 'character', 'object', 'entity', 'token', 'target'])
const TARGET_NOT_REQUIRED_TYPES = new Set(['self', 'self_only', 'self-target', 'self_target', 'selftarget', 'aura', 'none'])

function normalizeTargetHint(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
}

function parseBooleanishTargetRequirement(value) {
  if (value === undefined || value === null || value === '') return null
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value !== 0

  const normalized = normalizeTargetHint(value)
  if ([
    'true',
    'yes',
    'required',
    'require',
    'needs_target',
    'need_target',
    'target_required',
    'target_needed',
    'target_selection_required',
  ].includes(normalized)) return true
  if ([
    'false',
    'no',
    'optional',
    'self',
    'self_only',
    'self_target',
    'selftarget',
    'aura',
    'none',
  ].includes(normalized)) return false
  return null
}

function skillRequiresTarget(skill = {}) {
  const targeting = skill.targeting && typeof skill.targeting === 'object' ? skill.targeting : {}
  const explicit = parseBooleanishTargetRequirement(
    skill.requires_target
    ?? skill.requiresTarget
    ?? skill.target_required
    ?? skill.targetRequired
    ?? skill.needs_target
    ?? skill.needsTarget
    ?? targeting.requires_target
    ?? targeting.requiresTarget
    ?? targeting.target_required
    ?? targeting.targetRequired
    ?? targeting.needs_target
    ?? targeting.needsTarget,
  )
  if (explicit !== null) return explicit

  const targetType = normalizeTargetHint(
    skill.target_type
    ?? skill.targetType
    ?? skill.target
    ?? targeting.target_type
    ?? targeting.targetType
    ?? targeting.type,
  )
  if (TARGET_NOT_REQUIRED_TYPES.has(targetType)) return false
  if (TARGET_REQUIRED_TYPES.has(targetType)) return true
  return TARGET_REQUIRED_SKILL_KEYS.has(skill.k)
}

export function getSkillUnavailableReason({
  skill,
  turnState,
  isPlayerTurn = true,
  syncBlocked = false,
  isProcessing = false,
  selectedTarget = null,
} = {}) {
  if (!skill) return ''
  if (syncBlocked) return '等待战斗同步恢复'
  if (!isPlayerTurn) return '等待你的回合'
  if (isProcessing) return '正在结算上一项动作'
  if (skill.available === false) return skill.reason || '当前不可用'

  const key = skill.k
  const kind = skill.kind
  const needsTarget = skillRequiresTarget(skill)
  if (needsTarget && !selectedTarget) return '需要先选择目标'

  if (kind === 'bonus' || key === 'off_attack') {
    if (turnState?.bonus_action_used) return '本回合附赠动作已使用'
    if (key === 'off_attack' && (turnState?.attacks_made ?? 0) <= 0) return '需要先完成主手攻击'
  }

  const consumesAction = ['attack', 'spell', 'action', 'item'].includes(kind) || ['dash', 'disg', 'dodge', 'help'].includes(key)
  if (consumesAction && turnState?.action_used) return '本回合动作已使用'
  if (kind === 'move' && key !== 'dash' && (turnState?.movement_max ?? 0) - (turnState?.movement_used ?? 0) <= 0) {
    return '本回合移动力已用尽'
  }
  if (kind === 'reaction' && turnState?.reaction_used) return '本回合反应已使用'
  return ''
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
