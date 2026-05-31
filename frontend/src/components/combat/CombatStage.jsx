import IsoBattlefield from './IsoBattlefield'
import TargetCard from './TargetCard'
import CombatOutcomeOverlay from './CombatOutcomeOverlay'

export default function CombatStage({
  viewWidth,
  viewHeight,
  cam,
  walls,
  hazards,
  objectives,
  entityPositions,
  entities,
  selectedTarget,
  selectedTargetEntity,
  currentTurnCharacterId,
  threatCells,
  aoeCells,
  moveMode,
  helpMode,
  aoePreview,
  aoeHover,
  aoeLockedCenter,
  playerId,
  prediction,
  canInspectTarget,
  inspectBusy,
  floats,
  combatOver,
  onSelectTarget,
  onInspectTarget,
  onHelpTarget,
  onMoveTo,
  onAoeHover,
  onAoeLockCenter,
  onReturn,
}) {
  return (
    <div className="combat-stage">
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 30% 40%, rgba(47,168,184,.08), transparent 60%), radial-gradient(ellipse at 80% 60%, rgba(196,40,40,.1), transparent 55%)' }} />

      <IsoBattlefield
        viewWidth={viewWidth}
        viewHeight={viewHeight}
        cam={cam}
        walls={walls}
        hazards={hazards}
        objectives={objectives}
        entityPositions={entityPositions}
        entities={entities}
        selectedTarget={selectedTarget}
        currentTurnCharacterId={currentTurnCharacterId}
        threatCells={threatCells}
        aoeCells={aoeCells}
        moveMode={moveMode}
        helpMode={helpMode}
        aoePreview={aoePreview}
        aoeHover={aoeHover}
        aoeLockedCenter={aoeLockedCenter}
        playerId={playerId}
        onSelectTarget={onSelectTarget}
        onHelpTarget={onHelpTarget}
        onMoveTo={onMoveTo}
        onAoeHover={onAoeHover}
        onAoeLockCenter={onAoeLockCenter}
      />

      <TargetCard
        entity={selectedTargetEntity}
        prediction={prediction}
        canInspect={canInspectTarget}
        inspectBusy={inspectBusy}
        onInspect={onInspectTarget}
      />

      {floats.map(f => (
        <span key={f.id} className={`float-text ${f.kind}`} style={{ left: `${f.x}%`, top: `${f.y}%` }}>{f.val}</span>
      ))}

      <CombatOutcomeOverlay combatOver={combatOver} onReturn={onReturn} />
    </div>
  )
}
