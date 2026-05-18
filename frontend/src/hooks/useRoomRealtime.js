import { useCallback, useEffect, useMemo, useState } from 'react'
import { roomsApi } from '../api/rooms'

export function normalizeRealtimeRoom(room) {
  if (!room?.is_multiplayer) return null
  return {
    ...room,
    _currentSpeaker: room.current_speaker_user_id,
  }
}

export function mergeRealtimeRoomEvent(prev, event) {
  if (!event) return prev
  if (event.type === 'room_state_updated' && event.room) {
    return normalizeRealtimeRoom(event.room)
  }
  if (Array.isArray(event.members)) {
    return prev ? {
      ...prev,
      members: event.members,
      _currentSpeaker: event.current_speaker_user_id || prev._currentSpeaker,
    } : prev
  }
  return prev
}

export function useRoomRealtime(sessionId, myUserId = null) {
  const [room, setRoom] = useState(null)
  const [error, setError] = useState('')

  const refreshRoom = useCallback(async () => {
    if (!sessionId) return null
    try {
      const data = await roomsApi.get(sessionId)
      const normalized = normalizeRealtimeRoom(data)
      setRoom(normalized)
      setError('')
      return normalized
    } catch (e) {
      setRoom(null)
      setError(e.message || '')
      return null
    }
  }, [sessionId])

  useEffect(() => {
    let mounted = true
    ;(async () => {
      const data = await refreshRoom()
      if (!mounted) return
      setRoom(data)
    })()
    return () => { mounted = false }
  }, [refreshRoom])

  const myMember = useMemo(() => (
    (room?.members || []).find(member => member.user_id === myUserId) || null
  ), [myUserId, room])

  return {
    room,
    setRoom,
    refreshRoom,
    myMember,
    myCharacterId: myMember?.character_id || null,
    error,
  }
}
