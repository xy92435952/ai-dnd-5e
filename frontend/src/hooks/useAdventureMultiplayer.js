/**
 * useAdventureMultiplayer — Adventure 页面多人房间状态 + 发言权派生。
 *
 * 这层只负责房间数据加载、发言人状态派生，以及页面标题闪烁这类
 * 纯 UI 反馈，不碰 WS 发送或冒险主流程。
 */
import { useEffect, useMemo, useRef } from 'react'
import { JuiceAudio } from '../juice'

export function useAdventureMultiplayer({
  room,
  myUserId,
  wsConnected,
  session,
  loadSession,
  refreshRoom,
  onReconnectSynced,
}) {
  const currentSpeakerUid = room?._currentSpeaker
  const isMySpeakTurn = !room || (!!currentSpeakerUid && currentSpeakerUid === myUserId)
  const currentSpeakerName = useMemo(() => (
    (room?.members || []).find(m => m.user_id === currentSpeakerUid)?.display_name
  ), [room, currentSpeakerUid])

  const prevWsConnectedRef = useRef(null)
  const hasConnectedOnceRef = useRef(false)
  useEffect(() => {
    if (!room) {
      prevWsConnectedRef.current = wsConnected
      if (wsConnected) hasConnectedOnceRef.current = true
      return
    }
    const wasDisconnected = prevWsConnectedRef.current === false
    const shouldShowRecovery = wasDisconnected && hasConnectedOnceRef.current
    if (wsConnected && wasDisconnected && session) {
      let cancelled = false
      void Promise.allSettled([
        loadSession?.(),
        refreshRoom?.({ preserveOnError: true }),
      ]).then(() => {
        if (!cancelled && shouldShowRecovery) onReconnectSynced?.()
      })
      prevWsConnectedRef.current = wsConnected
      hasConnectedOnceRef.current = true
      return () => { cancelled = true }
    }
    prevWsConnectedRef.current = wsConnected
    if (wsConnected) hasConnectedOnceRef.current = true
  }, [wsConnected, room, session, loadSession, refreshRoom, onReconnectSynced])

  const prevSpeakerRef = useRef(null)
  useEffect(() => {
    if (!room) { prevSpeakerRef.current = null; return }
    const prev = prevSpeakerRef.current
    prevSpeakerRef.current = currentSpeakerUid
    if (prev && prev !== myUserId && currentSpeakerUid === myUserId) {
      try { JuiceAudio.turn() } catch {
        // Audio cues are non-critical and may be blocked by the browser.
      }
      const original = document.title
      let flipCount = 0
      const timer = setInterval(() => {
        document.title = flipCount % 2 === 0 ? '⚔ 轮到你了 · 说点什么' : original
        flipCount++
        if (flipCount >= 8) {
          clearInterval(timer)
          document.title = original
        }
      }, 600)
      return () => { clearInterval(timer); document.title = original }
    }
  }, [currentSpeakerUid, myUserId, room])

  return {
    currentSpeakerUid,
    isMySpeakTurn,
    currentSpeakerName,
  }
}
