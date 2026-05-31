import IsoBattlefieldCell from './IsoBattlefieldCell'
import IsoUnit from './IsoUnit'

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
  currentTurnCharacterId,
  threatCells,
  aoeCells,
  moveMode,
  helpMode,
  aoePreview,
  aoeHover,
  aoeLockedCenter,
  playerId,
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
      ? buildAoeImpactSummary({ aoeCells, entityPositions, entities, playerId })
      : ''
    const interactive = Boolean(ent && !isWall) || Boolean(moveMode && !isWall) || Boolean(aoePreview && !isWall)
    const disabledReason = isWall
      ? wallDisabledReason(terrainDetail)
      : !ent && !moveMode && !aoePreview
        ? emptyCellReason(terrainDetail)
        : ''
    const title = ent
      ? helpMode && !ent.is_enemy && entId !== playerId
        ? withTerrainHint(`协助 ${ent.name || entId}`, terrainDetail)
        : withTerrainHint(`选择 ${ent.name || entId}`, terrainDetail)
      : aoePreview && !isWall
        ? withTerrainHint(buildAoeCellTitle({ template: aoeTemplate, locked: aoeLockedCenter === key, x, y, impact: aoeImpact }), terrainDetail)
      : moveMode && !isWall
        ? withTerrainHint(`移动到 ${x}, ${y}`, terrainDetail)
        : ''

    return (
      <IsoBattlefieldCell
        key={key}
        className={`iso-cell ${klass}${isThreat ? ' threat' : ''}${isAoeRing ? ` aoe${aoeTemplateClass}` : ''}${isAoeCenter ? ' aoe-center' : ''}`}
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
        gridTemplateColumns: `repeat(${viewWidth}, var(--combat-cell-size, 54px))`,
        gridTemplateRows: `repeat(${viewHeight}, var(--combat-cell-size, 54px))`,
      }}>
        {Array.from({ length: viewHeight }).flatMap((_, dy) =>
          Array.from({ length: viewWidth }).map((_, dx) => renderCell(cam.x0 + dx, cam.y0 + dy))
        )}
      </div>
    </div>
  )
}

function buildAoeCellTitle({ template, locked, x, y, impact = '' }) {
  const prefix = locked ? '已确认' : '确认'
  const suffix = impact ? ` · ${impact}` : ''
  if (template === 'cone') return `${prefix}锥形方向 ${x}, ${y}${suffix}`
  if (template === 'line') return `${prefix}直线方向 ${x}, ${y}${suffix}`
  if (template === 'cube') return `${prefix}立方区域中心 ${x}, ${y}${suffix}`
  if (template === 'aura') return `${prefix}自身光环 ${x}, ${y}${suffix}`
  return `${prefix}法术中心 ${x}, ${y}${suffix}`
}

function buildAoeImpactSummary({ aoeCells, entityPositions = {}, entities = {}, playerId = '' }) {
  const affectedCells = new Set([...(aoeCells?.ring || []), aoeCells?.center].filter(Boolean))
  if (affectedCells.size === 0) return ''

  const counts = { enemy: 0, ally: 0, self: 0 }
  for (const [entityId, pos] of Object.entries(entityPositions || {})) {
    if (!pos || !affectedCells.has(`${pos.x}_${pos.y}`)) continue
    const ent = entities?.[entityId]
    if (!ent) continue
    if (entityId === playerId) counts.self += 1
    else if (ent.is_enemy) counts.enemy += 1
    else counts.ally += 1
  }

  const parts = []
  if (counts.enemy) parts.push(`敌方${counts.enemy}`)
  if (counts.ally) parts.push(`友方${counts.ally}`)
  if (counts.self) parts.push('自身')
  if (parts.length === 0) return ''
  const friendlyRisk = counts.ally || counts.self ? ' · 友伤风险' : ''
  return `影响 ${parts.join(' / ')}${friendlyRisk}`
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
  if (['Hazard', 'Difficult terrain', 'Objective', 'Cover', 'Wall', 'Total cover'].includes(label)) return ''
  return `: ${label}`
}
