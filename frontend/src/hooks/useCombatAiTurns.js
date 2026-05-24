import { useCallback } from 'react'
import { gameApi } from '../api/game'
import { applyHpUpdate, getPlayerTurnState, hasPendingAiReaction } from '../utils/combat'

const AI_TURN_LIMIT = 20

export function useCombatAiTurns({
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
}) {
  const triggerAiTurn = useCallback(async () => {
    if (processingRef.current) return
    processingRef.current = true
    setIsProcessing(true)

    try {
      let aiTurnCount = 0
      let lastTurnIndex = -1

      while (aiTurnCount < AI_TURN_LIMIT) {
        aiTurnCount++

        let fresh
        try {
          fresh = await gameApi.getCombat(sessionId)
        } catch {
          break
        }

        if (!fresh) break
        setCombat(fresh)

        if (hasPendingAiReaction(fresh)) {
          break
        }

        if (fresh.current_turn_index === lastTurnIndex) {
          console.warn('AI turn index not advancing, breaking loop')
          break
        }
        lastTurnIndex = fresh.current_turn_index

        const currentEntry = fresh.turn_order?.[fresh.current_turn_index]
        if (!currentEntry || currentEntry.is_player) {
          if (currentEntry?.is_player) {
            setTurnState(getPlayerTurnState(fresh, currentEntry.character_id))
          }
          break
        }

        let result
        try {
          result = await gameApi.aiTurn(sessionId)
        } catch (e) {
          addLog({ role: 'system', content: `AI行动错误: ${e.message}`, log_type: 'system' })
          break
        }

        if (result.skipped) {
          try {
            const latest = await gameApi.getCombat(sessionId)
            if (latest) {
              setCombat(latest)
              const latestEntry = latest.turn_order?.[latest.current_turn_index]
              if (latestEntry?.is_player) {
                setTurnState(getPlayerTurnState(latest, latestEntry.character_id))
              }
            }
          } catch {
            // A websocket update or the next manual refresh can reconcile this state.
          }
          break
        }

        if (result.concentration_check?.d20) {
          showDice({
            faces: 20,
            result: result.concentration_check.d20,
            label: `CON豁免 DC${result.concentration_check.dc || 10}`,
          })
        }

        setCombat(prev => {
          if (!prev) return prev
          const updated = applyHpUpdate(prev, result.target_id, result.target_new_hp)
          return {
            ...updated,
            current_turn_index: result.next_turn_index,
            round_number: result.round_number,
            ...(result.entity_positions ? { entity_positions: result.entity_positions } : {}),
          }
        })

        addLog({
          role: result.actor_id?.startsWith('enemy') ? 'enemy' : `companion_${result.actor_name}`,
          content: result.narration,
          log_type: 'combat',
          dice_result: result.attack_result?.d20
            ? { attack: result.attack_result, damage: result.damage }
            : null,
        })

        if (result.reaction_prompt && result.player_can_react) {
          if (result.target_id === playerId) {
            setReactionPrompt(result.reaction_prompt)
          }
          processingRef.current = false
          setIsProcessing(false)
          break
        }

        if (result.combat_over) {
          setCombatOver(result.outcome)
          break
        }

        await new Promise(r => setTimeout(r, 600))
      }
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    playerId,
    processingRef,
    sessionId,
    setCombat,
    setCombatOver,
    setIsProcessing,
    setReactionPrompt,
    setTurnState,
    showDice,
  ])

  return { triggerAiTurn }
}
