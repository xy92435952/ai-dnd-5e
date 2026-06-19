const STATUS_TONES = new Set([
  'connected',
  'connecting',
  'reconnecting',
  'unavailable',
  'auth_error',
  'permission_error',
  'missing_token',
  'idle',
])

function formatRetry(retryInMs) {
  if (!retryInMs) return ''
  return ` · ${Math.ceil(retryInMs / 1000)}秒后重试`
}

function getWebSocketStatusText(status, fallbackConnected = false) {
  if (!status) {
    return fallbackConnected
      ? { label: '同步在线', detail: '实时同步已连接。' }
      : { label: '正在重连', detail: '服务器暂不可达或正在重启，正在自动重连。' }
  }
  return {
    label: status.label || (fallbackConnected ? '同步在线' : '正在重连'),
    detail: `${status.detail || ''}${formatRetry(status.retryInMs)}`,
  }
}

export default function WebSocketStatusPill({
  status,
  connected = false,
  compact = false,
}) {
  const text = getWebSocketStatusText(status, connected)
  const tone = STATUS_TONES.has(status?.state)
    ? status.state
    : connected ? 'connected' : 'reconnecting'

  return (
    <span
      className={`websocket-status-pill${compact ? ' compact' : ''}`}
      data-state={tone}
      title={text.detail || text.label}
    >
      {text.label}
    </span>
  )
}
