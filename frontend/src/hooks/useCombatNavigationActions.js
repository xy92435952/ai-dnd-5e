import { useCallback, useState } from 'react'
import { gameApi } from '../api/client'

export function useCombatNavigationActions({ sessionId, navigate }) {
  const [forceEndConfirmOpen, setForceEndConfirmOpen] = useState(false)

  const returnToAdventure = useCallback(() => {
    navigate(`/adventure/${sessionId}`)
  }, [navigate, sessionId])

  const endCombatAndReturn = useCallback(async () => {
    await gameApi.endCombat?.(sessionId)
    navigate(`/adventure/${sessionId}`)
  }, [navigate, sessionId])

  const forceEndCombat = useCallback(() => {
    setForceEndConfirmOpen(true)
  }, [])

  const cancelForceEndCombat = useCallback(() => {
    setForceEndConfirmOpen(false)
  }, [])

  const confirmForceEndCombat = useCallback(async () => {
    setForceEndConfirmOpen(false)
    await gameApi.endCombat?.(sessionId)
    navigate(`/adventure/${sessionId}`)
  }, [navigate, sessionId])

  return {
    returnToAdventure,
    endCombatAndReturn,
    forceEndCombat,
    forceEndConfirmOpen,
    cancelForceEndCombat,
    confirmForceEndCombat,
  }
}
