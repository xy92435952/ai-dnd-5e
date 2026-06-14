import CombatHudPips from './CombatHudPips'
import CombatHudPortrait from './CombatHudPortrait'
import CombatHudSkillBar from './CombatHudSkillBar'
import CombatHudCombatLog from './CombatHudCombatLog'
import CombatHudSlots from './CombatHudSlots'
import CombatHudControls from './CombatHudControls'
import CombatQuickInventory from './CombatQuickInventory'
import CombatDeathSavePanel from './CombatDeathSavePanel'
import CombatHudIntentSummary from './CombatHudIntentSummary'

export default function CombatHud({
  session,
  playerClass,
  playerSubclass,
  playerLevel,
  turnState,
  skillBar,
  selectedTarget,
  entities,
  prediction,
  logs,
  logsEndRef,
  playerSpellSlots,
  controlledCharacter,
  isProcessing,
  isPlayerTurn,
  canDelayTurn = isPlayerTurn,
  delayTurnOptions = [],
  delayAfterEntityId = '',
  syncBlocked = false,
  moveMode,
  helpMode,
  isRanged,
  selectedWeaponName,
  classResources = {},
  useLuckyAttack = false,
  useBardicAttack = false,
  useBardicDeathSave = false,
  useBardicEndSave = false,
  onSessionChange,
  onTurnStateChange,
  onError,
  onSkillClick,
  onDeathSave,
  onEndTurn,
  onDelayTurn,
  onDelayAfterEntityChange,
  onEndConcentration,
  onToggleMove,
  onToggleRanged,
  onSelectedWeaponChange,
  onToggleLuckyAttack,
  onToggleBardicAttack,
  onToggleBardicDeathSave,
  onToggleBardicEndSave,
  onOpenCharacter,
  onReturnAdventure,
  onForceEndCombat,
}) {
  return (
    <div className="combat-hud" role="region" aria-label="Combat command HUD">
      <div className="combat-hud-left">
        <CombatHudPips turnState={turnState} />
        <CombatHudPortrait
          session={session}
          character={controlledCharacter}
          playerClass={playerClass}
          playerSubclass={playerSubclass}
          playerLevel={playerLevel}
          turnState={turnState}
        />
      </div>

      <div className="combat-hud-center">
        <CombatHudIntentSummary
          turnState={turnState}
          skillBar={skillBar}
          selectedTarget={selectedTarget}
          entities={entities}
          prediction={prediction}
          isPlayerTurn={isPlayerTurn}
          isProcessing={isProcessing}
          syncBlocked={syncBlocked}
          moveMode={moveMode}
          helpMode={helpMode}
          isRanged={isRanged}
          selectedWeaponName={selectedWeaponName}
        />

        <CombatHudSkillBar
          skillBar={skillBar}
          session={session}
          entities={entities}
          selectedTarget={selectedTarget}
          prediction={prediction}
          turnState={turnState}
          onSkillClick={onSkillClick}
          isPlayerTurn={isPlayerTurn}
          isProcessing={isProcessing}
          syncBlocked={syncBlocked}
        />

        <CombatHudCombatLog logs={logs} logsEndRef={logsEndRef} />
      </div>

      <div className="combat-hud-right">
        <CombatHudSlots
          session={session}
          playerSpellSlots={playerSpellSlots}
          character={controlledCharacter}
          disabled={isProcessing || syncBlocked}
          onEndConcentration={onEndConcentration}
        />
        <CombatDeathSavePanel
          character={controlledCharacter || session?.player}
          isPlayerTurn={isPlayerTurn}
          isProcessing={isProcessing}
          syncBlocked={syncBlocked}
          classResources={classResources}
          useBardicDeathSave={useBardicDeathSave}
          onToggleBardicDeathSave={onToggleBardicDeathSave}
          onDeathSave={onDeathSave}
        />
        <CombatQuickInventory
          session={session}
          turnState={turnState}
          isPlayerTurn={isPlayerTurn}
          disabled={isProcessing || syncBlocked}
          onSessionChange={onSessionChange}
          onTurnStateChange={onTurnStateChange}
          onError={onError}
        />
        <CombatHudControls
          isProcessing={isProcessing}
          isPlayerTurn={isPlayerTurn}
          canDelayTurn={canDelayTurn}
          delayTurnOptions={delayTurnOptions}
          delayAfterEntityId={delayAfterEntityId}
          syncBlocked={syncBlocked}
          moveMode={moveMode}
          isRanged={isRanged}
          selectedWeaponName={selectedWeaponName}
          classResources={classResources}
          useLuckyAttack={useLuckyAttack}
          useBardicAttack={useBardicAttack}
          useBardicEndSave={useBardicEndSave}
          character={controlledCharacter || session?.player}
          turnState={turnState}
          onEndTurn={onEndTurn}
          onDelayTurn={onDelayTurn}
          onDelayAfterEntityChange={onDelayAfterEntityChange}
          onToggleMove={onToggleMove}
          onToggleRanged={onToggleRanged}
          onSelectedWeaponChange={onSelectedWeaponChange}
          onToggleLuckyAttack={onToggleLuckyAttack}
          onToggleBardicAttack={onToggleBardicAttack}
          onToggleBardicEndSave={onToggleBardicEndSave}
          onOpenCharacter={onOpenCharacter}
          onReturnAdventure={onReturnAdventure}
          onForceEndCombat={onForceEndCombat}
        />
      </div>
    </div>
  )
}
