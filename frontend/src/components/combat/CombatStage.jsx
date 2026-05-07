import IsoBattlefield from './IsoBattlefield'
import TargetCard from './TargetCard'
import CombatOutcomeOverlay from './CombatOutcomeOverlay'

export default function CombatStage({
  viewWidth,
  viewHeight,
  cam,
  walls,
  hazards,
  entityPositions,
  entities,
  selectedTarget,
  selectedTargetEntity,
  currentTurnCharacterId,
  threatCells,
  aoeCells,
  moveMode,
  aoePreview,
  aoeHover,
  playerId,
  prediction,
  floats,
  combatOver,
  onSelectTarget,
  onMoveTo,
  onAoeHover,
  onReturn,
}) {
  return (
    <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'grid', placeItems: 'center', padding: '20px 20px 0', minHeight: 0 }}>
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 30% 40%, rgba(47,168,184,.08), transparent 60%), radial-gradient(ellipse at 80% 60%, rgba(196,40,40,.1), transparent 55%)' }} />

      <IsoBattlefield
        viewWidth={viewWidth}
        viewHeight={viewHeight}
        cam={cam}
        walls={walls}
        hazards={hazards}
        entityPositions={entityPositions}
        entities={entities}
        selectedTarget={selectedTarget}
        currentTurnCharacterId={currentTurnCharacterId}
        threatCells={threatCells}
        aoeCells={aoeCells}
        moveMode={moveMode}
        aoePreview={aoePreview}
        aoeHover={aoeHover}
        playerId={playerId}
        onSelectTarget={onSelectTarget}
        onMoveTo={onMoveTo}
        onAoeHover={onAoeHover}
      />

      <TargetCard entity={selectedTargetEntity} prediction={prediction} />

      {floats.map(f => (
        <span key={f.id} className={`float-text ${f.kind}`} style={{ left: `${f.x}%`, top: `${f.y}%` }}>{f.val}</span>
      ))}

      <CombatOutcomeOverlay combatOver={combatOver} onReturn={onReturn} />
    </div>
  )
}
