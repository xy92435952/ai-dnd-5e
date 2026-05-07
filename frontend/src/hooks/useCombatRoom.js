import { useEffect, useState } from 'react'
import { roomsApi } from '../api/client'

export function useCombatRoom(sessionId, myUserId) {
  const [room, setRoom] = useState(null)
  const [myCharacterId, setMyCharacterId] = useState(null)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const r = await roomsApi.get(sessionId)
        if (!mounted) return
        if (r?.is_multiplayer) {
          setRoom(r)
          const me = (r.members || []).find(m => m.user_id === myUserId)
          if (me?.character_id) setMyCharacterId(me.character_id)
        }
      } catch {
        // Single-player sessions may not have a room.
      }
    })()
    return () => { mounted = false }
  }, [sessionId, myUserId])

  return {
    room,
    setRoom,
    myCharacterId,
    setMyCharacterId,
  }
}
