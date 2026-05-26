import { useRoomRealtime } from './useRoomRealtime'

export function useCombatRoom(sessionId, myUserId) {
  const { room, setRoom, refreshRoom, myCharacterId } = useRoomRealtime(sessionId, myUserId)

  return {
    room,
    setRoom,
    refreshRoom,
    myCharacterId,
  }
}
