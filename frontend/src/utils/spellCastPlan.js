import {
  aoeRadiusCells,
  collectSpellCastTargetIds,
  getAoeTemplateType,
  getSpellMaxTargets,
  spellNameMatches,
} from './combat'
import { buildConditionImpactTags } from './conditionRules'

const SLOT_LABELS = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th']

function slotKey(level) {
  return SLOT_LABELS[level - 1] || `${level}th`
}

function asLevel(value, fallback = 0) {
  const level = Number(value)
  return Number.isFinite(level) && level > 0 ? Math.floor(level) : fallback
}

function isCantripSpell(spell, cantrips = []) {
  return asLevel(spell?.level, 0) === 0 || cantrips.some(name => spellNameMatches(spell, name))
}

function entityName(combat, entityId) {
  const entity = combat?.entities?.[entityId]
  return entity?.name || entityId || '未选择'
}

function entityById(combat, entityId) {
  return entityId ? combat?.entities?.[entityId] || null : null
}

function entityGroup(combat, entityId, playerId) {
  if (String(entityId) === String(playerId)) return 'self'
  const entity = combat?.entities?.[entityId]
  return entity?.is_enemy ? 'enemy' : 'ally'
}

function namesTitle(names) {
  return names.length ? names.join(' / ') : ''
}

function buildAoeBreakdown({ spell, combat, targetIds, playerId }) {
  const groups = { enemy: [], ally: [], self: [] }
  for (const id of targetIds) {
    const group = entityGroup(combat, id, playerId)
    groups[group].push(entityName(combat, id))
  }
  const isDamage = String(spell?.type || '').toLowerCase() === 'damage'
  const friendlyRisk = isDamage && (groups.ally.length > 0 || groups.self.length > 0)
  const chips = []
  if (groups.enemy.length) {
    chips.push({ key: 'enemy', label: `敌方 ${groups.enemy.length}`, tone: 'danger', title: namesTitle(groups.enemy) })
  }
  if (groups.ally.length) {
    chips.push({ key: 'ally', label: `友方 ${groups.ally.length}`, tone: friendlyRisk ? 'warning' : 'good', title: namesTitle(groups.ally) })
  }
  if (groups.self.length) {
    chips.push({ key: 'self', label: '自身', tone: friendlyRisk ? 'warning' : 'good', title: namesTitle(groups.self) })
  }
  if (friendlyRisk) {
    chips.push({ key: 'friendly-fire', label: '误伤风险', tone: 'warning', title: '伤害范围包含友方或施法者。' })
  }
  return {
    total: targetIds.length,
    enemies: groups.enemy.length,
    allies: groups.ally.length,
    self: groups.self.length,
    groups,
    risk: friendlyRisk ? 'friendly_fire' : '',
    chips,
  }
}

function buildTargetImpactChips(combat, targetId) {
  const entity = entityById(combat, targetId)
  return buildConditionImpactTags(entity?.conditions || [], entity?.condition_durations || {})
    .slice(0, 4)
    .map(tag => ({
      key: `condition-${tag.key}`,
      label: tag.label,
      tone: tag.tone,
      title: tag.title,
    }))
}

function casterDerived(combat, playerId) {
  const caster = combat?.entities?.[playerId] || combat?.player || combat?.actor || {}
  return caster?.derived || caster || {}
}

function readFiniteNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function slotRemaining(slots, level) {
  const value = readFiniteNumber(slots?.[slotKey(level)])
  return value === null ? 0 : Math.max(0, value)
}

function slotAfterCast(slots, level) {
  return Math.max(0, slotRemaining(slots, level) - 1)
}

function slotCostLabel(slots, level) {
  return `${level} 环法术位（剩余 ${slotRemaining(slots, level)} -> ${slotAfterCast(slots, level)}）`
}

function slotPreflightLabel(slots, level) {
  return `${level} 环 · ${slotRemaining(slots, level)} -> ${slotAfterCast(slots, level)}`
}

function formatSignedNumber(value) {
  const number = readFiniteNumber(value)
  if (number === null) return ''
  return number >= 0 ? `+${number}` : `${number}`
}

function targetArmorClass(entity = null) {
  return readFiniteNumber(entity?.ac ?? entity?.derived?.ac)
}

function spellAttackBonusValue(spell = {}, combat = null, playerId = null) {
  const derived = casterDerived(combat, playerId)
  return readFiniteNumber(spell.spell_attack_bonus ?? spell.attack_bonus ?? derived.spell_attack_bonus)
}

