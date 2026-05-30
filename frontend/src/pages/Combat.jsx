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
  const page = useCombatPageState()
  const { room, setRoom, refreshRoom, myCharacterId } = useCombatRoom(sessionId, myUserId, {
    enabled: page.session?.is_multiplayer === true,
  })
  const {
    error,
    playerId,
  } = page
  const targeting = useCombatTargeting()
  const {
    selectedTarget, setSelectedTarget,
    moveMode, setMoveMode,
    helpMode,
    selectedWeaponName, setSelectedWeaponName,
    isRanged, setIsRanged,
    showThreat, setShowThreat,
    aoePreview,
    aoeHover,
    aoeLockedCenter,
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
    refreshRoom,
    myUserId,
    myCharacterId,
    showDice,
    page,
    targeting,
    log,
    navigate,
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
    spellQuickPick,
    playerSpellSlots,
    playerCantrips,
    smitePrompt,
    maneuverModalOpen,
    playerSubclassEffects,
    classResources,
    reactionPrompt,
    prediction,
    derived,
    wsConnected,
    wsStatus,
    combatSyncBlocked,
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
    controlledCharacter,
    initiativeChips,
    skillBar,
    playerAvailableSpells,
    threatCells,
    aoeCells,
  } = derived
  const currentTurnControllerName = room && currentTurnEntry
    ? (room.members || []).find(member => member.character_id === currentTurnEntry.character_id)?.display_name
    : ''
  const currentTurnEntity = currentTurnEntry?.character_id
    ? entities?.[currentTurnEntry.character_id]
    : null
  const {
    onSkillClick,
    handleMoveTo,
    handleHelpTarget,
    handleInspectTarget,
    handleSpellHover,
    handleEndTurn,
    handleCastSpell,
    handleDeathSave,
    handleSmite,
    handleReaction,
    handleCancelReaction,
    handleManeuver,
    setAoeHover,
    setAoeLockedCenter,
    setSmitePrompt,
    setSpellModalOpen,
    setSpellQuickPick,
    setManeuverModalOpen,
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
        wsConnected={wsConnected}
        wsStatus={wsStatus}
        syncBlocked={combatSyncBlocked}
        currentTurnLabel={currentTurnLabel}
        isMyTurnMP={isMyTurnMP}
        controllerName={currentTurnControllerName}
        currentTurnCharacterId={currentTurnEntry?.character_id}
      />

      <TurnBanner
        roundNumber={combat?.round_number || 1}
        currentTurnName={currentTurnEntry?.name}
        currentTurnEntry={currentTurnEntry}
        currentTurnEntity={currentTurnEntity}
        controlledCharacter={controlledCharacter}
        combatOver={combatOver}
        isPlayerTurn={canActThisTurn && !combatSyncBlocked}
        isProcessing={isProcessing}
        syncBlocked={combatSyncBlocked}
        room={room}
        controllerName={currentTurnControllerName}
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
        helpMode={helpMode}
        aoePreview={aoePreview}
        aoeHover={aoeHover}
        aoeLockedCenter={aoeLockedCenter}
        playerId={effectivePlayerId || playerId}
        prediction={prediction}
        canInspectTarget={canActThisTurn && !combatSyncBlocked}
        inspectBusy={isProcessing}
        floats={floats}
        combatOver={combatOver}
        onSelectTarget={setSelectedTarget}
        onInspectTarget={handleInspectTarget}
        onHelpTarget={handleHelpTarget}
        onMoveTo={handleMoveTo}
        onAoeHover={setAoeHover}
        onAoeLockCenter={(key) => {
          setAoeLockedCenter(key)
          setAoeHover(key)
        }}
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
        prediction={prediction}
        logs={logs}
        logsEndRef={logsEndRef}
        playerSpellSlots={playerSpellSlots}
        controlledCharacter={controlledCharacter}
        isProcessing={isProcessing}
        isPlayerTurn={canActThisTurn && !combatSyncBlocked}
        syncBlocked={combatSyncBlocked}
        moveMode={moveMode}
        isRanged={isRanged}
        selectedWeaponName={selectedWeaponName}
        onSessionChange={runtime.setSession}
        onTurnStateChange={page.setTurnState}
        onError={page.setError}
        onSkillClick={onSkillClick}
        onDeathSave={handleDeathSave}
        onEndTurn={handleEndTurn}
        onToggleMove={() => setMoveMode(m => !m)}
        onToggleRanged={() => setIsRanged(r => !r)}
        onSelectedWeaponChange={setSelectedWeaponName}
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
        spellQuickPick={spellQuickPick}
        playerAvailableSpells={playerAvailableSpells}
        playerCantrips={playerCantrips}
        selectedTarget={selectedTarget}
        playerId={effectivePlayerId || playerId}
        combat={combat}
        aoeHover={aoeHover}
        aoeLockedCenter={aoeLockedCenter}
        onCastSpell={handleCastSpell}
        onCloseSpell={() => { setSpellModalOpen(false); setSpellQuickPick(null); clearAoePreview() }}
        onSpellHover={handleSpellHover}
        maneuverModalOpen={maneuverModalOpen}
        playerSubclassEffects={playerSubclassEffects}
        classResources={classResources}
        onUseManeuver={handleManeuver}
        onCloseManeuver={() => setManeuverModalOpen(false)}
        reactionPrompt={reactionPrompt}
        currentCharacterId={effectivePlayerId || playerId}
        onReact={handleReaction}
        onCancelReaction={handleCancelReaction}
        error={error}
      />
    </div>
  )
}
