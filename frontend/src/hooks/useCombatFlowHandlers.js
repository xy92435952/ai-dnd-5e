import { useCallback } from 'react'
import { useCombatAiTurns } from './useCombatAiTurns'
import { useCombatAttackFlow } from './useCombatAttackFlow'
import { useCombatLoader } from './useCombatLoader'
import { useCombatPlayerActions } from './useCombatPlayerActions'
import { useCombatSpecialActions } from './useCombatSpecialActions'
import { useCombatSpellFlow } from './useCombatSpellFlow'
import { useCombatTurnControls } from './useCombatTurnControls'
import { isMyCombatTurn, isPlayerCombatTurn } from '../utils/combat'

export function useCombatFlowHandlers({
  sessionId,
  room,
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
    moveMode,
    setMoveMode,
    isRanged,
    setHelpMode,
  } = targeting
  const { setLogs, addLog } = log

  const isHumanPlayerTurn = useCallback((combatState) => isPlayerCombatTurn(combatState), [])
  const canActInCombat = useCallback((combatState) => {
    if (room?.is_multiplayer) {
      return isMyCombatTurn({ room, combat: combatState, myCharacterId })
    }
    return isPlayerCombatTurn(combatState)
  }, [room, myCharacterId])

  const { triggerAiTurn } = useCombatAiTurns({
    sessionId,
    playerId,
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
    setReactionPrompt,
    setLogs,
    setInitiativeShown,
    setError,
    showDice,
    triggerAiTurn,
    isPlayerTurn: isHumanPlayerTurn,
  })

  const { handleEndTurn } = useCombatTurnControls({
    sessionId,
    combat,
    isProcessing,
    isPlayerTurn: canActInCombat,
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
  })

  const handleAttack = useCombatAttackFlow({
    sessionId,
    playerId,
    selectedTarget,
    isRanged,
    combat,
    isProcessing,
    isPlayerTurn: canActInCombat,
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
    playerId,
    selectedTarget,
    isProcessing,
    isPlayerTurn: canActInCombat,
    combat,
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
    playerId,
    combat,
    isProcessing,
    isPlayerTurn: canActInCombat,
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
    isPlayerTurn: canActInCombat,
    combat,
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
    isPlayerTurn: canActInCombat,
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
