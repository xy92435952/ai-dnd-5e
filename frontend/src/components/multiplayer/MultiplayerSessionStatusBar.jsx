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

  return (
    <div
      className="multiplayer-session-status"
      data-tone={isActionable ? 'active' : 'table'}
      role="status"
      aria-label="联机状态"
    >
      <span className="multiplayer-session-status-label">
        {label}
      </span>
      {title && (
        <span className="multiplayer-session-status-title">
          {title}
        </span>
      )}
      {reason && (
        <span className="multiplayer-session-status-reason">{reason}</span>
      )}
      {focusLabel && (
        <span className="multiplayer-session-status-focus">{focusLabel}</span>
      )}
      {nextLabel && (
        <span className="multiplayer-session-status-next">{nextLabel}</span>
      )}
      {children}
      {room.room_code && (
        <span className="multiplayer-session-status-room">
          房间 {room.room_code}
        </span>
      )}
    </div>
  )
}
