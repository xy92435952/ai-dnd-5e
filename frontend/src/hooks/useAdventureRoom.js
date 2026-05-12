import { normalizeRealtimeRoom, useRoomRealtime } from './useRoomRealtime'

export function normalizeAdventureRoom(room) {
  return normalizeRealtimeRoom(room)
}

export function useAdventureRoom(sessionId) {
  const { room, setRoom, refreshRoom } = useRoomRealtime(sessionId)
  return { room, setRoom, refreshRoom }
}
