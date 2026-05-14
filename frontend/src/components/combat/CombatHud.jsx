import CombatHudPips from './CombatHudPips'
import CombatHudPortrait from './CombatHudPortrait'
import CombatHudSkillBar from './CombatHudSkillBar'
import CombatHudCombatLog from './CombatHudCombatLog'
import CombatHudSlots from './CombatHudSlots'
import CombatHudControls from './CombatHudControls'
import CombatQuickInventory from './CombatQuickInventory'

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
  isProcessing,
  isPlayerTurn,
  moveMode,
  isRanged,
  onSessionChange,
  onTurnStateChange,
  onError,
  onSkillClick,
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
        />

        <CombatHudCombatLog logs={logs} logsEndRef={logsEndRef} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <CombatHudSlots session={session} playerSpellSlots={playerSpellSlots} />
        <CombatQuickInventory
          session={session}
          turnState={turnState}
          isPlayerTurn={isPlayerTurn}
          disabled={isProcessing}
          onSessionChange={onSessionChange}
          onTurnStateChange={onTurnStateChange}
          onError={onError}
        />
        <CombatHudControls
          isProcessing={isProcessing}
          isPlayerTurn={isPlayerTurn}
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