export function buildSpellAttackDefenseSummary({ spell, combat, playerId, targetId }) {
  if (!spellRequiresAttackRoll(spell)) return null
  const target = entityById(combat, targetId)
  const ac = targetArmorClass(target)
  if (ac === null) return null

  const parts = [`AC ${ac}`]
  const compactParts = [`AC ${ac}`]
  const attackBonus = spellAttackBonusValue(spell, combat, playerId)
  let hitChance = null
  if (attackBonus !== null) {
    const needed = ac - attackBonus
    const displayedNeeded = needed > 20 ? '自然20' : `${Math.max(2, needed)}+`
    const successRolls = Math.max(1, Math.min(19, 21 - needed))
    hitChance = Math.round((successRolls / 20) * 100)
    parts.push(`d20 需 ${displayedNeeded}`)
    parts.push(`约 ${hitChance}%`)
    compactParts.push(displayedNeeded)
    compactParts.push(`${hitChance}%`)
  }

  const value = parts.join(' · ')
  return {
    value,
    compactLabel: compactParts.join(' · '),
    hitChance,
    tone: hitChance !== null && hitChance < 50 ? 'warning' : 'good',
    title: `法术攻击基础估算：${value}。未包含临时掩护、优势/劣势或反应修正。`,
  }
}

function spellAttackDefenseRow({ spell, combat, playerId, targetId }) {
  const summary = buildSpellAttackDefenseSummary({ spell, combat, playerId, targetId })
  if (!summary) return null

  return {
    label: '目标防御',
    value: summary.value,
  }
}

function spellSaveAbility(spell = {}) {
  return spell.save || spell.saving_throw || spell.save_ability || ''
}

function spellHasHalfOnSave(spell = {}) {
  if (spell.half_on_save || spell.halfOnSave) return true
  return /half on save|success.*half|\u8c41\u514d\u6210\u529f.*\u51cf\u534a|\u6210\u529f.*\u51cf\u534a/i.test(`${spell.desc || ''} ${spell.description || ''}`)
}

function spellRequiresAttackRoll(spell = {}) {
  if (spell.attack_roll || spell.requires_attack_roll || spell.spell_attack) return true
  return /spell attack|ranged spell attack|melee spell attack|\u6cd5\u672f\u653b\u51fb|\u6cd5\u672f\u653b\u51fb\u68c0\u5b9a/i.test(`${spell.name || ''} ${spell.name_en || ''} ${spell.desc || ''} ${spell.description || ''}`)
}

function spellRequiresConcentration(spell = {}) {
  return !!spell.concentration || /concentration|\u4e13\u6ce8/i.test(`${spell.desc || ''} ${spell.description || ''}`)
}

function upcastDiceLabel(spell = {}) {
  return spell.upcast_dice || spell.upcastDice || spell.upcast || spell.higher_level || ''
}

function abilityLabel(value) {
  const key = String(value || '').trim().toLowerCase()
  return ({
    str: '力量',
    strength: '力量',
    dex: '敏捷',
    dexterity: '敏捷',
    con: '体质',
    constitution: '体质',
    int: '智力',
    intelligence: '智力',
    wis: '感知',
    wisdom: '感知',
    cha: '魅力',
    charisma: '魅力',
  })[key] || String(value || '').toUpperCase()
}

function buildRuleRows({ spell, combat, playerId, castLevel, baseLevel }) {
  const rows = []
  const derived = casterDerived(combat, playerId)
  const save = spellSaveAbility(spell)
  if (save) {
    const dc = readFiniteNumber(spell.save_dc ?? spell.dc ?? derived.spell_save_dc)
    rows.push({
      label: '判定',
      value: [
        `${abilityLabel(save)}豁免`,
        dc !== null ? `DC ${dc}` : '',
        spellHasHalfOnSave(spell) ? '成功减半' : '成功避免/减轻效果',
      ].filter(Boolean).join(' · '),
    })
  } else if (spellRequiresAttackRoll(spell)) {
    const attackBonus = formatSignedNumber(spell.spell_attack_bonus ?? spell.attack_bonus ?? derived.spell_attack_bonus)
    rows.push({
      label: '判定',
      value: `法术攻击${attackBonus ? ` ${attackBonus}` : ''}`,
    })
  }

  if (spellRequiresConcentration(spell)) {
    rows.push({
      label: '维持',
      value: '专注；受到伤害可能触发专注检定',
    })
  }

  const levelsUp = Math.max(0, asLevel(castLevel, 0) - asLevel(baseLevel, 0))
  if (levelsUp > 0) {
    const upcast = upcastDiceLabel(spell)
    rows.push({
      label: '升环',
      value: upcast
        ? `+${levelsUp} 环 · 每环 ${upcast}`
        : `+${levelsUp} 环 · 未记录额外成长`,
    })
  }

  return rows
}

