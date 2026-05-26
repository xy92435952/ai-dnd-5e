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
    combatOver,
    spellModalOpen,
    setSpellModalOpen,
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
  } = page
  const {
    selectedTarget,
    setSelectedTarget,
    moveMode,
    setMoveMode,
    isRanged,
    showThreat,
    aoePreview,
    setAoePreview,
    aoeHover,
    setAoeHover,
    setHelpMode,
    clearAoePreview,
  } = targeting
  const { logs, logsEndRef } = log
  const controlledPlayerId = room && myCharacterId ? myCharacterId : playerId
  const canDriveAiTurns = canDriveAiCombatTurns({ room, myUserId })

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
  })

  const { onWsEvent, onSkillClick, handleMoveTo, handleSpellHover } = useCombatPageActions({
    sessionId,
    setRoom,
    myCharacterId,
    playerId: controlledPlayerId,
    moveMode,
    isProcessing,
    canActThisTurn: derived.canActThisTurn,
    selectedTarget,
    entityPositions: derived.entityPositions,
    playerPos: derived.playerPos,
    setError,
    setCombat,
    setTurnState,
    setSpellModalOpen,
    setHelpMode,
    handleAttack: flow.handleAttack,
    handleDash: flow.handleDash,
    handleDisengage: flow.handleDisengage,
    handleDodge: flow.handleDodge,
    handleClassFeature: flow.handleClassFeature,
    setMoveMode,
    setAoePreview,
    setAoeHover,
    clearAoePreview,
    onLoadCombat: flow.loadCombat,
    setCombatOver: page.setCombatOver,
  })

  const { connected: wsConnected } = useWebSocket(room ? sessionId : null, onWsEvent)
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
    combatSyncBlocked,
    combatSyncBlockedReason,
    actions: {
      onSkillClick: guardCombatAction(onSkillClick),
      handleMoveTo: guardCombatAction(handleMoveTo),
      handleSpellHover,
      handleEndTurn: guardCombatAction(flow.handleEndTurn),
      handleCastSpell: guardCombatAction(flow.handleCastSpell),
      handleSmite: guardCombatAction(flow.handleSmite),
      handleReaction: guardCombatAction(flow.handleReaction),
      handleManeuver: guardCombatAction(flow.handleManeuver),
      setSelectedTarget,
      setAoeHover,
      setSmitePrompt,
      setSpellModalOpen,
      setManeuverModalOpen,
      setReactionPrompt,
      clearAoePreview,
    },
  }
}
