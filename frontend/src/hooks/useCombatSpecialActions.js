import { useCallback } from 'react'
import { gameApi } from '../api/client'
import { rollDice3D } from '../components/DiceRollerOverlay'
import { applyActionResultEntityStates } from '../utils/combat'
import { formatCombatError } from '../utils/combatErrors'
import { buildCombatStateChangeSummary } from '../utils/combatLog'

export function useCombatSpecialActions({
  sessionId,
  selectedTarget,
  isProcessing,
  canActThisTurn = true,
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
}) {
  const handleSmite = useCallback(async (slotLevel) => {
    if (!canActThisTurn || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    const currentSmiteTarget = smitePrompt?.targetId
    const currentSmiteIsCrit = Boolean(smitePrompt?.isCrit)
    setSmitePrompt(null)
    try {
      const smiteDiceCount = (2 + (slotLevel - 1)) * (currentSmiteIsCrit ? 2 : 1)
      const { total: smiteTotal, rolls: smiteRolls } = await rollDice3D(8, smiteDiceCount)
      showDice({ faces: 8, result: smiteTotal, label: '神圣斩击', count: smiteDiceCount })

      const result = await gameApi.smite(sessionId, slotLevel, false, smiteRolls, currentSmiteTarget, currentSmiteIsCrit)

      addLog({
        role: 'player',
        content: result.narration,
        log_type: 'combat',
        state_changes: buildCombatStateChangeSummary(result, {
          targetName: currentSmiteTarget,
        }),
      })
      if (result.remaining_slots) setPlayerSpellSlots(result.remaining_slots)
      setCombat(prev => {
        if (!prev) return prev
        return applyActionResultEntityStates(prev, {
          ...result,
          target_id: result.target_id || currentSmiteTarget,
        })
      })
      if (result.combat_over) setCombatOver(result.outcome)
    } catch (e) {
      setError(formatCombatError(e))
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    canActThisTurn,
    isProcessing,
    processingRef,
    sessionId,
    setCombat,
    setCombatOver,
    setError,
    setIsProcessing,
    setPlayerSpellSlots,
    setSmitePrompt,
    showDice,
    smitePrompt,
  ])

  const handleReaction = useCallback(async (reactionType, targetId = null, characterId = null) => {
    if (isProcessing || processingRef.current) return
    setReactionPrompt(null)
    processingRef.current = true
    setIsProcessing(true)
    try {
      if (reactionType === 'hellish_rebuke') {
        const { total } = await rollDice3D(10, 2)
        showDice({ faces: 10, result: total, label: '地狱斥责 2d10', count: 2 })
      }
      const result = await gameApi.useReaction(sessionId, reactionType, targetId, characterId)
      const reactionTargetName = result.target_state?.target_name || result.target_name || characterId || '反应者'
      addLog({
        role: 'player',
        content: result.narration,
        log_type: 'combat',
        state_changes: buildCombatStateChangeSummary(result, {
          targetName: reactionTargetName,
        }),
      })
      if (result.remaining_slots) setPlayerSpellSlots(result.remaining_slots)
      if (result.turn_state) setTurnState(result.turn_state)
      setCombat(prev => {
        if (!prev) return prev
        return applyActionResultEntityStates(prev, result)
      })
      if (result.combat_over) setCombatOver(result.outcome)
      if (result.lair_action_prompt) {
        setLairActionPrompt?.(result.lair_action_prompt)
        setLegendaryActionPrompt?.(null)
      } else if (result.legendary_action_prompt) {
        setLegendaryActionPrompt?.(result.legendary_action_prompt)
      }
      processingRef.current = false
      setIsProcessing(false)
      if (!result.lair_action_prompt && !result.legendary_action_prompt) triggerAiTurn()
    } catch (e) {
      setError(formatCombatError(e))
      processingRef.current = false
      setIsProcessing(false)
      triggerAiTurn()
    }
  }, [
    addLog,
    isProcessing,
    processingRef,
    sessionId,
    setCombat,
    setCombatOver,
    setError,
    setIsProcessing,
    setLairActionPrompt,
    setLegendaryActionPrompt,
    setPlayerSpellSlots,
    setReactionPrompt,
    setTurnState,
    showDice,
    triggerAiTurn,
  ])

  const handleCancelReaction = useCallback(async (prompt = null) => {
    setReactionPrompt(null)
    processingRef.current = true
    setIsProcessing(true)
    let followupPrompt = null
    try {
      const result = await gameApi.useReaction(
        sessionId,
        'decline',
        prompt.target_id || prompt.attacker_id || null,
        prompt.reactor_character_id || null,
      )
      followupPrompt = result?.lair_action_prompt || result?.legendary_action_prompt || null
      if (result?.lair_action_prompt) {
        setLairActionPrompt?.(result.lair_action_prompt)
        setLegendaryActionPrompt?.(null)
      } else if (result?.legendary_action_prompt) {
        setLegendaryActionPrompt?.(result.legendary_action_prompt)
      }
    } catch (e) {
      setError(formatCombatError(e))
    } finally {
      processingRef.current = false
      setIsProcessing(false)
      if (!followupPrompt) triggerAiTurn()
    }
  }, [
    processingRef,
    sessionId,
    setError,
    setIsProcessing,
    setLairActionPrompt,
    setLegendaryActionPrompt,
    setReactionPrompt,
    triggerAiTurn,
  ])

  const handleManeuver = useCallback(async (maneuverName) => {
    if (!canActThisTurn || isProcessing || !selectedTarget) return
    processingRef.current = true
    setIsProcessing(true)
    setError('')
    try {
      const sdFaces = parseInt((playerSubclassEffects?.superiority_die || 'd8').replace('d', '')) || 8
      const { total: sdTotal } = await rollDice3D(sdFaces)
      showDice({ faces: sdFaces, result: sdTotal, label: `战技·${maneuverName}` })

      const result = await gameApi.maneuver(sessionId, maneuverName, selectedTarget)
      addLog({
        role: 'player',
        content: result.narration || result.description,
        log_type: 'combat',
        dice_result: result.superiority_die_roll ? {
          type: 'maneuver',
          value: result.superiority_die_roll,
          die: result.superiority_die,
        } : null,
        state_changes: buildCombatStateChangeSummary(result, {
          targetName: selectedTarget,
        }),
      })
      if (result.turn_state) setTurnState(result.turn_state)
      if (result.class_resources) setClassResources(result.class_resources)
      setCombat(prev => {
        if (!prev) return prev
        return applyActionResultEntityStates(prev, {
          ...result,
          target_id: result.target_id || selectedTarget,
        })
      })
    } catch (e) {
      setError(formatCombatError(e))
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    canActThisTurn,
    isProcessing,
    playerSubclassEffects,
    processingRef,
    selectedTarget,
    sessionId,
    setClassResources,
    setCombat,
    setError,
    setIsProcessing,
    setTurnState,
    showDice,
  ])

  return {
    handleSmite,
    handleReaction,
    handleCancelReaction,
    handleManeuver,
  }
}