function targetKindLabel(spell = {}) {
  const target = String(spell.target_type || spell.targetType || spell.target || spell.targets || '').toLowerCase()
  if (/self|自身/.test(target)) return '自身'
  if (/ally|friend|willing|队友|友方/.test(target)) return '队友或自己'
  if (/enemy|hostile|foe|敌/.test(target)) return '敌方目标'
  if (String(spell.type || '').toLowerCase() === 'heal') return '队友或自己'
  return '目标'
}

function templateLabel(template) {
  return ({
    sphere: '球形区域',
    cone: '锥形区域',
    line: '直线区域',
    cube: '立方区域',
    aura: '自身光环',
  })[template] || '区域'
}

function centerLabel(aoeHover, template) {
  if (template === 'aura') return '自身'
  if (!aoeHover) return '待确认'
  const [x, y] = String(aoeHover).split('_')
  return x !== undefined && y !== undefined ? `${x}, ${y}` : String(aoeHover)
}

function areaAnchorLabel(aoeHover, template) {
  const label = centerLabel(aoeHover, template)
  if (template === 'aura') return label
  if (template === 'cone' || template === 'line') return `方向点 ${label}`
  return `中心 ${label}`
}

function readGridPoint(keyOrPoint) {
  if (!keyOrPoint) return null
  if (typeof keyOrPoint === 'object' && Number.isFinite(Number(keyOrPoint.x)) && Number.isFinite(Number(keyOrPoint.y))) {
    return { x: Number(keyOrPoint.x), y: Number(keyOrPoint.y) }
  }
  const [x, y] = String(keyOrPoint).split('_').map(Number)
  return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null
}

function directionName(from, to) {
  const dx = Math.sign((to?.x ?? from?.x) - from.x)
  const dy = Math.sign((to?.y ?? from?.y) - from.y)
  if (!dx && !dy) return ''
  const vertical = dy < 0 ? '北' : dy > 0 ? '南' : ''
  const horizontal = dx < 0 ? '西' : dx > 0 ? '东' : ''
  return `${vertical}${horizontal}` || ''
}

function areaDirectionLabel({ template, aoeHover, combat, playerId }) {
  if (template !== 'cone' && template !== 'line') return ''
  const from = readGridPoint(combat?.entity_positions?.[playerId])
  const to = readGridPoint(aoeHover)
  if (!from || !to) return ''
  const direction = directionName(from, to)
  if (!direction) return ''
  return `${direction} · 从 ${entityName(combat, playerId) || '施法者'} 指向 ${to.x}, ${to.y}`
}

function placementLabel({ template, aoeHover, aoeLockedCenter }) {
  if (template === 'aura') return '自身光环'
  if (aoeLockedCenter) return `已锁定 · ${areaAnchorLabel(aoeLockedCenter, template)}`
  if (aoeHover) return `预览中 · ${areaAnchorLabel(aoeHover, template)}；点击格子可锁定`
  return '待确认'
}

function effectLabel(spell = {}) {
  const parts = []
  if (spell.damage) parts.push(`伤害 ${spell.damage}`)
  if (spell.heal) parts.push(`治疗 ${spell.heal}`)
  if (spell.save || spell.saving_throw || spell.save_ability) {
    parts.push(`${abilityLabel(spell.save || spell.saving_throw || spell.save_ability)}豁免`)
  }
  if (spell.condition || spell.conditions) {
    const value = Array.isArray(spell.conditions) ? spell.conditions.join('/') : spell.condition || spell.conditions
    parts.push(`状态 ${value}`)
  }
  return parts.join(' · ') || spell.effect || spell.school || '效果见法术描述'
}

function nonAoeTargetId(spell, selectedTarget, playerId) {
  if (!spell) return null
  const spellType = String(spell.type || '').toLowerCase()
  if (spellType === 'heal') return selectedTarget || playerId || null
  if (/self|自身/.test(String(spell.target_type || spell.target || '').toLowerCase())) return playerId || selectedTarget
  return selectedTarget || null
}

