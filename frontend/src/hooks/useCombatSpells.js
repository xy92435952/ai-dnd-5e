import { useEffect, useState } from 'react'
import { gameApi } from '../api/client'

export function useCombatSpells(sessionId) {
  const [spells, setSpells] = useState([])

  useEffect(() => {
    let mounted = true
    gameApi.getSpells()
      .then((list) => {
        if (mounted) setSpells(list || [])
      })
      .catch(() => undefined)

    return () => { mounted = false }
  }, [sessionId])

  return spells
}
