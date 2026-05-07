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
}) {
  const currentSpeakerUid = room?._currentSpeaker
  const isMySpeakTurn = !room || !currentSpeakerUid || currentSpeakerUid === myUserId
  const currentSpeakerName = useMemo(() => (
    (room?.members || []).find(m => m.user_id === currentSpeakerUid)?.display_name
  ), [room, currentSpeakerUid])

  const prevWsConnectedRef = useRef(false)
  useEffect(() => {
    if (!room) return
    const wasDisconnected = !prevWsConnectedRef.current
    if (wsConnected && wasDisconnected && session) {
      loadSession()
    }
    prevWsConnectedRef.current = wsConnected
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsConnected, room])

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
