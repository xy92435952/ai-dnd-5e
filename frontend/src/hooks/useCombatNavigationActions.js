import { useCallback } from 'react'
import { gameApi } from '../api/game'

export function useCombatNavigationActions({ sessionId, navigate }) {
  const returnToAdventure = useCallback(() => {
    navigate(`/adventure/${sessionId}`)
  }, [navigate, sessionId])

  const endCombatAndReturn = useCallback(async () => {
    await gameApi.endCombat?.(sessionId)
    navigate(`/adventure/${sessionId}`)
  }, [navigate, sessionId])

  const forceEndCombat = useCallback(async () => {
    if (confirm('强制结束战斗？')) {
      await gameApi.endCombat?.(sessionId)
      navigate(`/adventure/${sessionId}`)
    }
  }, [navigate, sessionId])

  return {
    returnToAdventure,
    endCombatAndReturn,
    forceEndCombat,
  }
}
