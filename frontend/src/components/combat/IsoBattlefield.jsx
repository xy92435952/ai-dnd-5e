import IsoBattlefieldCell from './IsoBattlefieldCell'
import IsoUnit from './IsoUnit'

export default function IsoBattlefield({
  viewWidth,
  viewHeight,
  cam,
  walls,
  hazards,
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

    const isThreat = threatCells.has(key) && !isWall && !ent?.is_enemy
    const isAoeCenter = aoeCells.center === key
    const isAoeRing = !isAoeCenter && aoeCells.ring.has(key) && !isWall
    const aoeTemplateClass = isAoeRing && aoeCells.template ? ` aoe-${aoeCells.template}` : ''
    const interactive = Boolean(ent && !isWall) || Boolean(moveMode && !isWall) || Boolean(aoePreview && !isWall)
    const disabledReason = isWall
      ? '墙体阻挡，无法选择或移动'
      : !ent && !moveMode && !aoePreview
        ? '开启移动模式后可选择空格移动'
        : ''
    const title = ent
      ? helpMode && !ent.is_enemy && entId !== playerId
        ? `协助 ${ent.name || entId}`
        : `选择 ${ent.name || entId}`
      : aoePreview && !isWall
        ? (aoeLockedCenter === key ? `已确认法术中心 ${x}, ${y}` : `确认法术中心 ${x}, ${y}`)
      : moveMode && !isWall
        ? `移动到 ${x}, ${y}`
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
