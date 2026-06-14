import IsoBattlefield from './IsoBattlefield'
import TargetCard from './TargetCard'
import CombatOutcomeOverlay from './CombatOutcomeOverlay'
import CombatTacticalContextPanel from './CombatTacticalContextPanel'
import BattlefieldLegend from './BattlefieldLegend'

export default function CombatStage({
  viewWidth,
  viewHeight,
  cam,
  walls,
  hazards,
  objectives,
  terrainDetails,
  tacticalContext,
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
  turnState,
  prediction,
  canInspectTarget,
  inspectBusy,
  floats,
  combatOver,
  recoverableThrownWeapons,
  recoveredThrownWeapons,
  isRecoveringThrownWeapons,
  thrownRecoveryError,
  onSelectTarget,
  onInspectTarget,
  onHelpTarget,
  onMoveTo,
  onAoeHover,
  onAoeLockCenter,
  onReturn,
  onRecoverThrownWeapons,
}) {
  const stageClassName = tacticalContext?.hasContext ? 'combat-stage has-tactical-context' : 'combat-stage'

  return (
    <div className={stageClassName}>
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 30% 40%, rgba(47,168,184,.08), transparent 60%), radial-gradient(ellipse at 80% 60%, rgba(196,40,40,.1), transparent 55%)' }} />

      <IsoBattlefield
        viewWidth={viewWidth}
        viewHeight={viewHeight}
        cam={cam}
        walls={walls}
        hazards={hazards}
        objectives={objectives}
        terrainDetails={terrainDetails}
        entityPositions={entityPositions}
        entities={entities}
        selectedTarget={selectedTarget}
        prediction={prediction}
        currentTurnCharacterId={currentTurnCharacterId}
        threatCells={threatCells}
        aoeCells={aoeCells}
        moveMode={moveMode}
        helpMode={helpMode}
        aoePreview={aoePreview}
        aoeHover={aoeHover}
        aoeLockedCenter={aoeLockedCenter}
        playerId={playerId}
        turnState={turnState}
        onSelectTarget={onSelectTarget}
        onHelpTarget={onHelpTarget}
        onMoveTo={onMoveTo}
        onAoeHover={onAoeHover}
        onAoeLockCenter={onAoeLockCenter}
      />

      <CombatTacticalContextPanel context={tacticalContext} />

      <BattlefieldLegend
        walls={walls}
        hazards={hazards}
        objectives={objectives}
        threatCells={threatCells}
        aoeCells={aoeCells}
        moveMode={moveMode}
        helpMode={helpMode}
        aoePreview={aoePreview}
        aoeLockedCenter={aoeLockedCenter}
        prediction={prediction}
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

      <CombatOutcomeOverlay
        combatOver={combatOver}
        recoverableThrownWeapons={recoverableThrownWeapons}
        recoveredThrownWeapons={recoveredThrownWeapons}
        isRecoveringThrownWeapons={isRecoveringThrownWeapons}
        recoveryError={thrownRecoveryError}
        onRecoverThrownWeapons={onRecoverThrownWeapons}
        onReturn={onReturn}
      />
    </div>
  )
}
