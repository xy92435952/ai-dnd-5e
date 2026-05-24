import { useNavigate, useParams } from 'react-router-dom'
import { useGameStore } from '../store/gameStore'
import { useUser } from '../hooks/useUser'
import { useCombatLog } from '../hooks/useCombatLog'
import { useCombatRoom } from '../hooks/useCombatRoom'
import { useCombatTargeting } from '../hooks/useCombatTargeting'
import { useCombatNavigationActions } from '../hooks/useCombatNavigationActions'
import { useCombatPageState } from '../hooks/useCombatPageState'
import { useCombatRuntime } from '../hooks/useCombatRuntime'
import DiceRollerOverlay from '../components/DiceRollerOverlay'
import { JuiceAudio } from '../juice'
import MultiplayerTurnBar from '../components/combat/MultiplayerTurnBar'
import TurnBanner from '../components/combat/TurnBanner'
import InitiativeRibbon from '../components/combat/InitiativeRibbon'
import CombatStage from '../components/combat/CombatStage'
import CombatHud from '../components/combat/CombatHud'
import CombatOverlays from '../components/combat/CombatOverlays'
import { COMBAT_GRID, ignoreOptionalEffect } from '../utils/combatPage'

export default function Combat() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { showDice } = useGameStore()

  // ── 多人联机相关 ──
  const { userId: myUserId } = useUser()
  const { room, setRoom, myCharacterId } = useCombatRoom(sessionId, myUserId)

  const page = useCombatPageState()
  const {
    error,
    playerId,
  } = page
  const targeting = useCombatTargeting()
  const {
    selectedTarget, setSelectedTarget,
    moveMode, setMoveMode,
    isRanged, setIsRanged,
    showThreat, setShowThreat,
    aoePreview,
    aoeHover,
  } = targeting
  const log = useCombatLog()
  const {
    logs,
    logsEndRef,
  } = log
  const runtime = useCombatRuntime({
    sessionId,
    room,
    setRoom,
    myCharacterId,
    showDice,
    page,
    targeting,
    log,
  })
  const {
    session,
    playerClass,
    playerSubclass,
    playerLevel,
    turnState,
    combat,
    combatOver,
    isProcessing,
    spellModalOpen,
    playerSpellSlots,
    playerCantrips,
    smitePrompt,
    maneuverModalOpen,
    playerSubclassEffects,
    classResources,
    reactionPrompt,
    prediction,
    derived,
    actions,
  } = runtime
  const {
    entityPositions,
    entities,
    cam,
    effectivePlayerId,
    currentTurnEntry,
    canActThisTurn,
    isMyTurnMP,
    currentTurnLabel,
    walls,
    hazards,
    selectedTargetEntity,
    initiativeChips,
    skillBar,
    playerAvailableSpells,
    threatCells,
    aoeCells,
  } = derived
  const currentTurnControllerName = room && currentTurnEntry
    ? (room.members || []).find(member => member.character_id === currentTurnEntry.character_id)?.display_name
    : ''
  const {
    onSkillClick,
    handleMoveTo,
    handleSpellHover,
    handleEndTurn,
    handleCastSpell,
    handleSmite,
    handleReaction,
    handleManeuver,
    setAoeHover,
    setSmitePrompt,
    setSpellModalOpen,
    setManeuverModalOpen,
    setReactionPrompt,
    clearAoePreview,
  } = actions

  const { returnToAdventure, endCombatAndReturn, forceEndCombat } = useCombatNavigationActions({
    sessionId,
    navigate,
  })

  // v0.10 — 伤害飘字（保留 floats 占位，目前未使用）
  const floats = []

  // ── 渲染 ───────────────────────────────────────────────
  if (!combat) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
        {error
          ? <p style={{ color: 'var(--red-light)' }}>{error}</p>
          : <p className="animate-pulse" style={{ color: 'var(--gold)' }}>加载战斗...</p>}
      </div>
    )
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden',
      background: 'linear-gradient(180deg, #06040a 0%, #0a0604 100%)',
      position: 'relative', zIndex: 1,
    }}>
      <DiceRollerOverlay />

      <MultiplayerTurnBar
        room={room}
        currentTurnLabel={currentTurnLabel}
        isMyTurnMP={isMyTurnMP}
        controllerName={currentTurnControllerName}
        currentTurnCharacterId={currentTurnEntry?.character_id}
      />

      <TurnBanner
        roundNumber={combat?.round_number || 1}
        currentTurnName={currentTurnEntry?.name}
        combatOver={combatOver}
        showThreat={showThreat}
        onToggleThreat={() => { setShowThreat(v => !v); ignoreOptionalEffect(() => JuiceAudio.click()) }}
      />

      <InitiativeRibbon
        initiativeChips={initiativeChips}
        onSelectTarget={setSelectedTarget}
      />

      <CombatStage
        viewWidth={COMBAT_GRID.viewWidth}
        viewHeight={COMBAT_GRID.viewHeight}
        cam={cam}
        walls={walls}
        hazards={hazards}
        entityPositions={entityPositions}
        entities={entities}
        selectedTarget={selectedTarget}
        selectedTargetEntity={selectedTargetEntity}
        currentTurnCharacterId={currentTurnEntry?.character_id}
        threatCells={threatCells}
        aoeCells={aoeCells}
        moveMode={moveMode}
        aoePreview={aoePreview}
        aoeHover={aoeHover}
        playerId={effectivePlayerId || playerId}
        prediction={prediction}
        floats={floats}
        combatOver={combatOver}
        onSelectTarget={setSelectedTarget}
        onMoveTo={handleMoveTo}
        onAoeHover={setAoeHover}
        onReturn={endCombatAndReturn}
      />

      <CombatHud
        session={session}
        playerClass={playerClass}
        playerSubclass={playerSubclass}
        playerLevel={playerLevel}
        turnState={turnState}
        skillBar={skillBar}
        selectedTarget={selectedTarget}
        entities={entities}
        logs={logs}
        logsEndRef={logsEndRef}
        playerSpellSlots={playerSpellSlots}
        isProcessing={isProcessing}
        isPlayerTurn={canActThisTurn}
        moveMode={moveMode}
        isRanged={isRanged}
        onSessionChange={runtime.setSession}
        onTurnStateChange={page.setTurnState}
        onError={page.setError}
        onSkillClick={onSkillClick}
        onEndTurn={handleEndTurn}
        onToggleMove={() => setMoveMode(m => !m)}
        onToggleRanged={() => setIsRanged(r => !r)}
        onOpenCharacter={() => playerId && navigate(`/character/${playerId}?sessionId=${sessionId}`)}
        onReturnAdventure={returnToAdventure}
        onForceEndCombat={forceEndCombat}
      />

      <CombatOverlays
        smitePrompt={smitePrompt}
        playerSpellSlots={playerSpellSlots}
        onSmite={handleSmite}
        onCancelSmite={() => setSmitePrompt(null)}
        spellModalOpen={spellModalOpen}
        playerAvailableSpells={playerAvailableSpells}
        playerCantrips={playerCantrips}
        onCastSpell={handleCastSpell}
        onCloseSpell={() => { setSpellModalOpen(false); clearAoePreview() }}
        onSpellHover={handleSpellHover}
        maneuverModalOpen={maneuverModalOpen}
        playerSubclassEffects={playerSubclassEffects}
        classResources={classResources}
        onUseManeuver={handleManeuver}
        onCloseManeuver={() => setManeuverModalOpen(false)}
        reactionPrompt={reactionPrompt}
        onReact={handleReaction}
        onCancelReaction={() => setReactionPrompt(null)}
        error={error}
      />
    </div>
  )
}
