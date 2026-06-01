import IsoBattlefieldCell from './IsoBattlefieldCell'
import IsoUnit from './IsoUnit'
import { isCombatEntityDead } from '../../utils/combat'
import { buildCombatRuleTags } from '../../utils/combatRuleTags'

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
    const interactive = Boolean(ent && !isWall) || Boolean(moveMode && !isWall) || Boolean(aoePreview && !isWall)
    const disabledReason = isWall
      ? wallDisabledReason(terrainDetail)
      : !ent && !moveMode && !aoePreview
        ? emptyCellReason(terrainDetail)
        : ''
    const title = ent
      ? helpMode && !ent.is_enemy && entId !== playerId
        ? withTerrainHint(joinTitleParts([`协助 ${ent.name || entId}`, aoeUnitHint]), terrainDetail)
        : withTerrainHint(joinTitleParts([`选择 ${ent.name || entId}`, selectedAttackHint, aoeUnitHint]), terrainDetail)
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
