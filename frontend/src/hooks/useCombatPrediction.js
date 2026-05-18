import { useEffect, useState } from 'react'
import { gameApi } from '../api/game'
import { getCombatPredictionActionKey } from '../utils/combat'

export function useCombatPrediction({
  sessionId,
  playerId,
  selectedTarget,
  playerClass,
  isRanged,
  delay = 150,
}) {
  const [prediction, setPrediction] = useState(null)

  useEffect(() => {
    if (!selectedTarget || !playerId || !sessionId) {
      setPrediction(null)
      return undefined
    }

    const timer = setTimeout(() => {
      const actionKey = getCombatPredictionActionKey(playerClass)
      gameApi.predict(sessionId, playerId, selectedTarget, actionKey, isRanged)
        .then(setPrediction)
        .catch(() => setPrediction(null))
    }, delay)

    return () => clearTimeout(timer)
  }, [selectedTarget, playerId, sessionId, playerClass, isRanged, delay])

  return prediction
}
