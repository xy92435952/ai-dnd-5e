import { useCallback } from 'react'
import { gameApi } from '../api/client'
import { getCombatTurnToken, getPlayerTurnState } from '../utils/combat'
import { formatCombatError } from '../utils/combatErrors'
import { formatDelayedTurnLog } from '../utils/turnLogs'

function hasSpentDelayResources(combat, currentEntry) {
  const actorId = currentEntry?.character_id || currentEntry?.id
  if (!actorId) return false
  const turnState = combat?.turn_states?.[actorId] || {}
  return Boolean(
    turnState.action_used
    || turnState.bonus_action_used
    || Number(turnState.movement_used || 0) > 0
    || Number(turnState.attacks_made || 0) > 0
  )
}

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
  const handleTurnAdvance = useCallback(async (options = {}) => {
    const delay = typeof options === 'boolean' ? options : Boolean(options.delay)
    const afterEntityId = typeof options === 'object' ? options.afterEntityId || null : null
    const currentEntry = combat?.turn_order?.[combat?.current_turn_index ?? 0]
    const canDelayAiTurn = delay && canDriveAiTurns && currentEntry && currentEntry.is_player !== true
    if (delay && hasSpentDelayResources(combat, currentEntry)) return
    if (isProcessing || (!canDelayAiTurn && (!canActThisTurn || !isPlayerTurn(combat)))) return
    processingRef.current = true
    setIsProcessing(true)
    setMoveMode(false)
    setHelpMode(false)
    setError('')
    setLairActionPrompt?.(null)
    setLegendaryActionPrompt?.(null)
    try {
      const turnToken = getCombatTurnToken(combat)
      const result = delay
        ? await gameApi.delayTurn(sessionId, turnToken, afterEntityId)
        : await gameApi.endTurn(sessionId, turnToken)
      const lairPrompt = result.lair_action_prompt || null
      const legendaryPrompt = result.legendary_action_prompt || null

      if (delay && result.turn_order_delayed && result.delayed_turn) {
        addLog({
          role: 'system',
          content: formatDelayedTurnLog(result.delayed_turn),
          log_type: 'combat',
          dice_result: {
            type: 'delay_turn',
            ...result.delayed_turn,
          },
        })
      }

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
      if ((e.message || '').includes('token is stale')) {
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

  const handleEndTurn = useCallback(
    () => handleTurnAdvance(false),
    [handleTurnAdvance],
  )
  const handleDelayTurn = useCallback(
    (afterEntityId = null) => handleTurnAdvance({ delay: true, afterEntityId }),
    [handleTurnAdvance],
  )

  return { handleEndTurn, handleDelayTurn }
}
