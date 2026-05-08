import { useWebSocket } from './useWebSocket'
import { useCombatSkillBar } from './useCombatSkillBar'
import { useCombatSpells } from './useCombatSpells'
import { useCombatDerivedState } from './useCombatDerivedState'
import { useCombatFlowHandlers } from './useCombatFlowHandlers'
import { useCombatPrediction } from './useCombatPrediction'
import { useCombatPageActions } from './useCombatPageActions'
import { COMBAT_GRID } from '../utils/combatPage'

export function useCombatRuntime({
  sessionId,
  room,
  setRoom,
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

  const spells = useCombatSpells(sessionId)
  const skillBarV10 = useCombatSkillBar({
    sessionId,
    playerId,
    refreshKey: playerSpellSlots,
  })
  const flow = useCombatFlowHandlers({
    sessionId,
    showDice,
    page,
    targeting,
    log,
  })
  const prediction = useCombatPrediction({
    sessionId,
    playerId,
    selectedTarget,
    playerClass,
    isRanged,
  })

  const derived = useCombatDerivedState({
    combat,
    room,
    myCharacterId,
    playerId,
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

  const { onWsEvent, onSkillClick, handleMoveTo, handleSpellHover } = useCombatPageActions({
    sessionId,
    setRoom,
    myCharacterId,
    moveMode,
    isProcessing,
    isPlayerTurn: derived.isPlayerTurn,
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
  })

  useWebSocket(room ? sessionId : null, onWsEvent)

  return {
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
    logs,
    logsEndRef,
    derived,
    actions: {
      onSkillClick,
      handleMoveTo,
      handleSpellHover,
      handleEndTurn: flow.handleEndTurn,
      handleCastSpell: flow.handleCastSpell,
      handleSmite: flow.handleSmite,
      handleReaction: flow.handleReaction,
      handleManeuver: flow.handleManeuver,
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
