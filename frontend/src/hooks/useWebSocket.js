/**
 * useWebSocket — 多人联机 WS 客户端 Hook
 *
 * 用法：
 *   /** @type {(event: import('../types/ws').WSEvent) => void} *\/
 *   const onEvent = (e) => { switch (e.type) { ... } }
 *   const { connected, send, status } = useWebSocket(sessionId, onEvent)
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
 * @returns {{ connected: boolean, status: object, send: (event: object) => boolean }}
 */
import { useEffect, useRef, useState, useCallback } from 'react'

const HEARTBEAT_MS = 15000
const RECONNECT_BASE_MS = 1000
const RECONNECT_MAX_MS = 30000
const STATUS_IDLE = {
  state: 'idle',
  label: '未连接',
  detail: '当前页面没有联机会话。',
  canRetry: false,
  retryInMs: null,
  closeCode: null,
}
const STATUS_CONNECTED = {
  state: 'connected',
  label: '同步在线',
  detail: '实时同步已连接。',
  canRetry: false,
  retryInMs: null,
  closeCode: null,
}

function buildClosedStatus(event) {
  const code = event?.code || null
  if (code === 4401) {
    return {
      state: 'auth_error',
      label: '登录失效',
      detail: '登录凭证已失效，请重新登录后恢复联机同步。',
      canRetry: false,
      retryInMs: null,
      closeCode: code,
    }
  }
  if (code === 4403) {
    return {
      state: 'permission_error',
      label: '无房间权限',
      detail: '当前账号没有这个房间的联机权限，请确认房间码或重新加入。',
      canRetry: false,
      retryInMs: null,
      closeCode: code,
    }
  }
  return null
}

export function useWebSocket(sessionId, onEvent) {
  const wsRef = useRef(null)
  const heartbeatRef = useRef(null)
  const reconnectRef = useRef(null)
  const connectRef = useRef(null)
  const retryCountRef = useRef(0)
  const closedByUserRef = useRef(false)
  const onEventRef = useRef(onEvent)
  const [connected, setConnected] = useState(false)
  const [status, setStatus] = useState(STATUS_IDLE)

  // 让 onEvent 始终是最新引用，避免重连时丢失新版本
  useEffect(() => { onEventRef.current = onEvent }, [onEvent])

  const buildUrl = useCallback(() => {
    if (!sessionId) {
      return { url: null, status: STATUS_IDLE }
    }
    const token = localStorage.getItem('token')
    if (!token) {
      return {
        url: null,
        status: {
          state: 'missing_token',
          label: '需要登录',
          detail: '登录凭证不存在，请登录后恢复联机同步。',
          canRetry: false,
          retryInMs: null,
          closeCode: null,
        },
      }
    }
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host  // 包含端口；vite 代理在 dev 模式会处理
    return {
      url: `${proto}//${host}/api/ws/sessions/${sessionId}?token=${encodeURIComponent(token)}`,
      status: null,
    }
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

  const scheduleReconnect = useCallback((reason = {}) => {
    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, retryCountRef.current),
      RECONNECT_MAX_MS,
    )
    retryCountRef.current += 1
    setStatus({
      state: 'reconnecting',
      label: '正在重连',
      detail: reason.detail || '服务器暂不可达或正在重启，正在自动重连。',
      canRetry: true,
      retryInMs: delay,
      closeCode: reason.closeCode || null,
    })
    reconnectRef.current = setTimeout(() => {
      connectRef.current?.()
    }, delay)
  }, [])

  const connect = useCallback(() => {
    const target = buildUrl()
    if (!target.url) {
      cleanup()
      setConnected(false)
      setStatus(target.status || STATUS_IDLE)
      return
    }

    cleanup()
    closedByUserRef.current = false
    setConnected(false)
    setStatus({
      state: 'connecting',
      label: '正在连接',
      detail: '正在连接房间同步服务。',
      canRetry: true,
      retryInMs: null,
      closeCode: null,
    })

    let ws
    try {
      ws = new WebSocket(target.url)
    } catch (e) {
      console.warn('[WS] connect failed:', e)
      scheduleReconnect({ detail: '无法创建 WebSocket 连接，正在自动重试。' })
      return
    }

    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setStatus(STATUS_CONNECTED)
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
      if (closedByUserRef.current) {
        setStatus(STATUS_IDLE)
        return
      }
      const terminalStatus = buildClosedStatus(e)
      if (terminalStatus) {
        setStatus(terminalStatus)
        return
      }
      scheduleReconnect({
        closeCode: e?.code || null,
        detail: e?.code === 1006
          ? '服务器暂不可达或正在重启，正在自动重连。'
          : '联机同步已断开，正在自动重连。',
      })
    }

    ws.onerror = (err) => {
      console.warn('[WS] error:', err)
      setStatus(prev => prev.state === 'connected' ? prev : {
        state: 'unavailable',
        label: '服务器暂不可达',
        detail: 'WebSocket 连接失败，等待断开事件后会自动重试。',
        canRetry: true,
        retryInMs: null,
        closeCode: prev.closeCode || null,
      })
    }
  }, [buildUrl, cleanup, scheduleReconnect])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  // 主连接生命周期
  useEffect(() => {
    if (!sessionId) {
      setConnected(false)
      setStatus(STATUS_IDLE)
      return
    }
    connect()
    return () => {
      closedByUserRef.current = true
      cleanup()
      if (wsRef.current) {
        try { wsRef.current.close() } catch {}
        wsRef.current = null
      }
      setConnected(false)
      setStatus(STATUS_IDLE)
    }
  }, [sessionId, connect, cleanup])

  const send = useCallback((event) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(event))
      return true
    }
    return false
  }, [])

  return { connected, status, send }
}
