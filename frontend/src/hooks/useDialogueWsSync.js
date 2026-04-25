/**
 * useDialogueWsSync — Adventure 多人 WS 事件分发器（专管"DM 流程 + 房间成员刷新"）。
 *
 * 原位：Adventure.jsx 主体 onWsEvent useCallback 大段 switch（>40 行 + 8 个 deps）。
 * 抽出后 Adventure 直接 const onWsEvent = useDialogueWsSync({...})，再把它传给
 * useWebSocket。
 *
 * 不管的事情：
 *   - WS 连接生命周期 / 心跳 / 重连（useWebSocket 自己管）
 *   - WS 重连补漏 loadSession（Adventure 自己 useEffect 监 wsConnected）
 *   - speaker 标题闪烁（Adventure 自己监 currentSpeakerUid）
 *
 * @typedef {object} Deps
 * @property {string} sessionId
 * @property {string|null} myUserId
 * @property {Array<{name?: string}>} companions
 * @property {(narrative: string, companionReactions: string, companions: Array) => Array} buildDialogueQueue
 * @property {(queue: Array) => void} enterDialogueStage
 * @property {() => Promise<void>} loadSession
 * @property {(loading: boolean) => void} setIsLoading
 * @property {(updater: any) => void} setRoom
 *
 * @param {Deps} deps
 * @returns {(event: import('../types/ws').WSEvent) => void}
 */
import { useCallback } from 'react'
import { roomsApi } from '../api/client'

export function useDialogueWsSync({
  sessionId,
  myUserId,
  companions,
  buildDialogueQueue,
  enterDialogueStage,
  loadSession,
  setIsLoading,
  setRoom,
}) {
  return useCallback((event) => {
    switch (event.type) {
      case 'dm_thinking_start':
        // 别的玩家提交行动 → 我方同步显示"DM 思考中"
        if (event.by_user_id && event.by_user_id !== myUserId) {
          setIsLoading(true)
        }
        break

      case 'dm_responded': {
        const isMe = event.by_user_id && event.by_user_id === myUserId
        if (!isMe) {
          // 非发言者：用广播 payload 本地启动剧场，避免变只读观众
          setIsLoading(false)
          const queue = buildDialogueQueue(event.narrative, event.companion_reactions, companions)
          if (queue.length > 0) enterDialogueStage(queue)
        }
        // 发言者也需要 loadSession —— 广播里没有 player_choices / scene_vibe / clues
        // 这些是发言者侧通过 HTTP 响应单独拿的；loadSession 拉一次最新 game_state
        loadSession()
        break
      }

      case 'dm_speak_turn':
        setRoom(prev => prev ? { ...prev, _currentSpeaker: event.user_id } : prev)
        break

      case 'member_online':
      case 'member_offline':
      case 'member_joined':
      case 'member_left':
      case 'character_claimed':
        // 成员事件：拉一次最新房间信息（包含 is_online / character_id 等）
        roomsApi.get(sessionId)
          .then(r => r?.is_multiplayer && setRoom({ ...r, _currentSpeaker: r.current_speaker_user_id }))
          .catch(() => {})
        break

      default: break
    }
  }, [sessionId, myUserId, companions, buildDialogueQueue, enterDialogueStage, loadSession, setIsLoading, setRoom])
}
