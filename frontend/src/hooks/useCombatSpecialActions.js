import { useCallback } from 'react'
import { gameApi } from '../api/client'
import { rollDice3D } from '../components/DiceRollerOverlay'
import { applyHpUpdate } from '../utils/combat'

export function useCombatSpecialActions({
  sessionId,
  selectedTarget,
  isProcessing,
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
}) {
  const handleSmite = useCallback(async (slotLevel) => {
    if (isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    const currentSmiteTarget = smitePrompt?.targetId
    setSmitePrompt(null)
    try {
      const smiteDiceCount = 2 + (slotLevel - 1)
      const { total: smiteTotal, rolls: smiteRolls } = await rollDice3D(8, smiteDiceCount)
      showDice({ faces: 8, result: smiteTotal, label: '神圣斩击', count: smiteDiceCount })

      const result = await gameApi.smite(sessionId, slotLevel, false, smiteRolls, currentSmiteTarget)

      addLog({ role: 'player', content: result.narration, log_type: 'combat' })
      if (result.remaining_slots) setPlayerSpellSlots(result.remaining_slots)
      setCombat(prev => {
        if (!prev) return prev
        return applyHpUpdate(prev, currentSmiteTarget, result.target_new_hp)
      })
      if (result.combat_over) setCombatOver(result.outcome)
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
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
    setPlayerSpellSlots,
    setSmitePrompt,
    showDice,
    smitePrompt,
  ])

  const handleReaction = useCallback(async (reactionType, targetId = null, characterId = null) => {
    setReactionPrompt(null)
    processingRef.current = true
    setIsProcessing(true)
    try {
      if (reactionType === 'hellish_rebuke') {
        const { total } = await rollDice3D(10, 2)
        showDice({ faces: 10, result: total, label: '地狱斥责 2d10', count: 2 })
      }
      const result = await gameApi.useReaction(sessionId, reactionType, targetId, characterId)
      addLog({ role: 'player', content: result.narration, log_type: 'combat' })
      if (result.turn_state) setTurnState(result.turn_state)
      processingRef.current = false
      setIsProcessing(false)
      triggerAiTurn()
    } catch (e) {
      setError(e.message)
      processingRef.current = false
      setIsProcessing(false)
      triggerAiTurn()
    }
  }, [
    addLog,
    processingRef,
    sessionId,
    setError,
    setIsProcessing,
    setReactionPrompt,
    setTurnState,
    showDice,
    triggerAiTurn,
  ])

  const handleManeuver = useCallback(async (maneuverName) => {
    if (isProcessing || !selectedTarget) return
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
      })
      if (result.turn_state) setTurnState(result.turn_state)
      if (result.class_resources) setClassResources(result.class_resources)
      setCombat(prev => {
        if (!prev) return prev
        if (result.target_new_hp !== undefined && result.target_new_hp !== null) {
          return applyHpUpdate(prev, selectedTarget, result.target_new_hp)
        }
        return prev
      })
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
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
    handleManeuver,
  }
}
