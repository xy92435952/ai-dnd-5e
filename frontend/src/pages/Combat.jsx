import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { gameApi } from '../api/client'
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
import { buildCombatTacticalContext } from '../utils/combatTacticalContext'
import {
  formatThrownRecoverySummary,
  getRecoverableThrownWeapons,
  mergeThrownRecoveryResultIntoSession,
} from '../utils/thrownRecovery'

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
    addLog,
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
    setSession,
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
    legendaryActionPrompt,
    lairActionPrompt,
    prediction,
    derived,
    wsConnected,
    wsStatus,
    combatSyncBlocked,
    canDriveAiTurns,
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
    objectives,
    terrainDetails,
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
  const nextTurnChip = getNextInitiativeChip(initiativeChips)
  const nextTurnName = getInitiativeChipName(nextTurnChip)
  const nextTurnTone = nextTurnChip?.t?.is_enemy || nextTurnChip?.ent?.is_enemy ? 'enemy' : 'ally'
  const canDelayTurn = (
    canActThisTurn
    || (canDriveAiTurns && currentTurnEntry && currentTurnEntry.is_player !== true)
  )
  const delayTurnOptions = useMemo(
    () => buildDelayTurnOptions(combat, entities),
    [combat, entities],
  )
  const [delayAfterEntityId, setDelayAfterEntityId] = useState('')
  const recoveryCharacterId = effectivePlayerId || playerId
  const [isRecoveringThrownWeapons, setIsRecoveringThrownWeapons] = useState(false)
  const [lastRecoveredThrownWeapons, setLastRecoveredThrownWeapons] = useState([])
  const [thrownRecoveryError, setThrownRecoveryError] = useState('')
  const recoverableThrownWeapons = useMemo(
    () => getRecoverableThrownWeapons(session, recoveryCharacterId),
    [session, recoveryCharacterId],
  )

  useEffect(() => {
    if (!delayAfterEntityId) return
    if (!delayTurnOptions.some(option => option.value === delayAfterEntityId)) {
      setDelayAfterEntityId('')
    }
  }, [delayAfterEntityId, delayTurnOptions])

  useEffect(() => {
    if (!combatOver) {
      setLastRecoveredThrownWeapons([])
      setThrownRecoveryError('')
      return undefined
    }
    let cancelled = false
    gameApi.getSession(sessionId)
      .then(data => {
        if (!cancelled) setSession(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [combatOver, sessionId, setSession])

  const handleRecoverThrownWeapons = useCallback(async () => {
    if (!recoveryCharacterId || isRecoveringThrownWeapons) return
    setIsRecoveringThrownWeapons(true)
    setThrownRecoveryError('')
    try {
      const result = await gameApi.recoverThrownWeapons(sessionId, recoveryCharacterId)
      setSession(prev => mergeThrownRecoveryResultIntoSession(prev, result))
      const recovered = result?.recovered || []
      setLastRecoveredThrownWeapons(recovered)
      const summary = formatThrownRecoverySummary(recovered)
      if (summary) {
        addLog({
          role: 'system',
          content: `回收投掷武器：${summary}`,
          log_type: 'system',
          dice_result: result,
        })
      }
    } catch (e) {
      setThrownRecoveryError(e.message || '回收失败')
    } finally {
      setIsRecoveringThrownWeapons(false)
    }
  }, [
    addLog,
    isRecoveringThrownWeapons,
    recoveryCharacterId,
    sessionId,
    setSession,
  ])

  const {
    onSkillClick,
    handleMoveTo,
    handleHelpTarget,
    handleInspectTarget,
    handleSpellHover,
    handleEndTurn,
    handleDelayTurn,
    handleEndConcentration,
    handleCastSpell,
    handleDeathSave,
    handleSmite,
    handleReaction,
    handleCancelReaction,
    handleLegendaryAction,
    handleSkipLegendaryAction,
    handleLairAction,
    handleSkipLairAction,
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
  const tacticalContext = buildCombatTacticalContext({ combat, session })

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
        turnState={turnState}
        skillBar={skillBar}
        selectedTarget={selectedTarget}
        selectedTargetEntity={selectedTargetEntity}
        prediction={prediction}
        moveMode={moveMode}
        helpMode={helpMode}
        isRanged={isRanged}
        selectedWeaponName={selectedWeaponName}
        nextTurnName={nextTurnName}
        nextTurnTone={nextTurnTone}
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
        objectives={objectives}
        terrainDetails={terrainDetails}
        tacticalContext={tacticalContext}
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
        recoverableThrownWeapons={recoverableThrownWeapons}
        recoveredThrownWeapons={lastRecoveredThrownWeapons}
        isRecoveringThrownWeapons={isRecoveringThrownWeapons}
        thrownRecoveryError={thrownRecoveryError}
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
        onRecoverThrownWeapons={handleRecoverThrownWeapons}
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
        canDelayTurn={canDelayTurn && !combatSyncBlocked}
        delayTurnOptions={delayTurnOptions}
        delayAfterEntityId={delayAfterEntityId}
        syncBlocked={combatSyncBlocked}
        moveMode={moveMode}
        helpMode={helpMode}
        isRanged={isRanged}
        selectedWeaponName={selectedWeaponName}
        onSessionChange={runtime.setSession}
        onTurnStateChange={page.setTurnState}
        onError={page.setError}
        onSkillClick={onSkillClick}
        onDeathSave={handleDeathSave}
        onEndTurn={handleEndTurn}
        onDelayTurn={handleDelayTurn}
        onDelayAfterEntityChange={setDelayAfterEntityId}
        onEndConcentration={handleEndConcentration}
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
        onResetAoeCenter={() => {
          setAoeLockedCenter(null)
          setAoeHover(null)
        }}
        onCastSpell={handleCastSpell}
        onCloseSpell={() => { setSpellModalOpen(false); setSpellQuickPick(null); clearAoePreview() }}
        onSpellHover={handleSpellHover}
        maneuverModalOpen={maneuverModalOpen}
        playerSubclassEffects={playerSubclassEffects}
        classResources={classResources}
        onUseManeuver={handleManeuver}
        onCloseManeuver={() => setManeuverModalOpen(false)}
        reactionPrompt={reactionPrompt}
        lairActionPrompt={lairActionPrompt}
        legendaryActionPrompt={legendaryActionPrompt}
        currentCharacterId={effectivePlayerId || playerId}
        onReact={handleReaction}
        onCancelReaction={handleCancelReaction}
        onUseLairAction={handleLairAction}
        onSkipLairAction={handleSkipLairAction}
        onUseLegendaryAction={handleLegendaryAction}
        onSkipLegendaryAction={handleSkipLegendaryAction}
        error={error}
      />
    </div>
  )
}

function getNextInitiativeChip(chips = []) {
  if (!Array.isArray(chips) || chips.length === 0) return null
  const activeIndex = chips.findIndex(chip => chip?.isCur)
  if (activeIndex < 0) return null

  for (let offset = 1; offset < chips.length; offset += 1) {
    const index = (activeIndex + offset) % chips.length
    const chip = chips[index]
    if (chip && !chip.dead) return chip
  }
  return null
}

function getInitiativeChipName(chip) {
  if (!chip) return ''
  return chip.ent?.name || chip.t?.name || ''
}

function getTurnEntryId(entry) {
  return entry?.character_id || entry?.id || ''
}

function buildDelayTurnOptions(combat, entities = {}) {
  const turnOrder = Array.isArray(combat?.turn_order) ? combat.turn_order : []
  if (!turnOrder.length) return []
  const currentIndex = Math.max(0, combat?.current_turn_index ?? 0)
  return turnOrder
    .slice(currentIndex + 1)
    .map(entry => {
      const value = getTurnEntryId(entry)
      if (!value) return null
      const label = entities?.[value]?.name || entry?.name || value
      return { value: String(value), label }
    })
    .filter(Boolean)
}
