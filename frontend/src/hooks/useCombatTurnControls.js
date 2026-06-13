import { useCallback } from 'react'
import { gameApi } from '../api/client'
import { getCombatTurnToken, getPlayerTurnState } from '../utils/combat'
import { formatCombatError } from '../utils/combatErrors'

export function useCombatTurnControls({
  sessionId,
  combat,
  isProcessing,
  canActThisTurn = true,
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
  setLairActionPrompt = null,
  setLegendaryActionPrompt = null,
  addLog,
  triggerAiTurn,
  canDriveAiTurns = true,
}) {
  const handleEndTurn = useCallback(async () => {
    if (!canActThisTurn || !isPlayerTurn(combat) || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    setMoveMode(false)
    setHelpMode(false)
    setError('')
    setLairActionPrompt?.(null)
    setLegendaryActionPrompt?.(null)
    try {
      const turnToken = getCombatTurnToken(combat)
      const result = await gameApi.endTurn(sessionId, turnToken)
      const lairPrompt = result.lair_action_prompt || null
      const legendaryPrompt = result.legendary_action_prompt || null

      if (result.expired_conditions?.length) {
        result.expired_conditions.forEach(msg => addLog({ role: 'system', content: msg, log_type: 'system' }))
      }
      if (result.turn_start_hazard_log) {
        addLog({
          role: 'system',
          content: result.turn_start_hazard_log,
          log_type: 'combat',
          dice_result: result.turn_start_hazard
            ? {
                damage: result.turn_start_hazard.final_damage ?? result.turn_start_hazard.damage ?? 0,
                hazard: result.turn_start_hazard,
              }
            : null,
        })
      }

      if (result.combat_over) {
        setLairActionPrompt?.(null)
        setLegendaryActionPrompt?.(null)
        setCombatOver(result.outcome)
        return
      }
      if (lairPrompt) setLairActionPrompt?.(lairPrompt)
      if (legendaryPrompt) setLegendaryActionPrompt?.(legendaryPrompt)

      setCombat(prev => {
        if (!prev) return prev
        return {
          ...prev,
          current_turn_index: result.next_turn_index,
          round_number: result.round_number,
        }
      })

      processingRef.current = false
      setIsProcessing(false)

      try {
        const fresh = await gameApi.getCombat(sessionId)
        if (fresh) {
          setCombat(fresh)
          const nextEntry = fresh.turn_order?.[fresh.current_turn_index]
          if (lairPrompt || legendaryPrompt) {
            if (nextEntry?.is_player) setTurnState(getPlayerTurnState(fresh, nextEntry.character_id))
          } else if (canDriveAiTurns && nextEntry && !nextEntry.is_player) {
            aiTimer.current = setTimeout(() => triggerAiTurn(), 600)
          } else if (nextEntry?.is_player) {
            setTurnState(getPlayerTurnState(fresh, nextEntry.character_id))
          }
        }
      } catch {
        // Keep the locally advanced state when the refresh fails.
      }
    } catch (e) {
      if ((e.message || '').includes('End turn token is stale')) {
        try {
          const fresh = await gameApi.getCombat(sessionId)
          if (fresh) setCombat(fresh)
        } catch {
          // Leave the current view in place when refresh also fails.
        }
        processingRef.current = false
        setIsProcessing(false)
        return
      }
      setError(formatCombatError(e))
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    aiTimer,
    canDriveAiTurns,
    combat,
    canActThisTurn,
    isPlayerTurn,
    isProcessing,
    processingRef,
    sessionId,
    setCombat,
    setCombatOver,
    setError,
    setHelpMode,
    setIsProcessing,
    setLairActionPrompt,
    setLegendaryActionPrompt,
    setMoveMode,
    setTurnState,
    triggerAiTurn,
  ])

  return { handleEndTurn }
}
