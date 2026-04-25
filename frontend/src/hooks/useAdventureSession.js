/**
 * useAdventureSession — Adventure 页面会话加载 + 三个主状态的容器。
 *
 * 管的事情：
 *   - session / player / companions 三个 state
 *   - loadSession()：从后端拉 /game/sessions/{id}，写回上述 state
 *   - 战斗激活时自动导航到 /combat/{id}
 *   - mount 时自动加载一次
 *
 * 不管的事情（让 Adventure 通过 onLoaded callback 处理）：
 *   - logs 同步（Adventure 的 addLog 在太多地方被调用，logs state 留给 Adventure 管）
 *   - last_turn 恢复（要调 useSkillCheck / useState 的 setter）
 *   - 首次剧场模式（要调 useDialogueFlow.enterStage）
 *   - WS 重连补漏（依赖外部的 wsConnected / room 状态）
 *
 * @param {{
 *   sessionId: string,
 *   onLoaded?: (data: import('../types/api-responses').SessionDetail) => void,
 *   onError?:  (err: Error) => void,
 * }} deps
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { gameApi } from '../api/client'
import { useGameStore } from '../store/gameStore'

export function useAdventureSession({ sessionId, onLoaded, onError }) {
  const navigate = useNavigate()
  const setCombatActive = useGameStore(s => s.setCombatActive)

  const [session,    setSession]    = useState(null)
  const [player,     setPlayer]     = useState(null)
  const [companions, setCompanions] = useState([])

  // 用 ref 转发 callback，保持 loadSession 引用稳定（不会因 callback 重建而触发 useEffect）
  // 同时调用时拿到的总是最新 callback（闭包陈旧问题不会发生）
  const onLoadedRef = useRef(onLoaded)
  const onErrorRef  = useRef(onError)
  useEffect(() => { onLoadedRef.current = onLoaded })
  useEffect(() => { onErrorRef.current  = onError })

  const loadSession = useCallback(async () => {
    try {
      const data = await gameApi.getSession(sessionId)
      setSession(data)
      setPlayer(data.player)
      setCompanions(data.companions || [])
      setCombatActive(false)
      if (data.combat_active) {
        navigate(`/combat/${sessionId}`)
        return
      }
      // logs 和其他下游副作用交给 Adventure 的 onLoaded 处理
      onLoadedRef.current?.(data)
    } catch (e) {
      onErrorRef.current?.(e)
    }
  }, [sessionId, navigate, setCombatActive])

  // mount 时自动加载一次
  useEffect(() => {
    loadSession()
  }, [sessionId, loadSession])

  return {
    session, setSession,
    player, setPlayer,
    companions, setCompanions,
    loadSession,
  }
}
