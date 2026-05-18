import { normalizeAsyncError } from '../../hooks/useAsyncStatus'

const screenWrapStyle = {
  minHeight: '100vh',
  display: 'grid',
  placeItems: 'center',
  position: 'relative',
  zIndex: 1,
}

const panelStyle = {
  padding: 28,
  maxWidth: 460,
  textAlign: 'center',
  fontFamily: 'var(--font-script)',
  fontStyle: 'italic',
  color: 'var(--parchment-dark)',
}

export function LoadingState({ text = '加载中…', fullScreen = true }) {
  const body = (
    <div className="panel-ornate" style={panelStyle}>
      ✦ {text} ✦
    </div>
  )
  if (!fullScreen) return body
  return <div style={screenWrapStyle}>{body}</div>
}

export function ErrorState({
  error,
  title = '暂时无法完成请求',
  onRetry,
  fullScreen = false,
}) {
  const message = normalizeAsyncError(error)
  const isAuthError = typeof error === 'object' && error?.status === 401
  const retryText = isAuthError ? '重新登录' : '重试'

  const body = (
    <div className="panel-ornate" style={{
      ...panelStyle,
      color: '#ffaaaa',
      borderColor: 'var(--blood)',
      fontFamily: 'var(--font-mono)',
      fontStyle: 'normal',
    }}>
      <div style={{ fontFamily: 'var(--font-heading)', fontSize: 15, color: 'var(--parchment)' }}>{title}</div>
      <div style={{ marginTop: 8, fontSize: 12 }}>{message || '请求失败'}</div>
      {onRetry && (
        <button className="btn-ghost" onClick={onRetry} style={{ marginTop: 14, fontSize: 12 }}>
          {retryText}
        </button>
      )}
    </div>
  )

  if (!fullScreen) return body
  return <div style={screenWrapStyle}>{body}</div>
}

export function EmptyState({
  title,
  description = '',
  icon = '✦',
  action = null,
}) {
  return (
    <div style={{ textAlign: 'center', padding: '48px 0', opacity: 0.68 }}>
      <div style={{ fontSize: 44, marginBottom: 6 }}>{icon}</div>
      <p style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', color: 'var(--parchment-dark)', margin: 0 }}>
        {title}
      </p>
      {description && (
        <p style={{ color: 'var(--parchment-dark)', fontSize: 12, margin: '6px 0 0', fontFamily: 'var(--font-mono)' }}>
          {description}
        </p>
      )}
      {action && <div style={{ marginTop: 14 }}>{action}</div>}
    </div>
  )
}

export function ReconnectNotice({ connected = true, label = '连接' }) {
  if (connected) return null
  return (
    <div style={{
      padding: '6px 10px',
      border: '1px solid rgba(232,160,32,.45)',
      background: 'rgba(10,6,2,.68)',
      color: 'var(--amber)',
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      textAlign: 'center',
    }}>
      {label}重连中…
    </div>
  )
}

export function AsyncState({
  state,
  loadingText = '加载中…',
  error,
  onRetry,
  emptyTitle,
  emptyDescription,
  emptyIcon,
  children,
}) {
  if (state === 'loading') return <LoadingState text={loadingText} />
  if (state === 'error') return <ErrorState error={error} onRetry={onRetry} fullScreen />
  if (state === 'empty') return <EmptyState title={emptyTitle} description={emptyDescription} icon={emptyIcon} />
  return children || null
}
