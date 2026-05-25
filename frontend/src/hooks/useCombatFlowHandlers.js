import { useCallback } from 'react'
import { useCombatAiTurns } from './useCombatAiTurns'
import { useCombatAttackFlow } from './useCombatAttackFlow'
import { useCombatLoader } from './useCombatLoader'
import { useCombatPlayerActions } from './useCombatPlayerActions'
import { useCombatSpecialActions } from './useCombatSpecialActions'
import { useCombatSpellFlow } from './useCombatSpellFlow'
import { useCombatTurnControls } from './useCombatTurnControls'
import { isPlayerCombatTurn } from '../utils/combat'

export function useCombatFlowHandlers({
  sessionId,
  showDice,
  page,
  targeting,
  log,
  controlledPlayerId = null,
  canActThisTurn = true,
  canDriveAiTurns = true,
}) {
  const {
    combat,
    setCombat,
    isProcessing,
    setIsProcessing,
    setCombatOver,
    setSpellModalOpen,
    setPlayerSpellSlots,
    setPlayerKnownSpells,
    setPlayerCantrips,
    playerId,
    setPlayerId,
    setTurnState,
    smitePrompt,
    setSmitePrompt,
    setPlayerClass,
    setPlayerLevel,
    setClassResources,
    setPlayerSubclass,
    setPlayerSubclassEffects,
    playerSubclassEffects,
    setReactionPrompt,
    initiativeShown,
    setInitiativeShown,
    setSession,
    aiTimer,
    processingRef,
    setError,
  } = page
  const {
    selectedTarget,
    setSelectedTarget,
    setMoveMode,
    isRanged,
    setHelpMode,
  } = targeting
  const { setLogs, addLog } = log
  const actorId = controlledPlayerId || playerId

  const isPlayerTurn = useCallback((combatState) => isPlayerCombatTurn(combatState), [])

  const { triggerAiTurn } = useCombatAiTurns({
    sessionId,
    processingRef,
    setIsProcessing,
    setCombat,
    setTurnState,
    setReactionPrompt,
    setCombatOver,
    addLog,
    showDice,
  })

  const { loadCombat } = useCombatLoader({
    sessionId,
    initiativeShown,
    aiTimer,
    setCombat,
    setSession,
    setPlayerId,
    setPlayerSpellSlots,
    setPlayerKnownSpells,
    setPlayerCantrips,
    setPlayerClass,
    setPlayerLevel,
    setClassResources,
    setPlayerSubclass,
    setPlayerSubclassEffects,
    setTurnState,
    setLogs,
    setInitiativeShown,
    setError,
    showDice,
    triggerAiTurn,
    isPlayerTurn,
    canDriveAiTurns,
  })

  const { handleEndTurn } = useCombatTurnControls({
    sessionId,
    combat,
    isProcessing,
    canActThisTurn,
    isPlayerTurn,
    processingRef,
    aiTimer,
    setIsProcessing,
    setMoveMode,
    setHelpMode,
    setError,
    setCombat,
    setTurnState,
    setCombatOver,
    addLog,
    triggerAiTurn,
    canDriveAiTurns,
  })

  const handleAttack = useCombatAttackFlow({
    sessionId,
    playerId: actorId,
    selectedTarget,
    isRanged,
    combat,
    isProcessing,
    canActThisTurn,
    isPlayerTurn,
    processingRef,
    setIsProcessing,
    setError,
    showDice,
    addLog,
    setTurnState,
    setCombat,
    setSelectedTarget,
    setSmitePrompt,
    setCombatOver,
  })

  const handleCastSpell = useCombatSpellFlow({
    sessionId,
    playerId: actorId,
    selectedTarget,
    isProcessing,
    canActThisTurn,
    processingRef,
    setIsProcessing,
    setSpellModalOpen,
    setError,
    setTurnState,
    setCombat,
    setPlayerSpellSlots,
    addLog,
    setSelectedTarget,
    setCombatOver,
    showDice,
  })

  const {
    handleClassFeature,
    handleDodge,
    handleDash,
    handleDisengage,
  } = useCombatPlayerActions({
    sessionId,
    playerId: actorId,
    combat,
    isProcessing,
    canActThisTurn,
    isPlayerTurn,
    processingRef,
    setIsProcessing,
    setError,
    setTurnState,
    setClassResources,
    setCombat,
    showDice,
    addLog,
  })

  const {
    handleSmite,
    handleReaction,
    handleManeuver,
  } = useCombatSpecialActions({
    sessionId,
    selectedTarget,
    isProcessing,
    canActThisTurn,
    smitePrompt,
    playerSubclassEffects,
    processingRef,
    setIsProcessing,
    setError,
    setSmitePrompt,
    setPlayerSpellSlots,
    setTurnState,
    setClassResources,
    setCombat,
    setReactionPrompt,
    setCombatOver,
    triggerAiTurn,
    showDice,
    addLog,
  })

  return {
    isPlayerTurn,
    loadCombat,
    handleEndTurn,
    handleAttack,
    handleCastSpell,
    handleClassFeature,
    handleDodge,
    handleDash,
    handleDisengage,
    handleSmite,
    handleReaction,
    handleManeuver,
  }
}
