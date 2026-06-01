import { buildCombatRuleTags } from './combatRuleTags'

const ACTION_KINDS = new Set(['attack', 'spell', 'action', 'item', 'move'])
const BONUS_KINDS = new Set(['bonus', 'bonus_action'])

export function buildCombatActionCoach({
  isPlayerTurn = false,
  isProcessing = false,
  syncBlocked = false,
  turnState = {},
  skillBar = [],
  selectedTarget = null,
  selectedTargetEntity = null,
  prediction = null,
  moveMode = false,
  helpMode = false,
} = {}) {
  if (!isPlayerTurn || isProcessing || syncBlocked) {
    return { visible: false, items: [] }
  }

  const actionOpen = !turnState?.action_used
  const bonusOpen = !turnState?.bonus_action_used
  const reactionOpen = !turnState?.reaction_used
  const movementMax = readNumber(turnState?.movement_max, 6)
  const movementUsed = readNumber(turnState?.movement_used, 0)
  const movementLeft = Math.max(0, movementMax - movementUsed)
  const usableSkills = Array.isArray(skillBar) ? skillBar.filter(skill => skill?.available !== false) : []
  const hasActionOption = usableSkills.some(skill => ACTION_KINDS.has(skill.kind))
  const hasBonusOption = usableSkills.some(skill => BONUS_KINDS.has(skill.kind) || /bonus/i.test(String(skill.cost || '')))
  const targetNeeded = usableSkills.some(skill => skillNeedsTarget(skill))
  const hasTarget = Boolean(selectedTarget)
  const actionStatus = buildActionStatus({
    actionOpen,
    helpMode,
    hasTarget,
    targetNeeded,
    hasActionOption,
  })

  const items = [
    {
      key: 'action',
      label: '动作',
      value: actionStatus.value,
      tone: actionStatus.tone,
    },
    {
      key: 'move',
      label: '移动',
      value: moveMode ? '选格子' : `${movementLeft} 格`,
      tone: movementLeft > 0 ? moveMode ? 'warn' : 'ready' : 'spent',
    },
    {
      key: 'reaction',
      label: '反应',
      value: reactionOpen ? '保留' : '已用',
      tone: reactionOpen ? 'ready' : 'spent',
    },
    {
      key: 'finish',
      label: '结束',
      value: actionOpen || movementLeft > 0 ? '完成后结束' : '结束回合',
      tone: actionOpen || movementLeft > 0 ? '' : 'ready',
    },
  ]

  const targetItems = []
  if (helpMode) {
    targetItems.push({
      key: 'assist',
      label: '协助',
      value: actionOpen ? '选队友' : '动作已用',
      tone: actionOpen ? 'warn' : 'spent',
    })
  } else if (targetNeeded || selectedTargetEntity || hasTarget) {
    targetItems.push({
      key: 'target',
      label: '目标',
      value: hasTarget ? targetSummary(selectedTargetEntity, prediction) : '选目标',
      tone: hasTarget ? 'ready' : 'warn',
    })
    const sourceSummary = hasTarget ? attackRuleSourceSummary(prediction, selectedTargetEntity) : null
    if (sourceSummary) {
      targetItems.push({
        key: 'rules',
        label: '来源',
        value: sourceSummary.value,
        tone: sourceSummary.tone,
      })
    }
  }
  if (targetItems.length > 0) {
    items.splice(1, 0, ...targetItems)
  }

  if (hasBonusOption || !bonusOpen) {
    const bonusIndex = targetItems.length > 0 ? 1 + targetItems.length : 2
    items.splice(bonusIndex, 0, {
      key: 'bonus',
      label: '附赠',
      value: bonusOpen ? '可用' : '已用',
      tone: bonusOpen ? 'ready' : 'spent',
    })
  }

  return { visible: true, items }
}

function buildActionStatus({
  actionOpen,
  helpMode,
  hasTarget,
  targetNeeded,
  hasActionOption,
}) {
  if (!actionOpen) return { value: '已用', tone: 'spent' }
  if (helpMode) return { value: '选队友', tone: 'warn' }
  if (!hasTarget && targetNeeded) return { value: '选目标', tone: 'warn' }
  return { value: hasActionOption ? '可用' : '选择', tone: 'ready' }
}

function skillNeedsTarget(skill = {}) {
  if (skill.requires_target || skill.needs_target) return true
  if (skill.target_required || skill.targeting?.requires_target) return true
  if (['attack', 'spell'].includes(skill.kind)) return true
  return false
}

function readNumber(value, fallback) {
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

function targetSummary(entity = null, prediction = null) {
  if (!entity) return '已选择'

  const parts = [String(entity.name || '目标')]
  if (entity.ac !== null && entity.ac !== undefined) parts.push(`AC ${entity.ac}`)
  if (prediction?.hit_rate !== null && prediction?.hit_rate !== undefined) {
    parts.push(`命中 ${formatPercent(prediction.hit_rate)}`)
  }
  parts.push(...compactAttackRuleLabels(prediction, entity))

  return parts.join(' · ')
}

function compactAttackRuleLabels(prediction = null, entity = null) {
  return buildCombatRuleTags(prediction, entity)
    .map(tag => tag.label)
    .filter(label => label && !label.startsWith('优势:') && !label.startsWith('劣势:'))
    .slice(0, 3)
}

function attackRuleSourceSummary(prediction = null, entity = null) {
  const sourceTags = buildCombatRuleTags(prediction, entity)
    .filter(tag => tag.key === 'advantage-source' || tag.key === 'disadvantage-source')

  if (sourceTags.length === 0) return null

  const sources = uniqueStrings(sourceTags.flatMap(sourceLabelsFromTag))
  if (sources.length === 0) return null

  return {
    value: sources.join(' / '),
    tone: sourceTags.some(tag => tag.key === 'disadvantage-source') ? 'warn' : 'ready',
  }
}

function sourceLabelsFromTag(tag = {}) {
  if (Array.isArray(tag.sources)) {
    return tag.sources.map(source => String(source || '').trim()).filter(Boolean)
  }
  const titleMatch = String(tag.title || '').match(/来源：(.+?)(?:。)?$/)
  const raw = titleMatch?.[1] || String(tag.label || '').replace(/^(优势|劣势)\s*[:：]\s*/, '')
  return raw.split('/').map(source => source.trim()).filter(Boolean)
}

function uniqueStrings(values = []) {
  const seen = new Set()
  const result = []
  for (const value of values) {
    if (!value || seen.has(value)) continue
    seen.add(value)
    result.push(value)
  }
  return result
}

function formatPercent(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '--'
  return `${Math.round((number <= 1 ? number * 100 : number))}%`
}
