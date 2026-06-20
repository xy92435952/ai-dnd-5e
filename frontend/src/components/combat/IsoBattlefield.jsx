import IsoBattlefieldCell from './IsoBattlefieldCell'
import IsoUnit from './IsoUnit'
import { isCombatEntityDead } from '../../utils/combat'
import { buildCombatRuleTags } from '../../utils/combatRuleTags'
import {
  buildConditionFrightenedMoveBlockedReason,
  buildConditionSpeedLockReason,
  buildConditionStandUpMoveNotice,
} from '../../utils/conditionRules'

export default function IsoBattlefield({
  viewWidth,
  viewHeight,
  cam,
  walls,
  hazards,
  objectives = new Set(),
  terrainDetails = {},
  entityPositions,
  entities,
  selectedTarget,
  prediction,
  currentTurnCharacterId,
  threatCells,
  aoeCells,
  moveMode,
  helpMode,
  aoePreview,
  aoeHover,
  aoeLockedCenter,
  playerId,
  turnState = {},
  onSelectTarget,
  onHelpTarget = () => {},
  onMoveTo,
  onAoeHover,
  onAoeLockCenter = () => {},
}) {
  const renderCell = (x, y) => {
    const key = `${x}_${y}`
    const isWall = walls.has(key)
    const isHazard = hazards.has(key)
    const isObjective = objectives.has(key)
    const terrainDetail = terrainDetails?.[key] || null
    const entryEntry = Object.entries(entityPositions || {})
      .find(([, pos]) => pos?.x === x && pos?.y === y)
    const [entId] = entryEntry || []
    const ent = entId ? entities[entId] : null
    const isTarget = entId && entId === selectedTarget
    const isCurTurn = entId && entId === currentTurnCharacterId

    let klass = ''
    if (isWall) klass = 'wall'
    else if (isTarget) klass = 'target'
    else if (isHazard) klass = 'hazard'
    else if (isObjective) klass = 'objective'

    const isThreat = threatCells.has(key) && !isWall && !ent?.is_enemy
    const isAoeCenter = aoeCells.center === key
    const isAoeRing = !isAoeCenter && aoeCells.ring.has(key) && !isWall
    const aoeTemplate = aoeCells?.template || aoePreview?.template || ''
    const aoeTemplateClass = isAoeRing && aoeCells.template ? ` aoe-${aoeCells.template}` : ''
    const aoeImpact = aoePreview
      ? buildAoeImpactSummary({ aoeCells, entityPositions, entities, playerId, aoePreview })
      : ''
    const aoeUnitHint = aoePreview && ent && isCellInAoe(key, aoeCells)
      ? buildAoeUnitHint({ entityId: entId, entity: ent, playerId, aoePreview })
      : ''
    const selectedAttackHint = buildSelectedAttackHint({
      entId,
      selectedTarget,
      prediction,
      entity: ent,
    })
    const coverPathHint = buildCoverPathHintForCell(key, prediction)
    const movementState = moveMode && !isWall && !ent
      ? buildMovementCellState({
          x,
          y,
          terrainDetail,
          terrainDetails,
          entityPositions,
          entities,
          currentTurnCharacterId,
          playerId,
          turnState,
        })
      : null
    const interactive = Boolean(ent && !isWall) || Boolean(moveMode && !isWall) || Boolean(aoePreview && !isWall)
    const disabledReason = isWall
      ? joinTitleParts([wallDisabledReason(terrainDetail), coverPathHint])
      : movementState?.disabledReason
        ? movementState.disabledReason
      : !ent && !moveMode && !aoePreview
        ? joinTitleParts([emptyCellReason(terrainDetail), coverPathHint])
        : ''
    const title = ent
      ? helpMode && !ent.is_enemy && entId !== playerId
        ? withTerrainHint(joinTitleParts([`协助 ${ent.name || entId}`, aoeUnitHint]), terrainDetail)
        : withTerrainHint(joinTitleParts([`选择 ${ent.name || entId}`, selectedAttackHint, aoeUnitHint]), terrainDetail)
      : aoePreview && !isWall
        ? withTerrainHint(buildAoeCellTitle({ template: aoeTemplate, locked: aoeLockedCenter === key, x, y, impact: aoeImpact }), terrainDetail)
      : moveMode && !isWall
        ? movementState?.title || withTerrainHint(`移动到 ${x}, ${y}`, terrainDetail)
        : ''

    return (
      <IsoBattlefieldCell
        key={key}
        className={`iso-cell ${klass}${coverPathHint ? ' cover-path' : ''}${isThreat ? ' threat' : ''}${isAoeRing ? ` aoe${aoeTemplateClass}` : ''}${isAoeCenter ? ' aoe-center' : ''}`}
        gridKey={key}
        interactive={interactive}
        disabledReason={disabledReason}
        title={title}
        onClick={() => {
          if (aoePreview && !isWall && !ent) {
            onAoeLockCenter(key)
          } else if (ent && !isWall) {
            if (helpMode && !ent.is_enemy && entId !== playerId) {
              onHelpTarget(entId, ent)
            } else {
              onSelectTarget(entId)
            }
          } else if (moveMode && !isWall) {
            onMoveTo(x, y)
          }
        }}
        onMouseEnter={() => { if (aoePreview && !aoeLockedCenter) onAoeHover(key) }}
        onMouseLeave={() => { if (aoePreview && !aoeLockedCenter && aoeHover === key) onAoeHover(null) }}
      >
        {ent && (
          <IsoUnit
            ent={ent}
            entId={entId}
            playerId={playerId}
            isCurTurn={isCurTurn}
            isTarget={isTarget}
            isHelpTarget={helpMode && !ent.is_enemy && entId !== playerId}
          />
        )}
      </IsoBattlefieldCell>
    )
  }

  return (
    <div className="iso-battlefield">
      <div className="iso-grid" style={{
        '--iso-grid-columns': `repeat(${viewWidth}, var(--combat-cell-size, 54px))`,
        '--iso-grid-rows': `repeat(${viewHeight}, var(--combat-cell-size, 54px))`,
      }}>
        {Array.from({ length: viewHeight }).flatMap((_, dy) =>
          Array.from({ length: viewWidth }).map((_, dx) => renderCell(cam.x0 + dx, cam.y0 + dy))
        )}
      </div>
    </div>
  )
}

