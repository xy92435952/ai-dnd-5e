import { getRoomPresenceSummary } from '../../utils/multiplayerStatus'

export default function MultiplayerSessionStatusBar({
  room,
  label,
  title = '',
  reason = '',
  focusLabel = '',
  nextLabel = '',
  tone = 'table',
  children = null,
}) {
  if (!room?.is_multiplayer) return null
  const presence = getRoomPresenceSummary(room)

  const isActionable = tone === 'active'
  const borderColor = isActionable ? 'rgba(92,211,123,.5)' : 'rgba(240,208,96,.24)'
  const background = isActionable
    ? 'linear-gradient(90deg, rgba(42,92,56,.55), rgba(18,34,28,.82))'
    : 'rgba(24,18,10,.78)'

  return (
    <div style={{
      margin: '8px 24px 0',
      padding: '7px 10px',
      border: `1px solid ${borderColor}`,
      background,
      color: 'var(--parchment-dark)',
      fontSize: 11,
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      flexWrap: 'wrap',
      flexShrink: 0,
    }}>
      <span style={{
        color: isActionable ? 'var(--emerald-light)' : 'var(--amber)',
        fontFamily: 'var(--font-mono)',
        letterSpacing: '.12em',
        fontSize: 10,
      }}>
        {label}
      </span>
      {title && (
        <span style={{
          color: 'var(--void)',
          background: isActionable ? 'var(--emerald-light)' : 'var(--amber)',
          padding: '2px 6px',
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
        }}>
          {title}
        </span>
      )}
      {reason && (
        <span style={{ color: 'var(--parchment)' }}>{reason}</span>
      )}
      {focusLabel && (
        <span style={{ color: 'var(--arcane-light)' }}>{focusLabel}</span>
      )}
      {nextLabel && (
        <span style={{ color: 'var(--emerald-light)' }}>{nextLabel}</span>
      )}
      {children}
      {presence.label && (
        <span style={{ color: 'var(--parchment-dark)' }}>
          {presence.label}
        </span>
      )}
      {presence.offlineLabel && (
        <span style={{ color: 'var(--danger)' }}>
          {presence.offlineLabel}
        </span>
      )}
      {room.room_code && (
        <span style={{ color: 'var(--parchment-dark)', marginLeft: 'auto' }}>
          房间 {room.room_code}
        </span>
      )}
    </div>
  )
}
