import { useRoomRealtime } from './useRoomRealtime'

export function useCombatRoom(sessionId, myUserId) {
  const { room, setRoom, myCharacterId } = useRoomRealtime(sessionId, myUserId)

  return {
    room,
    setRoom,
    myCharacterId,
  }
}
