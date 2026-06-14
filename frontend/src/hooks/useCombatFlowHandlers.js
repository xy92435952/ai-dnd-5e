import { useCallback } from 'react'
import { useCombatAiTurns } from './useCombatAiTurns'
import { useCombatAttackFlow } from './useCombatAttackFlow'
import { useCombatLoader } from './useCombatLoader'
import { useCombatDeathSave } from './useCombatDeathSave'
import { useCombatPlayerActions } from './useCombatPlayerActions'
import { useCombatSpecialActions } from './useCombatSpecialActions'
import { useCombatSpellFlow } from './useCombatSpellFlow'
import { useCombatTurnControls } from './useCombatTurnControls'
import { gameApi } from '../api/client'
import { applyActionResultEntityStates, getPlayerTurnState, isPlayerCombatTurn } from '../utils/combat'
import { formatCombatError } from '../utils/combatErrors'
import { buildCombatStateChangeSummary } from '../utils/combatLog'

export function useCombatFlowHandlers({
  sessionId,
  showDice,
  page,
  targeting,
  log,
  controlledPlayerId = null,
  canActThisTurn = true,
  canDriveAiTurns = true,
  prediction = null,
  onCombatEnded,
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
    classResources,
    useLuckyAttack,
    setUseLuckyAttack,
    setPlayerSubclass,
    setPlayerSubclassEffects,
    playerSubclassEffects,
    setReactionPrompt,
    setLegendaryActionPrompt,
    setLairActionPrompt,
    initiativeShown,
    setInitiativeShown,
    session,
    setSession,
    aiTimer,
    processingRef,
    setError,
  } = page
  const {
    selectedTarget,
    setSelectedTarget,
    aoeLockedCenter,
    setMoveMode,
    isRanged,
    selectedWeaponName,
    setHelpMode,
  } = targeting
  const { setLogs, addLog } = log
  const actorId = controlledPlayerId || playerId

  const isPlayerTurn = useCallback((combatState) => isPlayerCombatTurn(combatState), [])

  const { triggerAiTurn } = useCombatAiTurns({
    sessionId,
    playerId: actorId,
    processingRef,
    setIsProcessing,
    setCombat,
    setTurnState,
    setReactionPrompt,
    setLairActionPrompt,
    setLegendaryActionPrompt,
    setCombatOver,
    addLog,
    showDice,
  })

  const continueAfterLegendaryWindow = useCallback((combatState = combat) => {
    const nextEntry = combatState?.turn_order?.[combatState.current_turn_index]
    if (canDriveAiTurns && nextEntry && !nextEntry.is_player) {
      aiTimer.current = setTimeout(() => triggerAiTurn(), 600)
    } else if (nextEntry?.is_player) {
      setTurnState(getPlayerTurnState(combatState, nextEntry.character_id))
    }
  }, [aiTimer, canDriveAiTurns, combat, setTurnState, triggerAiTurn])

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
    onCombatEnded,
    showDice,
    triggerAiTurn,
    isPlayerTurn,
    canDriveAiTurns,
  })

  const { handleEndTurn, handleDelayTurn } = useCombatTurnControls({
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
    setLairActionPrompt,
    setLegendaryActionPrompt,
    addLog,
    triggerAiTurn,
    canDriveAiTurns,
  })

  const handleAttack = useCombatAttackFlow({
    sessionId,
    playerId: actorId,
    selectedTarget,
    isRanged,
    selectedWeaponName,
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
    prediction,
    classResources,
    useLuckyAttack,
    setUseLuckyAttack,
    setClassResources,
  })

  const handleCastSpell = useCombatSpellFlow({
    sessionId,
    playerId: actorId,
    selectedTarget,
    aoeHover: aoeLockedCenter || targeting.aoeHover,
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
    combat,
    prediction,
  })

  const handleEndConcentration = useCallback(async () => {
    if (!actorId || isProcessing || processingRef.current) return
    processingRef.current = true
    setIsProcessing(true)
    setError('')
    try {
      const result = await gameApi.endConcentration(sessionId, actorId)
      setCombat(prev => applyActionResultEntityStates(prev, result))
      addLog({
        role: 'player',
        content: result.narration || '结束专注',
        log_type: 'combat',
        dice_result: result,
        state_changes: buildCombatStateChangeSummary(result),
      })
    } catch (e) {
      setError(formatCombatError(e))
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    actorId,
    addLog,
    isProcessing,
    processingRef,
    sessionId,
    setCombat,
    setError,
    setIsProcessing,
  ])

  const handleLegendaryAction = useCallback(async (actorId, actionId = null, targetId = null) => {
    if (!actorId || isProcessing || processingRef.current) return
    setLegendaryActionPrompt(null)
    processingRef.current = true
    setIsProcessing(true)
    setError('')
    try {
      const result = await gameApi.useLegendaryAction(sessionId, actorId, actionId, targetId)
      addLog({
        role: 'system',
        content: result.narration || result.log_msg || '传奇动作',
        log_type: 'combat',
        dice_result: result.dice_result || result.legendary_action || null,
        state_changes: buildCombatStateChangeSummary(result),
      })
      setCombat(prev => applyActionResultEntityStates(prev, result))
      if (result.player_can_react && result.reaction_prompt) {
        setReactionPrompt(result.reaction_prompt)
        if (result.combat) setCombat(result.combat)
        return
      }
      try {
        const fresh = await gameApi.getCombat(sessionId)
        if (fresh) {
          setCombat(fresh)
          continueAfterLegendaryWindow(fresh)
        } else {
          continueAfterLegendaryWindow()
        }
      } catch {
        continueAfterLegendaryWindow()
      }
    } catch (e) {
      setError(formatCombatError(e))
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    continueAfterLegendaryWindow,
    isProcessing,
    processingRef,
    sessionId,
    setCombat,
    setError,
    setIsProcessing,
    setLegendaryActionPrompt,
    setReactionPrompt,
  ])

  const handleSkipLegendaryAction = useCallback(() => {
    setLegendaryActionPrompt(null)
    continueAfterLegendaryWindow()
  }, [continueAfterLegendaryWindow, setLegendaryActionPrompt])

  const handleLairAction = useCallback(async (sourceId, actionId = null, targetId = null) => {
    if (isProcessing || processingRef.current) return
    setLairActionPrompt(null)
    processingRef.current = true
    setIsProcessing(true)
    setError('')
    try {
      const result = await gameApi.useLairAction(sessionId, sourceId, actionId, targetId)
      addLog({
        role: 'system',
        content: result.narration || result.log_msg || '巢穴动作',
        log_type: 'combat',
        dice_result: result.dice_result || result.lair_action || null,
        state_changes: buildCombatStateChangeSummary(result),
      })
      setCombat(prev => applyActionResultEntityStates(prev, result))
      if (result.player_can_react && result.reaction_prompt) {
        setReactionPrompt(result.reaction_prompt)
        if (result.combat) setCombat(result.combat)
        return
      }
      try {
        const fresh = await gameApi.getCombat(sessionId)
        if (fresh) {
          setCombat(fresh)
          continueAfterLegendaryWindow(fresh)
        } else {
          continueAfterLegendaryWindow()
        }
      } catch {
        continueAfterLegendaryWindow()
      }
    } catch (e) {
      setError(formatCombatError(e))
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    continueAfterLegendaryWindow,
    isProcessing,
    processingRef,
    sessionId,
    setCombat,
    setError,
    setIsProcessing,
    setLairActionPrompt,
    setReactionPrompt,
  ])

  const handleSkipLairAction = useCallback(() => {
    setLairActionPrompt(null)
    continueAfterLegendaryWindow()
  }, [continueAfterLegendaryWindow, setLairActionPrompt])

  const handleDeathSave = useCombatDeathSave({
    sessionId,
    playerId: actorId,
    isProcessing,
    canActThisTurn,
    processingRef,
    setIsProcessing,
    setError,
    setCombat,
    setSession,
    showDice,
    addLog,
  })

  const {
    handleClassFeature,
    handleHealingPotion,
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
    session,
    setSession,
    showDice,
    addLog,
  })

  const {
    handleSmite,
    handleReaction,
    handleCancelReaction,
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
    setLairActionPrompt,
    setLegendaryActionPrompt,
    setCombatOver,
    triggerAiTurn,
    showDice,
    addLog,
  })

  return {
    isPlayerTurn,
    loadCombat,
    handleEndTurn,
    handleDelayTurn,
    handleAttack,
    handleCastSpell,
    handleEndConcentration,
    handleDeathSave,
    handleClassFeature,
    handleHealingPotion,
    handleDodge,
    handleDash,
    handleDisengage,
    handleSmite,
    handleReaction,
    handleCancelReaction,
    handleLegendaryAction,
    handleSkipLegendaryAction,
    handleLairAction,
    handleSkipLairAction,
    handleManeuver,
  }
}
