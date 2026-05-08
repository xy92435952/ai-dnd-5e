import { useEffect, useState } from 'react'
import { roomsApi } from '../api/client'

export function normalizeAdventureRoom(room) {
  if (!room?.is_multiplayer) return null
  return { ...room, _currentSpeaker: room.current_speaker_user_id }
}

export function useAdventureRoom(sessionId) {
  const [room, setRoom] = useState(null)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const roomData = await roomsApi.get(sessionId)
        const normalized = normalizeAdventureRoom(roomData)
        if (mounted && normalized) setRoom(normalized)
      } catch {
        // Room lookup is best-effort; single-player sessions do not need it.
      }
    })()
    return () => { mounted = false }
  }, [sessionId])

  return { room, setRoom }
}