function aoePreflightTarget({ aoeBreakdown, maxTargets, hasPlacement }) {
  if (!hasPlacement) {
    return {
      key: 'target',
      label: '目标',
      value: '待确认落点',
      tone: 'warning',
      title: '先在战场上选择或锁定范围落点。',
    }
  }
  if (!aoeBreakdown?.total) {
    return {
      key: 'target',
      label: '目标',
      value: '影响 0 个',
      tone: 'warning',
      title: '当前范围内没有可结算目标。',
    }
  }

  const groups = []
  if (aoeBreakdown.enemies) groups.push(`敌方 ${aoeBreakdown.enemies}`)
  if (aoeBreakdown.allies) groups.push(`友方 ${aoeBreakdown.allies}`)
  if (aoeBreakdown.self) groups.push('自身')
  const total = `影响 ${aoeBreakdown.total}${maxTargets ? `/${maxTargets}` : ''} 个`
  return {
    key: 'target',
    label: '目标',
    value: groups.length ? `${total}：${groups.join(' / ')}` : total,
    tone: aoeBreakdown.risk ? 'warning' : 'ready',
    title: aoeBreakdown.risk ? '伤害范围包含友方或施法者。' : '当前范围目标已可结算。',
  }
}

function buildAoeWarnings({ spell, aoeBreakdown, hasPlacement, excludedNames = [] }) {
  const warnings = []
  if (!hasPlacement) {
    warnings.push({
      key: 'placement',
      label: '落点',
      detail: '先在战场上选择范围中心或方向点。',
      tone: 'warning',
    })
    return warnings
  }

  if (!aoeBreakdown?.total) {
    warnings.push({
      key: 'empty',
      label: '空范围',
      detail: '当前范围内没有可结算目标。',
      tone: 'warning',
    })
  }

  const isDamage = String(spell?.type || '').toLowerCase() === 'damage'
  if (isDamage && aoeBreakdown?.risk === 'friendly_fire') {
    const affected = [
      ...aoeBreakdown.groups.ally,
      ...aoeBreakdown.groups.self,
    ].filter(Boolean).join('、')
    warnings.push({
      key: 'friendly-fire',
      label: '误伤',
      detail: affected ? `伤害范围包含友方或施法者：${affected}` : '伤害范围包含友方或施法者。',
      tone: 'warning',
    })
  }

  if (excludedNames.length) {
    warnings.push({
      key: 'target-limit',
      label: '上限',
      detail: `超过目标上限，${excludedNames.join('、')} 不会结算。`,
      tone: 'warning',
    })
  }

  return warnings
}

