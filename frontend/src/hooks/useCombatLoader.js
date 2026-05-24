import { useCallback, useEffect } from 'react'
import { gameApi } from '../api/game'
import { applyCombatSessionSnapshot } from '../utils/combatSession'
import { hasPendingAiReaction } from '../utils/combat'

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
  showDice,
  triggerAiTurn,
  isPlayerTurn,
}) {
  const loadCombat = useCallback(async () => {
    try {
      const data = await gameApi.getCombat(sessionId)
      const sessionData = await gameApi.getSession(sessionId)
      setError('')
      const { playerId: pid, playerEntry } = applyCombatSessionSnapshot({
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
          const d20Val = playerEntry.d20 ?? playerEntry.initiative
          showDice({ faces: 20, result: d20Val, label: '先攻检定' })
        }
      }

      if (!isPlayerTurn(data) && !hasPendingAiReaction(data)) {
        aiTimer.current = setTimeout(() => triggerAiTurn(), 1000)
      }
    } catch (e) {
      setError(e.message)
    }
  }, [
    aiTimer,
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
    showDice,
    triggerAiTurn,
  ])

  useEffect(() => {
    loadCombat()
    return () => clearTimeout(aiTimer.current)
  }, [loadCombat, aiTimer])

  return { loadCombat }
}
