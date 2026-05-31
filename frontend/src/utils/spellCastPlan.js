import {
  aoeRadiusCells,
  collectSpellCastTargetIds,
  getAoeTemplateType,
  getSpellMaxTargets,
  spellNameMatches,
} from './combat'

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
    chips.push({ key: 'enemy', label: `Enemies ${groups.enemy.length}`, tone: 'danger', title: namesTitle(groups.enemy) })
  }
  if (groups.ally.length) {
    chips.push({ key: 'ally', label: `Allies ${groups.ally.length}`, tone: friendlyRisk ? 'warning' : 'good', title: namesTitle(groups.ally) })
  }
  if (groups.self.length) {
    chips.push({ key: 'self', label: 'Self', tone: friendlyRisk ? 'warning' : 'good', title: namesTitle(groups.self) })
  }
  if (friendlyRisk) {
    chips.push({ key: 'friendly-fire', label: 'Friendly fire', tone: 'warning', title: 'A damage AoE includes allies or the caster.' })
  }
  return {
    total: targetIds.length,
    enemies: groups.enemy.length,
    allies: groups.ally.length,
    self: groups.self.length,
    risk: friendlyRisk ? 'friendly_fire' : '',
    chips,
  }
}

function casterDerived(combat, playerId) {
  const caster = combat?.entities?.[playerId] || combat?.player || combat?.actor || {}
  return caster?.derived || caster || {}
}

function readFiniteNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatSignedNumber(value) {
  const number = readFiniteNumber(value)
  if (number === null) return ''
  return number >= 0 ? `+${number}` : `${number}`
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

function buildRuleRows({ spell, combat, playerId, castLevel, baseLevel }) {
  const rows = []
  const derived = casterDerived(combat, playerId)
  const save = spellSaveAbility(spell)
  if (save) {
    const dc = readFiniteNumber(spell.save_dc ?? spell.dc ?? derived.spell_save_dc)
    rows.push({
      label: '判定',
      value: [
        `${String(save).toUpperCase()} save`,
        dc !== null ? `DC ${dc}` : '',
        spellHasHalfOnSave(spell) ? 'success halves damage' : 'success negates/reduces effect',
      ].filter(Boolean).join(' · '),
    })
  } else if (spellRequiresAttackRoll(spell)) {
    const attackBonus = formatSignedNumber(spell.spell_attack_bonus ?? spell.attack_bonus ?? derived.spell_attack_bonus)
    rows.push({
      label: '判定',
      value: `Spell attack${attackBonus ? ` ${attackBonus}` : ''}`,
    })
  }

  if (spellRequiresConcentration(spell)) {
    rows.push({
      label: '维持',
      value: 'Concentration; taking damage may force a check',
    })
  }

  const levelsUp = Math.max(0, asLevel(castLevel, 0) - asLevel(baseLevel, 0))
  if (levelsUp > 0) {
    const upcast = upcastDiceLabel(spell)
    rows.push({
      label: '升环',
      value: upcast
        ? `+${levelsUp} slot level${levelsUp === 1 ? '' : 's'} · ${upcast} per level`
        : `+${levelsUp} slot level${levelsUp === 1 ? '' : 's'} · no extra scaling recorded`,
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

function effectLabel(spell = {}) {
  const parts = []
  if (spell.damage) parts.push(`伤害 ${spell.damage}`)
  if (spell.heal) parts.push(`治疗 ${spell.heal}`)
  if (spell.save || spell.saving_throw || spell.save_ability) {
    parts.push(`豁免 ${spell.save || spell.saving_throw || spell.save_ability}`)
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

export function buildSpellCastPlan({
  spell,
  level = 0,
  cantrips = [],
  slots = {},
  selectedTarget = null,
  playerId = null,
  combat = null,
  aoeHover = null,
  disabledReason = '',
} = {}) {
  if (!spell) {
    return {
      tone: 'empty',
      status: '等待选择',
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
        : `${castLevel} 环法术位（剩余 ${slots?.[slotKey(castLevel)] ?? 0}）`,
    },
    { label: '效果', value: effectLabel(spell) },
  ]
  rows.push(...buildRuleRows({ spell, combat, playerId, castLevel, baseLevel }))

  let aoeBreakdown = null

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
    aoeBreakdown = buildAoeBreakdown({ spell, combat, targetIds, playerId })
    if (maxTargets) {
      aoeBreakdown.limit = maxTargets
      aoeBreakdown.excluded = excludedTargetIds.length
      aoeBreakdown.chips.push({
        key: 'target-limit',
        label: `Limit ${targetIds.length}/${maxTargets}`,
        tone: excludedTargetIds.length ? 'warning' : 'good',
        title: excludedTargetIds.length
          ? `Targets beyond the cap are excluded: ${namesTitle(excludedNames)}`
          : 'Current targets fit within the spell target cap.',
      })
    }
    rows.push({
      label: '区域',
      value: `${templateLabel(template)} · ${aoeRadiusCells(spell) * 5} 尺 · 中心 ${centerLabel(aoeHover, template)}`,
    })
    rows.push({
      label: '命中单位',
      value: targetIds.length
        ? `${targetIds.length}${maxTargets ? `/${maxTargets}` : ''} 个：${names.join('、')}`
        : (aoeHover ? '0 个' : '待确认'),
      tone: targetIds.length ? 'ready' : 'warning',
    })
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
    rows.push({
      label: '目标',
      value: targetId ? entityName(combat, targetId) : `需要选择${targetKindLabel(spell)}`,
      tone: targetId ? 'ready' : 'warning',
    })
  }

  rows.push({
    label: '状态',
    value: disabledReason || '可施放',
    tone: disabledReason ? 'blocked' : 'ready',
  })

  return {
    tone: disabledReason ? 'blocked' : 'ready',
    status: disabledReason ? '无法施放' : '可施放',
    rows,
    aoeBreakdown,
  }
}