function buildMovementCellState({
  x,
  y,
  terrainDetail,
  terrainDetails = {},
  entityPositions = {},
  entities = {},
  currentTurnCharacterId,
  playerId,
  turnState = {},
}) {
  const actorId = String(currentTurnCharacterId || playerId || '')
  const actor = entities?.[actorId] || entities?.[playerId] || null
  const conditions = actor?.conditions || []
  const durations = actor?.condition_durations || {}
  const speedLock = buildConditionSpeedLockReason(conditions, durations)
  if (speedLock) {
    return { disabledReason: speedLock, title: speedLock }
  }

  const destination = { x, y }
  const actorPosition = positionFrom(entityPositions?.[actorId] || entityPositions?.[playerId])
  const remaining = movementRemaining(turnState)
  const standUp = buildConditionStandUpMoveNotice({ conditions, durations, turnState })
  if (standUp?.blocksMovement) {
    return { disabledReason: standUp.reason, title: standUp.reason }
  }

  const frightenedBlock = actorPosition
    ? buildConditionFrightenedMoveBlockedReason({
        conditions,
        durations,
        from: actorPosition,
        to: destination,
        entityPositions,
      })
    : ''
  if (frightenedBlock) {
    return { disabledReason: frightenedBlock, title: frightenedBlock }
  }

  const path = actorPosition ? movementPath(actorPosition, destination) : []
  const baseCost = path.length
  const difficultExtra = difficultTerrainExtra(path, terrainDetails)
  const dragged = findDraggedEntity({ actorId, entities })
  const dragCost = dragged ? baseCost * 2 : null
  const normalCost = baseCost + difficultExtra
  const totalCost = dragged ? dragCost : normalCost

  if (dragged && dragCost > remaining) {
    const reason = `拖拽 ${dragged.name} 需要 ${dragCost} 格移动力，当前剩余 ${remaining} 格`
    return { disabledReason: reason, title: reason }
  }

  if (!dragged && difficultExtra > 0 && normalCost > remaining) {
    const reason = `困难地形需要 ${normalCost} 格移动力，当前剩余 ${remaining} 格`
    return { disabledReason: reason, title: reason }
  }

  const titleParts = [`移动到 ${x}, ${y}`]
  if (standUp?.title) titleParts.push(standUp.title)
  if (dragged && dragCost > 0) {
    titleParts.push(`拖拽 ${dragged.name}：移动消耗翻倍，此移动消耗 ${dragCost} 格（剩余 ${remaining} 格）`)
  } else if (difficultExtra > 0) {
    titleParts.push(`困难地形${labelSuffix(terrainDetail).replace(':', '')}，此移动消耗 ${normalCost} 格`)
  } else {
    const terrain = terrainHint(terrainDetail)
    if (terrain) titleParts.push(terrain)
  }

  return {
    disabledReason: '',
    title: joinTitleParts(titleParts),
    totalCost,
  }
}

