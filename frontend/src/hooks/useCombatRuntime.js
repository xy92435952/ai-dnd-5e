import { useCallback } from 'react'
import { useWebSocket } from './useWebSocket'
import { useCombatSkillBar } from './useCombatSkillBar'
import { useCombatSpells } from './useCombatSpells'
import { useCombatDerivedState } from './useCombatDerivedState'
import { useCombatFlowHandlers } from './useCombatFlowHandlers'
import { useCombatPrediction } from './useCombatPrediction'
import { useCombatPageActions } from './useCombatPageActions'
import { useCombatReconnectRefresh } from './useCombatReconnectRefresh'
import { COMBAT_GRID } from '../utils/combatPage'
import { canDriveAiCombatTurns } from '../utils/combat'

export function useCombatRuntime({
  sessionId,
  navigate,
  room,
  setRoom,
  refreshRoom,
  myUserId,
  myCharacterId,
  showDice,
  page,
  targeting,
  log,
}) {
  const {
    combat,
    setCombat,
    isProcessing,
    setIsProcessing,
    combatOver,
    setCombatOver,
    spellModalOpen,
    setSpellModalOpen,
    spellQuickPick,
    setSpellQuickPick,
    playerSpellSlots,
    playerKnownSpells,
    playerCantrips,
    playerId,
    turnState,
    setTurnState,
    smitePrompt,
    setSmitePrompt,
    playerClass,
    playerLevel,
    classResources,
    playerSubclass,
    playerSubclassEffects,
    maneuverModalOpen,
    setManeuverModalOpen,
    reactionPrompt,
    setReactionPrompt,
    session,
    setSession,
    setError,
    aiTimer,
    processingRef,
  } = page
  const {
    selectedTarget,
    setSelectedTarget,
    moveMode,
    setMoveMode,
    helpMode,
    isRanged,
    showThreat,
    aoePreview,
    setAoePreview,
    aoeHover,
    setAoeHover,
    aoeLockedCenter,
    setAoeLockedCenter,
    setHelpMode,
    clearAoePreview,
  } = targeting
  const { logs, logsEndRef, addLog } = log
  const controlledPlayerId = room && myCharacterId ? myCharacterId : playerId
  const canDriveAiTurns = canDriveAiCombatTurns({ room, myUserId })
  const handleCombatEnded = useCallback((outcome = 'ended') => {
    if (aiTimer.current) {
      clearTimeout(aiTimer.current)
      aiTimer.current = null
    }
    processingRef.current = false
    setIsProcessing(false)
    setCombat(null)
    setTurnState(null)
    setReactionPrompt(null)
    setCombatOver(outcome)
    setMoveMode(false)
    setHelpMode(false)
    setSelectedTarget(null)
    clearAoePreview()
    setError('')
    navigate?.(`/adventure/${sessionId}`)
  }, [
    aiTimer,
    clearAoePreview,
    navigate,
    processingRef,
    sessionId,
    setCombat,
    setCombatOver,
    setError,
    setHelpMode,
    setIsProcessing,
    setMoveMode,
    setReactionPrompt,
    setSelectedTarget,
    setTurnState,
  ])

  const spells = useCombatSpells(sessionId)
  const skillBarV10 = useCombatSkillBar({
    sessionId,
    playerId: controlledPlayerId,
    refreshKey: playerSpellSlots,
  })
  const prediction = useCombatPrediction({
    sessionId,
    playerId: controlledPlayerId,
    selectedTarget,
    playerClass,
    isRanged,
  })

  const derived = useCombatDerivedState({
    combat,
    room,
    myCharacterId,
    playerId: controlledPlayerId,
    selectedTarget,
    showThreat,
    aoePreview,
    aoeHover,
    aoeLockedCenter,
    spells,
    playerKnownSpells,
    playerCantrips,
    playerClass,
    skillBarV10,
    gridWidth: COMBAT_GRID.width,
    gridHeight: COMBAT_GRID.height,
    viewWidth: COMBAT_GRID.viewWidth,
    viewHeight: COMBAT_GRID.viewHeight,
  })

  const flow = useCombatFlowHandlers({
    sessionId,
    showDice,
    page,
    targeting,
    log,
    controlledPlayerId,
    canActThisTurn: derived.canActThisTurn,
    canDriveAiTurns,
    onCombatEnded: handleCombatEnded,
  })

  const { onWsEvent, onSkillClick, handleMoveTo, handleHelpTarget, handleInspectTarget, handleSpellHover } = useCombatPageActions({
    sessionId,
    setRoom,
    myCharacterId,
    playerId: controlledPlayerId,
    moveMode,
    helpMode,
    isProcessing,
    setIsProcessing,
    canActThisTurn: derived.canActThisTurn,
    selectedTarget,
    entities: derived.entities,
    entityPositions: derived.entityPositions,
    playerPos: derived.playerPos,
    setError,
    setCombat,
    setTurnState,
    setReactionPrompt,
    addLog,
    setSpellModalOpen,
    setSpellQuickPick,
    setHelpMode,
    handleAttack: flow.handleAttack,
    handleDash: flow.handleDash,
    handleDisengage: flow.handleDisengage,
    handleDodge: flow.handleDodge,
    handleHealingPotion: flow.handleHealingPotion,
    handleClassFeature: flow.handleClassFeature,
    setMoveMode,
    setAoePreview,
    setAoeHover,
    setAoeLockedCenter,
    clearAoePreview,
    onLoadCombat: flow.loadCombat,
    setCombatOver: page.setCombatOver,
    onCombatEnded: handleCombatEnded,
    combat,
  })

  const { connected: wsConnected, status: wsStatus } = useWebSocket(room ? sessionId : null, onWsEvent)
  const combatSyncBlocked = !!room && !wsConnected
  const combatSyncBlockedReason = combatSyncBlocked ? '战斗房间正在重新同步，请恢复连接后再行动。' : ''

  useCombatReconnectRefresh({
    room,
    combat,
    wsConnected,
    loadCombat: flow.loadCombat,
    refreshRoom,
  })

  const guardCombatAction = (fn) => (...args) => {
    if (combatSyncBlocked) {
      setError(combatSyncBlockedReason)
      return undefined
    }
    return fn?.(...args)
  }

  return {
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
    prediction,
    logs,
    logsEndRef,
    derived,
    wsConnected,
    wsStatus,
    combatSyncBlocked,
    combatSyncBlockedReason,
    actions: {
      onSkillClick: guardCombatAction(onSkillClick),
      handleMoveTo: guardCombatAction(handleMoveTo),
      handleHelpTarget: guardCombatAction(handleHelpTarget),
      handleInspectTarget: guardCombatAction(handleInspectTarget),
      handleSpellHover,
      handleEndTurn: guardCombatAction(flow.handleEndTurn),
      handleCastSpell: guardCombatAction(flow.handleCastSpell),
      handleDeathSave: guardCombatAction(flow.handleDeathSave),
      handleSmite: guardCombatAction(flow.handleSmite),
      handleReaction: guardCombatAction(flow.handleReaction),
      handleCancelReaction: guardCombatAction(flow.handleCancelReaction),
      handleManeuver: guardCombatAction(flow.handleManeuver),
      setSelectedTarget,
      setAoeHover,
      setAoeLockedCenter,
      setSmitePrompt,
      setSpellModalOpen,
      setSpellQuickPick,
      setManeuverModalOpen,
      setReactionPrompt,
      clearAoePreview,
    },
  }
}
