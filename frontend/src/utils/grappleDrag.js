const GRAPPLED_ALIASES = {
  擒抱: 'grappled',
  被擒抱: 'grappled',
}

export function buildGrappleDragStatus({
  actorId = null,
  actorPosition = null,
  entities = {},
  entityPositions = {},
} = {}) {
  if (!actorId || !positionFrom(actorPosition)) return null

  const targets = Object.entries(entities || {})
    .filter(([entityId, entity]) => {
      if (!entity || String(entityId) === String(actorId)) return false
      const targetPosition = positionFrom(entityPositions?.[entityId])
      return targetPosition
        && isAdjacent(actorPosition, targetPosition)
        && isGrappledBy(entity, actorId)
    })
    .map(([entityId, entity]) => ({
      id: String(entity?.id || entityId),
      name: entity?.name || entity?.display_name || entity?.label || String(entityId),
      position: positionFrom(entityPositions?.[entityId]),
    }))

  if (!targets.length) return null
  return {
    type: 'grapple_drag',
    targets,
    summary: formatDraggedTargets(targets),
    title: `拖拽 ${formatDraggedTargets(targets)} · 移动消耗翻倍`,
  }
}

export function buildGrappleDragMovePreview({
  actorId = null,
  actorPosition = null,
  destination = null,
  entities = {},
  entityPositions = {},
  turnState = {},
  reservedMovementCost = 0,
} = {}) {
  const status = buildGrappleDragStatus({
    actorId,
    actorPosition,
    entities,
    entityPositions,
  })
  if (!status) return null

  const steps = gridDistance(actorPosition, destination)
  if (!steps) return null

  const movementCost = steps * 2
  const movementMax = readMovementNumber(turnState?.movement_max, 6)
  const movementUsed = readMovementNumber(turnState?.movement_used, 0)
  const reserved = readMovementNumber(reservedMovementCost, 0)
  const remaining = Math.max(0, movementMax - movementUsed)
  const effectiveRemaining = Math.max(0, remaining - reserved)
  const remainingNotice = reserved > 0
    ? `起身后剩余 ${effectiveRemaining} 格`
    : `剩余 ${effectiveRemaining} 格`
  const blockedRemaining = reserved > 0
    ? `起身后剩余 ${effectiveRemaining} 格`
    : `当前剩余 ${effectiveRemaining} 格`

  return {
    ...status,
    steps,
    movementCost,
    remaining,
    effectiveRemaining,
    reservedMovementCost: reserved,
    notice: `拖拽 ${status.summary}：移动消耗翻倍，此移动消耗 ${movementCost} 格（${remainingNotice}）`,
    blockedReason: movementCost > effectiveRemaining
      ? `拖拽 ${status.summary} 需要 ${movementCost} 格移动力，${blockedRemaining}`
      : '',
  }
}

function isGrappledBy(entity, actorId) {
  const conditions = Array.isArray(entity?.conditions) ? entity.conditions : []
  if (!conditions.some(condition => conditionKey(condition) === 'grappled')) return false

  const entry = durationEntry(entity?.condition_durations || entity?.conditionDurations || {}, 'grappled')
  return sourceIdsFrom(entry).some(id => String(id) === String(actorId))
}

function durationEntry(durations = {}, condition) {
  const canonical = conditionKey(condition)
  for (const [key, value] of Object.entries(durations || {})) {
    if (conditionKey(key) === canonical) return value
  }
  return null
}

function sourceIdsFrom(entry) {
  if (entry == null) return []
  if (Array.isArray(entry)) return entry.flatMap(item => sourceIdsFrom(item))
  if (typeof entry === 'object') {
    const ids = []
    ;['source_ids', 'sourceIds'].forEach(key => {
      ids.push(...sourceIdsFrom(entry[key]))
    })
    ;[
      'source_id',
      'sourceId',
      'source',
      'source_entity_id',
      'sourceEntityId',
      'grappler_id',
      'grapplerId',
    ].forEach(key => {
      const value = entry[key]
      if (value != null && typeof value !== 'object') ids.push(String(value))
    })
    return ids
  }
  return [String(entry)]
}

function formatDraggedTargets(targets = []) {
  if (targets.length === 1) return targets[0].name
  return `${targets[0]?.name || '目标'} 等 ${targets.length} 个目标`
}

function conditionKey(condition) {
  if (typeof condition === 'string') return normalize(condition)
  if (!condition || typeof condition !== 'object') return ''
  return normalize(condition.name || condition.condition || condition.type || condition.id || '')
}

function normalize(value) {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_')
  return GRAPPLED_ALIASES[normalized] || normalized
}

function isAdjacent(a, b) {
  const distance = gridDistance(a, b)
  return distance != null && distance <= 1
}

function gridDistance(a, b) {
  const from = positionFrom(a)
  const to = positionFrom(b)
  if (!from || !to) return null
  return Math.max(Math.abs(from.x - to.x), Math.abs(from.y - to.y))
}

function positionFrom(value) {
  if (!value || typeof value !== 'object') return null
  const x = Number(value.x)
  const y = Number(value.y)
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null
  return { x, y }
}

function readMovementNumber(value, fallback = 0) {
  const number = Number(value)
  if (!Number.isFinite(number)) return fallback
  return Math.max(0, Math.floor(number))
}
