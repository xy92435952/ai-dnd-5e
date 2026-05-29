const TONE = {
  connected: {
    border: 'var(--emerald-light)',
    color: 'var(--emerald-light)',
  },
  connecting: {
    border: 'var(--wood-light)',
    color: 'var(--parchment-dark)',
  },
  reconnecting: {
    border: 'var(--amber)',
    color: 'var(--amber)',
  },
  unavailable: {
    border: 'var(--amber)',
    color: 'var(--amber)',
  },
  auth_error: {
    border: 'var(--blood)',
    color: '#ffaaaa',
  },
  permission_error: {
    border: 'var(--blood)',
    color: '#ffaaaa',
  },
  missing_token: {
    border: 'var(--blood)',
    color: '#ffaaaa',
  },
  idle: {
    border: 'var(--wood-light)',
    color: 'var(--parchment-dark)',
  },
}

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
  const tone = TONE[status?.state] || (connected ? TONE.connected : TONE.reconnecting)

  return (
    <span title={text.detail || text.label} style={{
      padding: '2px 7px',
      border: `1px solid ${tone.border}`,
      color: tone.color,
      borderRadius: 3,
      fontSize: 10,
      fontFamily: 'var(--font-mono)',
      whiteSpace: compact ? 'normal' : 'nowrap',
      maxWidth: compact ? 220 : 'none',
    }}>
      {text.label}
    </span>
  )
}
