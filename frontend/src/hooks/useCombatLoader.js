import { useCallback, useEffect } from 'react'
import { gameApi } from '../api/client'
import { applyCombatSessionSnapshot } from '../utils/combatSession'
import { isCombatEndedError } from '../utils/combatEnded'

export function useCombatLoader({
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
  canDriveAiTurns = true,
}) {
  const loadCombat = useCallback(async () => {
    try {
      const data = await gameApi.getCombat(sessionId)
      const sessionData = await gameApi.getSession(sessionId)
      const { playerId: pid, playerEntry, pendingReaction } = applyCombatSessionSnapshot({
        combatData: data,
        sessionData,
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
      })

      if (data.round_number === 1 && !initiativeShown && pid) {
        if (playerEntry && playerEntry.initiative != null) {
          setInitiativeShown(true)
          const d20Val = playerEntry.d20 || playerEntry.initiative
          // Initiative has already been settled by the backend; avoid opening an interactive roll prompt on load.
          showDice({ faces: 20, result: d20Val, label: '先攻检定' })
        }
      }

      if (aiTimer.current) {
        clearTimeout(aiTimer.current)
        aiTimer.current = null
      }

      if (canDriveAiTurns && !pendingReaction && !isPlayerTurn(data)) {
        aiTimer.current = setTimeout(() => {
          aiTimer.current = null
          triggerAiTurn()
        }, 1000)
      }
    } catch (e) {
      if (isCombatEndedError(e)) {
        if (aiTimer.current) {
          clearTimeout(aiTimer.current)
          aiTimer.current = null
        }
        onCombatEnded?.()
        return
      }
      setError(e.message)
    }
  }, [
    aiTimer,
    canDriveAiTurns,
    initiativeShown,
    isPlayerTurn,
    sessionId,
    setClassResources,
    setCombat,
    setError,
    setInitiativeShown,
    setLogs,
    setPlayerCantrips,
    setPlayerClass,
    setPlayerId,
    setPlayerKnownSpells,
    setPlayerLevel,
    setPlayerSpellSlots,
    setPlayerSubclass,
    setPlayerSubclassEffects,
    setReactionPrompt,
    setSession,
    setTurnState,
    onCombatEnded,
    showDice,
    triggerAiTurn,
  ])

  useEffect(() => {
    loadCombat()
    return () => {
      clearTimeout(aiTimer.current)
      aiTimer.current = null
    }
  }, [loadCombat, aiTimer])

  return { loadCombat }
}
