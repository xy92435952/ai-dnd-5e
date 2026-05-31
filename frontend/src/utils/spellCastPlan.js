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
    const maxTargets = getSpellMaxTargets(spell, castLevel || baseLevel)
    const names = targetIds.map(id => entityName(combat, id))
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
  }
}
