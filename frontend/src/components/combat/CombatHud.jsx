import CombatHudPips from './CombatHudPips'
import CombatHudPortrait from './CombatHudPortrait'
import CombatHudSkillBar from './CombatHudSkillBar'
import CombatHudCombatLog from './CombatHudCombatLog'
import CombatHudSlots from './CombatHudSlots'
import CombatHudControls from './CombatHudControls'
import CombatQuickInventory from './CombatQuickInventory'
import CombatDeathSavePanel from './CombatDeathSavePanel'

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
  syncBlocked = false,
  moveMode,
  isRanged,
  selectedWeaponName,
  onSessionChange,
  onTurnStateChange,
  onError,
  onSkillClick,
  onDeathSave,
  onEndTurn,
  onToggleMove,
  onToggleRanged,
  onSelectedWeaponChange,
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
        <CombatHudSlots session={session} playerSpellSlots={playerSpellSlots} character={controlledCharacter} />
        <CombatDeathSavePanel
          character={controlledCharacter || session?.player}
          isPlayerTurn={isPlayerTurn}
          isProcessing={isProcessing}
          syncBlocked={syncBlocked}
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
          syncBlocked={syncBlocked}
          moveMode={moveMode}
          isRanged={isRanged}
          selectedWeaponName={selectedWeaponName}
          character={controlledCharacter || session?.player}
          onEndTurn={onEndTurn}
          onToggleMove={onToggleMove}
          onToggleRanged={onToggleRanged}
          onSelectedWeaponChange={onSelectedWeaponChange}
          onOpenCharacter={onOpenCharacter}
          onReturnAdventure={onReturnAdventure}
          onForceEndCombat={onForceEndCombat}
        />
      </div>
    </div>
  )
}