export function buildSpellCastPlan({
  spell,
  level = 0,
  cantrips = [],
  slots = {},
  selectedTarget = null,
  playerId = null,
  combat = null,
  aoeHover = null,
  aoeLockedCenter = null,
  disabledReason = '',
} = {}) {
  if (!spell) {
    return {
      tone: 'empty',
      status: '等待选择',
      preflight: [
        { key: 'next', label: '下一步', value: '选择法术', tone: 'warning' },
      ],
      rows: [
        { label: '下一步', value: '先从列表选择一个法术' },
        { label: '目标', value: '选择后会显示消耗、目标与影响范围' },
      ],
    }
  }

  const cantrip = isCantripSpell(spell, cantrips)
  const baseLevel = asLevel(spell.level, 0)
  const castLevel = cantrip ? 0 : Math.max(asLevel(level, baseLevel || 1), baseLevel || 1)
  const rows = [
    {
      label: '消耗',
      value: cantrip
        ? '戏法，无需法术位'
        : slotCostLabel(slots, castLevel),
    },
    { label: '效果', value: effectLabel(spell) },
  ]
  rows.push(...buildRuleRows({ spell, combat, playerId, castLevel, baseLevel }))

  let aoeBreakdown = null
  let aoePlacement = null
  let targetPreflight = null
  let targetImpactChips = []
  let warnings = []

  if (spell.aoe) {
    const template = getAoeTemplateType(spell)
    const targetIds = collectSpellCastTargetIds({
      spell,
      selectedTarget,
      playerId,
      combat,
      aoeHover,
      level: castLevel || baseLevel,
    })
    const uncappedTargetIds = collectSpellCastTargetIds({
      spell,
      selectedTarget,
      playerId,
      combat,
      aoeHover,
      level: castLevel || baseLevel,
      ignoreTargetCap: true,
    })
    const maxTargets = getSpellMaxTargets(spell, castLevel || baseLevel)
    const names = targetIds.map(id => entityName(combat, id))
    const excludedTargetIds = uncappedTargetIds.slice(targetIds.length)
    const excludedNames = excludedTargetIds.map(id => entityName(combat, id))
    const direction = areaDirectionLabel({ template, aoeHover, combat, playerId })
    const hasPlacement = Boolean(aoeHover) || template === 'aura'
    aoePlacement = {
      locked: Boolean(aoeLockedCenter),
      canReset: Boolean(aoeLockedCenter),
      label: placementLabel({ template, aoeHover, aoeLockedCenter }),
    }
    aoeBreakdown = buildAoeBreakdown({ spell, combat, targetIds, playerId })
    targetPreflight = aoePreflightTarget({ aoeBreakdown, maxTargets, hasPlacement })
    if (maxTargets) {
      aoeBreakdown.limit = maxTargets
      aoeBreakdown.excluded = excludedTargetIds.length
      aoeBreakdown.chips.push({
        key: 'target-limit',
        label: `上限 ${targetIds.length}/${maxTargets}`,
        tone: excludedTargetIds.length ? 'warning' : 'good',
        title: excludedTargetIds.length
          ? `超过上限的目标不会结算：${namesTitle(excludedNames)}`
          : '当前目标未超过法术上限。',
      })
    }
    warnings = buildAoeWarnings({ spell, aoeBreakdown, hasPlacement, excludedNames })
    rows.push({
      label: '区域',
      value: `${templateLabel(template)} · ${aoeRadiusCells(spell) * 5} 尺 · ${areaAnchorLabel(aoeHover, template)}`,
    })
    rows.push({
      label: '放置',
      value: placementLabel({ template, aoeHover, aoeLockedCenter }),
      tone: aoeHover || template === 'aura' ? 'ready' : 'warning',
    })
    if (direction) {
      rows.push({
        label: '方向',
        value: direction,
      })
    }
    rows.push({
      label: '命中单位',
      value: targetIds.length
        ? `${targetIds.length}${maxTargets ? `/${maxTargets}` : ''} 个：${names.join('、')}`
        : (aoeHover ? '0 个' : '待确认'),
      tone: targetIds.length ? 'ready' : 'warning',
    })
    if (aoeBreakdown.groups.enemy.length) {
      rows.push({
        label: '敌方',
        value: aoeBreakdown.groups.enemy.join('、'),
        tone: 'ready',
      })
    }
    if (aoeBreakdown.groups.ally.length) {
      rows.push({
        label: '友方',
        value: aoeBreakdown.groups.ally.join('、'),
        tone: String(spell.type || '').toLowerCase() === 'damage' ? 'warning' : 'ready',
      })
    }
    if (aoeBreakdown.groups.self.length) {
      rows.push({
        label: '自身',
        value: aoeBreakdown.groups.self.join('、'),
        tone: String(spell.type || '').toLowerCase() === 'damage' ? 'warning' : 'ready',
      })
    }
    if (maxTargets) {
      rows.push({
        label: '目标上限',
        value: excludedTargetIds.length
          ? `最多 ${maxTargets} 个；排除 ${excludedNames.join('、')}`
          : `最多 ${maxTargets} 个；当前 ${targetIds.length}`,
        tone: excludedTargetIds.length ? 'warning' : 'ready',
      })
    }
  } else {
    const targetId = nonAoeTargetId(spell, selectedTarget, playerId)
    targetImpactChips = buildTargetImpactChips(combat, targetId)
    targetPreflight = {
      key: 'target',
      label: '目标',
      value: targetId ? entityName(combat, targetId) : `需要选择${targetKindLabel(spell)}`,
      tone: targetId ? 'ready' : 'warning',
    }
    rows.push({
      label: '目标',
      value: targetId ? entityName(combat, targetId) : `需要选择${targetKindLabel(spell)}`,
      tone: targetId ? 'ready' : 'warning',
    })
    const defenseRow = spellAttackDefenseRow({ spell, combat, playerId, targetId })
    if (defenseRow) rows.push(defenseRow)
  }

  rows.push({
    label: '状态',
    value: disabledReason || '可施放',
    tone: disabledReason ? 'blocked' : 'ready',
  })

  return {
    tone: disabledReason ? 'blocked' : 'ready',
    status: disabledReason ? '无法施放' : '可施放',
    preflight: [
      {
        key: 'status',
        label: '状态',
        value: disabledReason || '可施放',
        tone: disabledReason ? 'blocked' : 'ready',
      },
      {
        key: 'cost',
        label: '消耗',
        value: cantrip ? '戏法' : slotPreflightLabel(slots, castLevel),
        tone: cantrip || slotRemaining(slots, castLevel) > 0 ? 'ready' : 'blocked',
      },
      targetPreflight,
    ].filter(Boolean),
    rows,
    aoeBreakdown,
    aoePlacement,
    targetImpactChips,
    warnings,
  }
}
