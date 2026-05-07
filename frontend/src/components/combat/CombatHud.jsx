import CombatHudPips from './CombatHudPips'
import CombatHudPortrait from './CombatHudPortrait'
import CombatHudSkillBar from './CombatHudSkillBar'
import CombatHudCombatLog from './CombatHudCombatLog'
import CombatHudSlots from './CombatHudSlots'
import CombatHudControls from './CombatHudControls'

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
  onSkillClick,
  onEndTurn,
  onToggleMove,
  onToggleRanged,
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
        <CombatHudControls
          isProcessing={isProcessing}
          isPlayerTurn={isPlayerTurn}
          moveMode={moveMode}
          isRanged={isRanged}
          onEndTurn={onEndTurn}
          onToggleMove={onToggleMove}
          onToggleRanged={onToggleRanged}
          onReturnAdventure={onReturnAdventure}
          onForceEndCombat={onForceEndCombat}
        />
      </div>
    </div>
  )
}
