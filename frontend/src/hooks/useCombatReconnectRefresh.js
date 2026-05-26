import { useEffect, useRef } from 'react'

export function useCombatReconnectRefresh({
  room,
  combat,
  wsConnected,
  loadCombat,
  refreshRoom,
}) {
  const prevWsConnectedRef = useRef(false)

  useEffect(() => {
    if (!room) {
      prevWsConnectedRef.current = wsConnected
      return
    }
    const wasDisconnected = !prevWsConnectedRef.current
    if (wsConnected && wasDisconnected && combat) {
      void Promise.allSettled([
        loadCombat?.(),
        refreshRoom?.({ preserveOnError: true }),
      ])
    }
    prevWsConnectedRef.current = wsConnected
  }, [wsConnected, room, combat, loadCombat, refreshRoom])
}
