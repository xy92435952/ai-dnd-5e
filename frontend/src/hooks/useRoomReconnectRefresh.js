import { useEffect, useRef } from 'react'

export function useRoomReconnectRefresh({
  room,
  wsConnected,
  refresh,
}) {
  const prevWsConnectedRef = useRef(false)

  useEffect(() => {
    if (!room) {
      prevWsConnectedRef.current = wsConnected
      return
    }
    const wasDisconnected = !prevWsConnectedRef.current
    if (wsConnected && wasDisconnected) {
      void refresh?.()
    }
    prevWsConnectedRef.current = wsConnected
  }, [wsConnected, room, refresh])
}
