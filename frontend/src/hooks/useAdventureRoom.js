import { normalizeRealtimeRoom, useRoomRealtime } from './useRoomRealtime'

export function normalizeAdventureRoom(room) {
  return normalizeRealtimeRoom(room)
}

export function useAdventureRoom(sessionId, options = {}) {
  const { room, setRoom, refreshRoom } = useRoomRealtime(sessionId, null, options)
  return { room, setRoom, refreshRoom }
}