function buildCoverPathHintForCell(key, prediction) {
  const cell = coverPathCells(prediction).find(item => item.key === key)
  if (!cell) return ''
  const coverTag = buildCombatRuleTags(prediction, {}).find(tag => String(tag.key || '').startsWith('cover-'))
  if (!coverTag) return ''
  return `掩护路径 ${cell.terrain || 'cover'}：${coverTag.label}`
}

function coverPathCells(prediction) {
  const cells = prediction?.cover_detail?.cells || prediction?.coverDetail?.cells || []
  if (!Array.isArray(cells)) return []
  return cells.map(cell => {
    if (typeof cell === 'string') return { key: cell, terrain: '' }
    if (!cell || typeof cell !== 'object') return null
    return {
      key: String(cell.cell || cell.key || ''),
      terrain: String(cell.terrain || cell.type || cell.kind || ''),
    }
  }).filter(cell => cell?.key)
}

function movementRemaining(turnState = {}) {
  const max = readMovementNumber(turnState?.movement_max, 6)
  const used = readMovementNumber(turnState?.movement_used, 0)
  return Math.max(0, max - used)
}

function movementPath(from, to) {
  const start = positionFrom(from)
  const end = positionFrom(to)
  if (!start || !end) return []
  const dx = end.x - start.x
  const dy = end.y - start.y
  const steps = Math.max(Math.abs(dx), Math.abs(dy))
  if (steps <= 0) return []
  return Array.from({ length: steps }, (_, index) => {
    const step = index + 1
    return {
      x: start.x + Math.round((dx * step) / steps),
      y: start.y + Math.round((dy * step) / steps),
    }
  })
}

function difficultTerrainExtra(path, terrainDetails = {}) {
  return path.filter(pos => {
    const detail = terrainDetails?.[`${pos.x}_${pos.y}`]
    const terrain = String(detail?.terrain || '').toLowerCase()
    return terrain === 'difficult' || terrain === 'difficult_terrain'
  }).length
}

function findDraggedEntity({ actorId, entities = {} }) {
  for (const [entityId, entity] of Object.entries(entities || {})) {
    if (String(entityId) === String(actorId)) continue
    if (!Array.isArray(entity?.conditions) || !entity.conditions.some(condition => normalizeCondition(condition) === 'grappled')) continue
    const sourceIds = conditionSourceIds(entity.condition_durations?.grappled)
    if (sourceIds.has(String(actorId))) {
      return { id: entityId, name: entity.name || entityId }
    }
  }
  return null
}

function conditionSourceIds(entry) {
  const ids = new Set()
  if (!entry) return ids
  if (typeof entry === 'object' && !Array.isArray(entry)) {
    ;['source_id', 'sourceId', 'source', 'grappler_id', 'grapplerId'].forEach(key => {
      if (entry[key] != null) ids.add(String(entry[key]))
    })
    const list = entry.source_ids || entry.sourceIds
    if (Array.isArray(list)) list.forEach(value => ids.add(String(value)))
  } else {
    ids.add(String(entry))
  }
  return ids
}

