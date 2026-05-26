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
  playerId,
  onSelectTarget,
  onHelpTarget = () => {},
  onMoveTo,
  onAoeHover,
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

    return (
      <IsoBattlefieldCell
        key={key}
        className={`iso-cell ${klass}${isThreat ? ' threat' : ''}${isAoeRing ? ' aoe' : ''}${isAoeCenter ? ' aoe-center' : ''}`}
        onClick={() => {
          if (ent && !isWall) {
            if (helpMode && !ent.is_enemy && entId !== playerId) {
              onHelpTarget(entId, ent)
            } else {
              onSelectTarget(entId)
            }
          } else if (moveMode && !isWall) {
            onMoveTo(x, y)
          }
        }}
        onMouseEnter={() => { if (aoePreview) onAoeHover(key) }}
        onMouseLeave={() => { if (aoePreview && aoeHover === key) onAoeHover(null) }}
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
        gridTemplateColumns: `repeat(${viewWidth}, 54px)`,
        gridTemplateRows: `repeat(${viewHeight}, 54px)`,
      }}>
        {Array.from({ length: viewHeight }).flatMap((_, dy) =>
          Array.from({ length: viewWidth }).map((_, dx) => renderCell(cam.x0 + dx, cam.y0 + dy))
        )}
      </div>
    </div>
  )
}
