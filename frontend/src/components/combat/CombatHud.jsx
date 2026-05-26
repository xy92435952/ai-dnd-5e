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
  logs,
  logsEndRef,
  playerSpellSlots,
  controlledCharacter,
  isProcessing,
  isPlayerTurn,
  syncBlocked = false,
  moveMode,
  isRanged,
  onSessionChange,
  onTurnStateChange,
  onError,
  onSkillClick,
  onDeathSave,
  onEndTurn,
  onToggleMove,
  onToggleRanged,
  onOpenCharacter,
  onReturnAdventure,
  onForceEndCombat,
}) {
  return (
    <div className="combat-hud" style={{ flexShrink: 0 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
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

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
        <CombatHudSkillBar
          skillBar={skillBar}
          session={session}
          entities={entities}
          selectedTarget={selectedTarget}
          onSkillClick={onSkillClick}
          isPlayerTurn={isPlayerTurn}
          syncBlocked={syncBlocked}
        />

        <CombatHudCombatLog logs={logs} logsEndRef={logsEndRef} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
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
          onEndTurn={onEndTurn}
          onToggleMove={onToggleMove}
          onToggleRanged={onToggleRanged}
          onOpenCharacter={onOpenCharacter}
          onReturnAdventure={onReturnAdventure}
          onForceEndCombat={onForceEndCombat}
        />
      </div>
    </div>
  )
}