function normalizeCondition(condition) {
  return String(condition?.name || condition?.condition || condition || '').trim().toLowerCase().replace(/[-\s]+/g, '_')
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

function buildAoeCellTitle({ template, locked, x, y, impact = '' }) {
  const prefix = locked ? '已锁定' : '预览'
  const action = locked ? '' : '；点击锁定'
  const suffix = impact ? ` · ${impact}` : ''
  if (template === 'cone') return `${prefix}锥形方向点 ${x}, ${y}${action}${suffix}`
  if (template === 'line') return `${prefix}直线方向点 ${x}, ${y}${action}${suffix}`
  if (template === 'cube') return `${prefix}立方中心 ${x}, ${y}${action}${suffix}`
  if (template === 'aura') return `${prefix}自身光环 ${x}, ${y}${action}${suffix}`
  return `${prefix}范围中心 ${x}, ${y}${action}${suffix}`
}

function buildAoeImpactSummary({ aoeCells, entityPositions = {}, entities = {}, playerId = '', aoePreview = null }) {
  const affectedCells = new Set([...(aoeCells?.ring || []), aoeCells?.center].filter(Boolean))
  if (affectedCells.size === 0) return ''

  const groups = { enemy: [], ally: [], self: [] }
  for (const [entityId, pos] of Object.entries(entityPositions || {})) {
    if (!pos || !affectedCells.has(`${pos.x}_${pos.y}`)) continue
    const ent = entities?.[entityId]
    if (!ent || isCombatEntityDead(ent)) continue
    const name = ent.name || entityId
    if (entityId === playerId) groups.self.push(name)
    else if (ent.is_enemy) groups.enemy.push(name)
    else groups.ally.push(name)
  }

  const parts = []
  if (groups.enemy.length) parts.push(`敌方 ${groups.enemy.join('、')}`)
  if (groups.ally.length) parts.push(`友方 ${groups.ally.join('、')}`)
  if (groups.self.length) parts.push(`自身 ${groups.self.join('、')}`)
  const total = groups.enemy.length + groups.ally.length + groups.self.length
  if (!total) return '命中 0'
  const friendlyRisk = isHarmfulAoe(aoePreview) && (groups.ally.length || groups.self.length) ? ' · 误伤风险' : ''
  return `命中 ${total}：${parts.join('；')}${friendlyRisk}`
}

function buildAoeUnitHint({ entityId, entity, playerId, aoePreview = null }) {
  if (!entity || isCombatEntityDead(entity)) return ''
  const group = entityId === playerId ? '自身' : entity.is_enemy ? '敌方' : '友方'
  const risk = isHarmfulAoe(aoePreview) && (group === '友方' || group === '自身') ? ' · 误伤风险' : ''
  return `范围命中：${group}${risk}`
}

function buildSelectedAttackHint({ entId, selectedTarget, prediction = null, entity = null }) {
  if (!prediction || !entId || entId !== selectedTarget || !entity) return ''

  const parts = []
  if (prediction.hit_rate !== null && prediction.hit_rate !== undefined) {
    parts.push(`命中 ${formatPercent(prediction.hit_rate)}`)
  }

  const ruleLabels = buildCombatRuleTags(prediction, entity)
    .map(tag => tag.label)
    .filter(label => label && !label.startsWith('优势:') && !label.startsWith('劣势:'))
    .slice(0, 4)

  parts.push(...ruleLabels)
  return parts.join(' · ')
}

function formatPercent(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '--'
  return `${Math.round((number <= 1 ? number * 100 : number))}%`
}

function isCellInAoe(key, aoeCells) {
  return Boolean(key && (aoeCells?.center === key || aoeCells?.ring?.has(key)))
}

function isHarmfulAoe(aoePreview = null) {
  const type = String(aoePreview?.spellType || '').toLowerCase()
  return !['heal', 'buff', 'support'].includes(type)
}

function wallDisabledReason(detail) {
  if (!detail) return '墙体阻挡，无法选择或移动'
  return `${terrainSummary(detail)}阻挡，无法选择或移动`
}

function emptyCellReason(detail) {
  return withTerrainHint('开启移动模式后可选择空格移动', detail)
}

function withTerrainHint(base, detail) {
  const hint = terrainHint(detail)
  return hint ? `${base} · ${hint}` : base
}

function joinTitleParts(parts) {
  return parts.filter(Boolean).join(' · ')
}

function terrainHint(detail) {
  if (!detail) return ''
  const terrain = detail.terrain || ''
  if (terrain === 'hazard') {
    const save = detail.saveDc ? ` DC ${detail.saveDc}${detail.saveAbility ? ` ${String(detail.saveAbility).toUpperCase()}` : ''}` : ''
    const damage = detail.damageDice ? ` ${detail.damageDice}` : ''
    return `危险地形${labelSuffix(detail)}${damage}${save}`
  }
  if (terrain === 'difficult' || terrain === 'difficult_terrain') return `困难地形${labelSuffix(detail)}，移动消耗更高`
  if (terrain === 'objective') return `目标点${labelSuffix(detail)}`
  if (terrain === 'cover' || terrain === 'half_cover' || terrain === 'three_quarters_cover') return `掩体${labelSuffix(detail)}`
  if (terrain === 'total_cover') return `全掩体${labelSuffix(detail)}`
  return ''
}

function terrainSummary(detail) {
  if (!detail) return '墙体'
  const terrain = detail.terrain || ''
  if (terrain === 'total_cover') return `全掩体${labelSuffix(detail)}`
  if (terrain === 'cover' || terrain === 'half_cover' || terrain === 'three_quarters_cover') return `掩体${labelSuffix(detail)}`
  return `${detail.label || '墙体'}`
}

function labelSuffix(detail) {
  const label = detail?.label
  if (!label) return ''
  if (['Hazard', 'Difficult terrain', 'Objective', 'Cover', 'Wall', 'Total cover', '危险', '困难地形', '目标点', '掩护', '阻挡', '全掩护'].includes(label)) return ''
  return `: ${label}`
}
