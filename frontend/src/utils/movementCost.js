const DIFFICULT_TERRAIN = new Set(['difficult', 'difficult_terrain'])

export function buildMovementPathCells(from = null, to = null) {
  const ax = readInteger(from?.x)
  const ay = readInteger(from?.y)
  const tx = readInteger(to?.x)
  const ty = readInteger(to?.y)
  if ([ax, ay, tx, ty].some(value => value == null)) return []

  const dx = tx - ax
  const dy = ty - ay
  const steps = Math.max(Math.abs(dx), Math.abs(dy))
  if (steps <= 0) return []

  const cells = []
  const seen = new Set()
  for (let index = 1; index <= steps; index += 1) {
    const cx = ax + Math.round(dx * index / steps)
    const cy = ay + Math.round(dy * index / steps)
    const key = `${cx}_${cy}`
    if (seen.has(key)) continue
    seen.add(key)
    cells.push({ key, cell: key, x: cx, y: cy })
  }
  return cells
}

export function buildDifficultTerrainMovePreview({
  actorPosition = null,
  destination = null,
  terrainDetails = null,
  gridData = null,
  turnState = {},
  reservedMovementCost = 0,
  baseMovementCost = null,
} = {}) {
  const path = buildMovementPathCells(actorPosition, destination)
  if (!path.length) return null

  const difficultCells = path
    .map(cell => ({ ...cell, detail: readTerrainDetail(cell.key, terrainDetails, gridData) }))
    .filter(cell => DIFFICULT_TERRAIN.has(normalizeTerrain(cell.detail?.terrain)))

  if (!difficultCells.length) return null

  const steps = path.length
  const baseCost = readMovementNumber(baseMovementCost, steps)
  const difficultExtra = difficultCells.length
  const movementCost = baseCost + difficultExtra
  const movementMax = readMovementNumber(turnState?.movement_max, 6)
  const movementUsed = readMovementNumber(turnState?.movement_used, 0)
  const reserved = readMovementNumber(reservedMovementCost, 0)
  const remaining = Math.max(0, movementMax - movementUsed)
  const effectiveRemaining = Math.max(0, remaining - reserved)
  const labelText = difficultCells
    .map(cell => cell.detail?.label || cell.key)
    .filter(Boolean)
    .slice(0, 2)
    .join('、')
  const suffix = difficultCells.length > 2 ? ` 等 ${difficultCells.length} 格` : ''
  const remainingNotice = reserved > 0
    ? `起身后剩余 ${effectiveRemaining} 格`
    : `剩余 ${effectiveRemaining} 格`
  const blockedRemaining = reserved > 0
    ? `起身后剩余 ${effectiveRemaining} 格`
    : `当前剩余 ${effectiveRemaining} 格`

  return {
    type: 'difficult_terrain',
    steps,
    baseCost,
    difficultExtra,
    movementCost,
    remaining,
    effectiveRemaining,
    cells: difficultCells.map(cell => ({
      key: cell.key,
      terrain: normalizeTerrain(cell.detail?.terrain),
      label: cell.detail?.label || cell.key,
      extraCost: 1,
    })),
    notice: `困难地形${labelText ? ` ${labelText}${suffix}` : ''}：每格额外消耗 1 格，此移动消耗 ${movementCost} 格（${remainingNotice}）`,
    blockedReason: movementCost > effectiveRemaining
      ? `困难地形需要 ${movementCost} 格移动力，${blockedRemaining}`
      : '',
  }
}

function readTerrainDetail(key, terrainDetails, gridData) {
  const detail = terrainDetails?.[key]
  if (detail) return detail
  return buildTerrainDetail(key, gridData?.[key])
}

function buildTerrainDetail(key, value) {
  const terrain = getTerrainKind(value)
  if (!terrain) return null
  const data = value && typeof value === 'object' ? value : {}
  return {
    key,
    terrain,
    label: data.name || data.label || data.title || terrainLabel(terrain),
  }
}

function getTerrainKind(value) {
  if (typeof value === 'string') return normalizeTerrain(value)
  if (!value || typeof value !== 'object') return ''
  if (value.hazard === true) return 'hazard'
  if (value.objective === true) return 'objective'
  const raw = value.terrain || value.type || value.kind || value.category || ''
  if (raw) return normalizeTerrain(raw)
  if (value.cover || value.cover_bonus || value.cover_level) return 'cover'
  return ''
}

function terrainLabel(terrain) {
  return DIFFICULT_TERRAIN.has(terrain) ? '困难地形' : terrain || '地形'
}

function normalizeTerrain(value) {
  return String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_')
}

function readMovementNumber(value, fallback) {
  if (value === null || value === undefined || value === '') return fallback
  const numeric = Number(value)
  return Number.isFinite(numeric) ? Math.max(0, numeric) : fallback
}

function readInteger(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? Math.trunc(numeric) : null
}
