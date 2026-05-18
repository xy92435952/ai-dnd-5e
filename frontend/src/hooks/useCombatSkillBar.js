import { useEffect, useState } from 'react'
import { gameApi } from '../api/game'

export function useCombatSkillBar({ sessionId, playerId, refreshKey }) {
  const [skillBar, setSkillBar] = useState(null)

  useEffect(() => {
    if (!sessionId || !playerId) return undefined

    let mounted = true
    gameApi.getSkillBar(sessionId, playerId)
      .then((data) => {
        if (mounted && data?.bar) setSkillBar(data.bar)
      })
      .catch(() => undefined)

    return () => { mounted = false }
  }, [sessionId, playerId, refreshKey])

  return skillBar
}
