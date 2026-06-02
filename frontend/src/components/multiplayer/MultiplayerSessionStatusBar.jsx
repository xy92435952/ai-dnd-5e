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

  const isActionable = tone === 'active'
  const borderColor = isActionable ? 'rgba(92,211,123,.5)' : 'rgba(240,208,96,.24)'
  const background = isActionable
    ? 'linear-gradient(90deg, rgba(42,92,56,.55), rgba(18,34,28,.82))'
    : 'rgba(24,18,10,.78)'
  const textItemStyle = {
    minWidth: 0,
    overflowWrap: 'anywhere',
    lineHeight: 1.35,
  }

  return (
    <div role="status" aria-label="联机状态" style={{
      margin: '8px clamp(10px, 3vw, 24px) 0',
      padding: '7px 10px',
      border: `1px solid ${borderColor}`,
      background,
      color: 'var(--parchment-dark)',
      fontSize: 11,
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      rowGap: 6,
      flexWrap: 'wrap',
      flexShrink: 0,
      minWidth: 0,
      boxSizing: 'border-box',
    }}>
      <span style={{
        color: isActionable ? 'var(--emerald-light)' : 'var(--amber)',
        fontFamily: 'var(--font-mono)',
        letterSpacing: '.12em',
        fontSize: 10,
        whiteSpace: 'nowrap',
        flex: '0 0 auto',
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
          whiteSpace: 'nowrap',
          flex: '0 0 auto',
        }}>
          {title}
        </span>
      )}
      {reason && (
        <span style={{ ...textItemStyle, color: 'var(--parchment)', flex: '1 1 180px' }}>{reason}</span>
      )}
      {focusLabel && (
        <span style={{ ...textItemStyle, color: 'var(--arcane-light)', flex: '1 1 140px' }}>{focusLabel}</span>
      )}
      {nextLabel && (
        <span style={{ ...textItemStyle, color: 'var(--emerald-light)', flex: '1 1 160px' }}>{nextLabel}</span>
      )}
      {children}
      {room.room_code && (
        <span style={{
          color: 'var(--parchment-dark)',
          marginLeft: 'auto',
          whiteSpace: 'nowrap',
          flex: '0 0 auto',
        }}>
          房间 {room.room_code}
        </span>
      )}
    </div>
  )
}
