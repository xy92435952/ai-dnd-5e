import { useRoomRealtime } from './useRoomRealtime'

export function useCombatRoom(sessionId, myUserId, options = {}) {
  const { room, setRoom, refreshRoom, myCharacterId } = useRoomRealtime(sessionId, myUserId, options)

  return {
    room,
    setRoom,
    refreshRoom,
    myCharacterId,
  }
}
