import { useCallback } from 'react'
import { gameApi } from '../api/game'
import { getPlayerTurnState } from '../utils/combat'

export function useCombatTurnControls({
  sessionId,
  combat,
  isProcessing,
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
}) {
  const handleEndTurn = useCallback(async () => {
    if (!isPlayerTurn(combat) || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    setMoveMode(false)
    setHelpMode(false)
    setError('')
    try {
      const result = await gameApi.endTurn(sessionId)

      if (result.expired_conditions?.length) {
        result.expired_conditions.forEach(msg => addLog({ role: 'system', content: msg, log_type: 'system' }))
      }

      if (result.combat_over) {
        setCombatOver(result.outcome)
        return
      }

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
          if (nextEntry && !nextEntry.is_player) {
            aiTimer.current = setTimeout(() => triggerAiTurn(), 600)
          } else if (nextEntry?.is_player) {
            setTurnState(getPlayerTurnState(fresh, nextEntry.character_id))
          }
        }
      } catch {
        // Keep the locally advanced state when the refresh fails.
      }
    } catch (e) {
      setError(e.message)
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    aiTimer,
    combat,
    isPlayerTurn,
    isProcessing,
    processingRef,
    sessionId,
    setCombat,
    setCombatOver,
    setError,
    setHelpMode,
    setIsProcessing,
    setMoveMode,
    setTurnState,
    triggerAiTurn,
  ])

  return { handleEndTurn }
}
