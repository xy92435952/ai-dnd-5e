import { useCallback } from 'react'
import { gameApi } from '../api/client'
import { applyActionResultEntityStates, getCombatTurnToken, getPlayerTurnState } from '../utils/combat'
import { getPendingReactionPrompt } from '../utils/combatSession'
import { buildCombatResultImpactSummary, buildCombatStateChangeSummary } from '../utils/combatLog'

const AI_TURN_LIMIT = 20

export function useCombatAiTurns({
  sessionId,
  playerId,
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

        const playerTurnState = getPlayerTurnState(fresh, playerId)
        const pendingReaction = getPendingReactionPrompt(playerTurnState, playerId)
        if (pendingReaction) {
          setTurnState(playerTurnState)
          setReactionPrompt(pendingReaction)
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
          const turnToken = getCombatTurnToken(fresh)
          result = await gameApi.aiTurn(sessionId, turnToken)
        } catch (e) {
          if ((e.message || '').includes('AI turn token is stale')) {
            break
          }
          addLog({ role: 'system', content: `AI行动错误: ${e.message}`, log_type: 'system' })
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
          const updated = applyActionResultEntityStates(prev, result)
          return {
            ...updated,
            current_turn_index: result.next_turn_index,
            round_number: result.round_number,
            ...(result.entity_positions ? { entity_positions: result.entity_positions } : {}),
          }
        })

        const impactSummary = buildCombatResultImpactSummary(result)
        addLog({
          role: result.actor_id?.startsWith('enemy') ? 'enemy' : `companion_${result.actor_name}`,
          content: result.narration,
          log_type: 'combat',
          dice_result: result.attack_result?.d20
            ? { attack: result.attack_result, damage: result.damage }
            : null,
          ...(impactSummary.length > 0 ? { impact_summary: impactSummary } : {}),
          state_changes: buildCombatStateChangeSummary(result),
        })

        if (result.reaction_prompt && result.player_can_react) {
          setReactionPrompt(result.reaction_prompt)
          processingRef.current = false
          setIsProcessing(false)
          break
        }

        if (result.lair_action_prompt) {
          setLairActionPrompt?.(result.lair_action_prompt)
          setLegendaryActionPrompt?.(null)
          break
        }

        if (result.legendary_action_prompt) {
          setLegendaryActionPrompt?.(result.legendary_action_prompt)
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
    processingRef,
    playerId,
    sessionId,
    setCombat,
    setCombatOver,
    setIsProcessing,
    setLairActionPrompt,
    setLegendaryActionPrompt,
    setReactionPrompt,
    setTurnState,
    showDice,
  ])

  return { triggerAiTurn }
}
