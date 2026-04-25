/**
 * useWebSocket — 多人联机 WS 客户端 Hook
 *
 * 用法：
 *   /** @type {(event: import('../types/ws').WSEvent) => void} *\/
 *   const onEvent = (e) => { switch (e.type) { ... } }
 *   const { connected, send } = useWebSocket(sessionId, onEvent)
 *
 * 自动：
 *   - 建立连接 + JWT 鉴权（token 来自 localStorage）
 *   - 每 15s 心跳（pong）保持 last_seen_at
 *   - 断线 3s 后自动重连（指数退避，最多 30s）
 *   - 组件卸载时清理
 *
 * 不负责：
 *   - 业务事件分发（由 onEvent 回调处理）
 *   - 状态管理（由调用方注入到 Zustand store）
 *
 * @param {string|null} sessionId
 * @param {(event: import('../types/ws').WSEvent) => void} onEvent
 * @returns {{ connected: boolean, send: (event: object) => boolean }}
 */
import { useEffect, useRef, useState, useCallback } from 'react'

const HEARTBEAT_MS = 15000
const RECONNECT_BASE_MS = 1000
const RECONNECT_MAX_MS = 30000

export function useWebSocket(sessionId, onEvent) {
  const wsRef = useRef(null)
  const heartbeatRef = useRef(null)
  const reconnectRef = useRef(null)
  const retryCountRef = useRef(0)
  const closedByUserRef = useRef(false)
  const onEventRef = useRef(onEvent)
  const [connected, setConnected] = useState(false)

  // 让 onEvent 始终是最新引用，避免重连时丢失新版本
  useEffect(() => { onEventRef.current = onEvent }, [onEvent])

  const buildUrl = useCallback(() => {
    const token = localStorage.getItem('token')
    if (!token || !sessionId) return null
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host  // 包含端口；vite 代理在 dev 模式会处理
    return `${proto}//${host}/api/ws/sessions/${sessionId}?token=${encodeURIComponent(token)}`
  }, [sessionId])

  const cleanup = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current)
      heartbeatRef.current = null
    }
    if (reconnectRef.current) {
      clearTimeout(reconnectRef.current)
      reconnectRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    const url = buildUrl()
    if (!url) return

    cleanup()
    closedByUserRef.current = false

    let ws
    try {
      ws = new WebSocket(url)
    } catch (e) {
      console.warn('[WS] connect failed:', e)
      scheduleReconnect()
      return
    }

    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      retryCountRef.current = 0
      // 启动心跳
      heartbeatRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'pong' }))
        }
      }, HEARTBEAT_MS)
    }

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        onEventRef.current?.(event)
      } catch (err) {
        console.warn('[WS] bad message:', err)
      }
    }

    ws.onclose = (e) => {
      setConnected(false)
      cleanup()
      if (!closedByUserRef.current && e.code !== 4401 && e.code !== 4403) {
        // 4401/4403 是鉴权/权限错误，不应重连
        scheduleReconnect()
      }
    }

    ws.onerror = (err) => {
      console.warn('[WS] error:', err)
    }
  }, [buildUrl, cleanup])

  const scheduleReconnect = useCallback(() => {
    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, retryCountRef.current),
      RECONNECT_MAX_MS,
    )
    retryCountRef.current += 1
    reconnectRef.current = setTimeout(connect, delay)
  }, [connect])

  // 主连接生命周期
  useEffect(() => {
    if (!sessionId) return
    connect()
    return () => {
      closedByUserRef.current = true
      cleanup()
      if (wsRef.current) {
        try { wsRef.current.close() } catch {}
        wsRef.current = null
      }
      setConnected(false)
    }
    // 不监听 connect/cleanup（它们是 useCallback，仅 sessionId 变化时重连）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const send = useCallback((event) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(event))
      return true
    }
    return false
  }, [])

  return { connected, send }
}
